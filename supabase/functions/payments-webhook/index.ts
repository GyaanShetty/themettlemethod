// Payments webhook. Verifies the sender, turns the provider's payload into one normalised event,
// and hands it to apply_payment_event, which applies it exactly once.
//   POST /payments-webhook?provider=gumroad&token=...   (Gumroad ping, form-encoded)
//   POST /payments-webhook?provider=stripe              (Stripe-Signature header)
//   POST /payments-webhook?provider=razorpay            (X-Razorpay-Signature header)
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

type Kind = "sale" | "refund" | "cancelled" | "ended";
interface PaymentEvent {
  provider: string; event_id: string; kind: Kind; email?: string; user_id?: string;
  provider_ref: string; sale_ref?: string; amount_cents?: number; currency?: string;
  product?: string; stream: string; billing_interval?: string; period_end?: string;
}
interface Provider { verify(req: Request, raw: string, url: URL): Promise<boolean>; parse(raw: string): PaymentEvent | null }

const env = (k: string) => Deno.env.get(k) ?? "";
const enc = new TextEncoder();
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function safeEqual(a: string, b: string): boolean {
  const x = enc.encode(a), y = enc.encode(b);
  if (x.length !== y.length) return false;
  let d = 0;
  for (let i = 0; i < x.length; i++) d |= x[i] ^ y[i];
  return d === 0;
}
async function hmacHex(secret: string, msg: string): Promise<string> {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(msg));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
const plus = (iso: string | undefined, interval?: string) => {
  const d = iso ? new Date(iso) : new Date();
  if (interval === "year") d.setUTCFullYear(d.getUTCFullYear() + 1); else d.setUTCMonth(d.getUTCMonth() + 1);
  return d.toISOString();
};

// Gumroad pings carry no signature. The sender is checked three ways: a secret in the URL that only
// Gumroad was given, the seller id on the ping, and the inner product's permalink deciding the stream.
const gumroad: Provider = {
  async verify(_req, raw, url) {
    const secret = env("GUMROAD_WEBHOOK_SECRET"), seller = env("GUMROAD_SELLER_ID");
    if (!secret || !seller) return false;
    const f = new URLSearchParams(raw);
    return safeEqual(url.searchParams.get("token") ?? "", secret) && safeEqual(f.get("seller_id") ?? "", seller);
  },
  parse(raw) {
    const f = new URLSearchParams(raw);
    const resource = f.get("resource_name") ?? "sale";
    const sub = f.get("subscription_id") ?? "", sale = f.get("sale_id") ?? "";
    if (!sub && !sale) return null;
    const inner = !!env("GUMROAD_INNER_PERMALINK") && f.get("product_permalink") === env("GUMROAD_INNER_PERMALINK");
    const interval = f.get("recurrence") === "yearly" ? "year" : f.get("recurrence") ? "month" : undefined;
    const kind: Kind = resource === "cancellation" ? "cancelled" : resource === "subscription_ended" ? "ended"
      : resource === "refund" || f.get("refunded") === "true" ? "refund" : "sale";
    return {
      provider: "gumroad", event_id: `${resource}:${sale || sub}`, kind,
      email: f.get("email") ?? undefined, user_id: f.get("url_params[user_id]") ?? undefined,
      provider_ref: sub || sale, sale_ref: sale || undefined,
      amount_cents: f.get("price") ? Number(f.get("price")) : undefined, currency: (f.get("currency") ?? "usd").toUpperCase(),
      product: f.get("product_permalink") ?? undefined, stream: inner || (sub && !sale) ? "inner_order" : "products",
      billing_interval: interval, period_end: kind === "sale" && sub ? plus(f.get("sale_timestamp") ?? undefined, interval) : undefined,
    };
  },
};

const stripe: Provider = {
  async verify(req, raw) {
    const secret = env("STRIPE_WEBHOOK_SECRET");
    if (!secret) return false;
    const parts = Object.fromEntries((req.headers.get("stripe-signature") ?? "").split(",").map((p) => p.split("=") as [string, string]));
    if (!parts.t || !parts.v1 || Math.abs(Date.now() / 1000 - Number(parts.t)) > 300) return false;
    return safeEqual(await hmacHex(secret, `${parts.t}.${raw}`), parts.v1);
  },
  parse(raw) {
    const ev = JSON.parse(raw), o = ev.data?.object ?? {};
    const base = { provider: "stripe", event_id: ev.id as string, stream: "inner_order" };
    if (ev.type === "invoice.paid" && o.subscription) {
      const line = o.lines?.data?.[0];
      return { ...base, kind: "sale", email: o.customer_email, user_id: o.subscription_details?.metadata?.user_id, provider_ref: o.subscription, sale_ref: o.id,
        amount_cents: o.amount_paid, currency: String(o.currency).toUpperCase(), billing_interval: line?.price?.recurring?.interval,
        period_end: line?.period?.end ? new Date(line.period.end * 1000).toISOString() : undefined };
    }
    if (ev.type === "customer.subscription.updated" && o.cancel_at_period_end) return { ...base, kind: "cancelled", provider_ref: o.id };
    if (ev.type === "customer.subscription.deleted") return { ...base, kind: "ended", provider_ref: o.id };
    return null;
  },
};

const razorpay: Provider = {
  async verify(req, raw) {
    const secret = env("RAZORPAY_WEBHOOK_SECRET");
    return !!secret && safeEqual(await hmacHex(secret, raw), req.headers.get("x-razorpay-signature") ?? "");
  },
  parse(raw) {
    const ev = JSON.parse(raw), sub = ev.payload?.subscription?.entity, pay = ev.payload?.payment?.entity;
    if (!sub) return null;
    const base = { provider: "razorpay", event_id: `${ev.event}:${pay?.id ?? sub.id}:${ev.created_at ?? ""}`, stream: "inner_order", provider_ref: sub.id as string };
    if (ev.event === "subscription.charged") {
      return { ...base, kind: "sale", email: pay?.email, user_id: sub.notes?.user_id, sale_ref: pay?.id, amount_cents: pay?.amount,
        currency: pay?.currency, period_end: sub.current_end ? new Date(sub.current_end * 1000).toISOString() : undefined };
    }
    if (ev.event === "subscription.cancelled") return { ...base, kind: "cancelled" };
    if (ev.event === "subscription.completed" || ev.event === "subscription.halted") return { ...base, kind: "ended" };
    return null;
  },
};

const PROVIDERS: Record<string, Provider> = { gumroad, stripe, razorpay };

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);
  const url = new URL(req.url);
  const provider = PROVIDERS[url.searchParams.get("provider") ?? ""];
  if (!provider) return json({ error: "unknown provider" }, 400);

  const db = createClient(env("SUPABASE_URL"), env("SUPABASE_SERVICE_ROLE_KEY"), { auth: { persistSession: false } });
  const ip = (req.headers.get("x-forwarded-for") ?? "unknown").split(",")[0].trim();
  const { data: allowed } = await db.rpc("rate_limit_hit", { p_key: `webhook:${ip}`, p_max: 120, p_window_seconds: 60 });
  if (allowed === false) return json({ error: "slow down" }, 429);

  const raw = await req.text();
  if (raw.length > 200_000) return json({ error: "too large" }, 413);
  if (!(await provider.verify(req, raw, url))) return json({ error: "not verified" }, 401);

  let event: PaymentEvent | null;
  try { event = provider.parse(raw); } catch { return json({ error: "unreadable payload" }, 400); }
  if (!event) return json({ result: "ignored" });

  const { data, error } = await db.rpc("apply_payment_event", { e: event });
  if (error) {
    console.error("apply_payment_event failed", error.message);
    return json({ error: "could not apply" }, 500);   // the provider will retry; the event id keeps it single
  }
  return json({ result: data });
});

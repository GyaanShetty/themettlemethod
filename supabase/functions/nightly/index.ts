// Nightly: end memberships whose paid period has run out, fill circles, and send the flame note.
// Called by the nightly workflow with the cron secret. Never by a browser.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const env = (k: string) => Deno.env.get(k) ?? "";
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

// Encouraging, never shaming. No streak counts used against the reader, no urgency, no exclamation marks.
function note(name: string | null, daysKept: number, site: string) {
  const hello = name ? `${name.split(" ")[0]},` : "Friend,";
  const text = `${hello}\n\nYour flame is still lit. It rests after three quiet days, and it relights the day you return.\n\n` +
    `You have kept ${daysKept} ${daysKept === 1 ? "day" : "days"}. None of them are lost.\n\nOne thing, today, when you are ready: ${site}/home.html\n\n` +
    `The Mettle Method. Obey the process.\nTo stop these notes, turn off email in your settings.`;
  const html = `<div style="max-width:520px;margin:0 auto;padding:32px 16px;font:400 17px/1.6 Helvetica,Arial,sans-serif;color:#111111;background:#FAFAF7">` +
    text.split("\n\n").map((p) => `<p style="margin:0 0 16px">${p.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/\n/g, "<br>")}</p>`).join("") + `</div>`;
  return { subject: "Your flame is still lit.", text, html };
}

async function send(to: string, m: { subject: string; text: string; html: string }): Promise<boolean> {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const r = await fetch("https://api.resend.com/emails", {
        method: "POST", signal: AbortSignal.timeout(15000),
        headers: { Authorization: `Bearer ${env("RESEND_API_KEY")}`, "Content-Type": "application/json" },
        body: JSON.stringify({ from: env("EMAIL_FROM"), to, ...m }),
      });
      if (r.ok) return true;
      if (r.status < 500 && r.status !== 429) return false;
    } catch { /* retry */ }
    await new Promise((res) => setTimeout(res, 1000 * 2 ** attempt));
  }
  return false;
}

Deno.serve(async (req: Request) => {
  const secret = env("CRON_SECRET");
  if (!secret || !safeEqual(req.headers.get("x-cron-secret") ?? "", secret)) return json({ error: "not allowed" }, 401);

  const db = createClient(env("SUPABASE_URL"), env("SUPABASE_SERVICE_ROLE_KEY"), { auth: { persistSession: false } });
  const { data, error } = await db.rpc("nightly");
  if (error) return json({ error: error.message }, 500);

  const nudges: { email: string; name: string | null; days_kept: number }[] = data.nudges ?? [];
  const connected = !!env("RESEND_API_KEY") && !!env("EMAIL_FROM");
  let sent = 0;
  if (connected) {
    for (const n of nudges) if (await send(n.email, note(n.name, n.days_kept, env("SITE_URL")))) sent++;
  }
  await db.from("events").insert({ name: "external_call", props: { job: "nightly", ended: data.memberships_ended, placed: data.placed_in_circles, nudges_due: nudges.length, nudges_sent: sent } });
  return json({ memberships_ended: data.memberships_ended, placed_in_circles: data.placed_in_circles, nudges_due: nudges.length, nudges_sent: sent, email: connected ? "connected" : "not connected" });
});

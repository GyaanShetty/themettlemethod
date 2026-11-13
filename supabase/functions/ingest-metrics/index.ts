// Pulls yesterday's figures from each platform into channel_metrics, once a day.
// A platform with no secret is skipped and reported as "not connected". Called with the cron secret.
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

// One external call: 20s timeout, three tries with backoff.
async function get(url: string, headers: Record<string, string> = {}, init: RequestInit = {}): Promise<any> {
  let last = "";
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const r = await fetch(url, { ...init, headers, signal: AbortSignal.timeout(20000) });
      if (r.ok) return await r.json();
      last = `${r.status} ${(await r.text()).slice(0, 200)}`;
      if (r.status < 500 && r.status !== 429) break;
    } catch (e) { last = String(e); }
    await new Promise((res) => setTimeout(res, 1000 * 2 ** attempt));
  }
  throw new Error(last);
}

type Row = { followers?: number; reach?: number; saves?: number; shares?: number; clicks?: number; raw?: unknown };
const total = (data: any[], name: string) => data?.find((m) => m.name === name)?.total_value?.value;

const sources: Record<string, { needs: string[]; pull: () => Promise<Row> }> = {
  instagram: {
    needs: ["IG_ACCESS_TOKEN"],
    pull: async () => {
      const base = `https://graph.instagram.com/${env("IG_API_VERSION") || "v26.0"}`, t = env("IG_ACCESS_TOKEN");
      const me = await get(`${base}/me?fields=user_id,followers_count&access_token=${t}`);
      const ins = await get(`${base}/${me.user_id ?? me.id}/insights?metric=reach,saves,shares&period=day&metric_type=total_value&access_token=${t}`);
      return { followers: me.followers_count, reach: total(ins.data, "reach"), saves: total(ins.data, "saves"), shares: total(ins.data, "shares") };
    },
  },
  threads: {
    needs: ["THREADS_ACCESS_TOKEN"],
    pull: async () => {
      const t = env("THREADS_ACCESS_TOKEN");
      const ins = await get(`https://graph.threads.net/v1.0/me/threads_insights?metric=views,reposts,followers_count&access_token=${t}`);
      return { followers: total(ins.data, "followers_count"), reach: total(ins.data, "views"), shares: total(ins.data, "reposts"), raw: ins.data };
    },
  },
  youtube: {
    needs: ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"],
    pull: async () => {
      const tok = await get("https://oauth2.googleapis.com/token", { "Content-Type": "application/x-www-form-urlencoded" }, {
        method: "POST",
        body: new URLSearchParams({ client_id: env("YOUTUBE_CLIENT_ID"), client_secret: env("YOUTUBE_CLIENT_SECRET"), refresh_token: env("YOUTUBE_REFRESH_TOKEN"), grant_type: "refresh_token" }),
      });
      const ch = await get("https://www.googleapis.com/youtube/v3/channels?part=statistics&mine=true", { Authorization: `Bearer ${tok.access_token}` });
      const s = ch.items?.[0]?.statistics ?? {};
      // The upload scope gives channel totals only. Daily reach needs the analytics scope; views are stored as a running total.
      return { followers: Number(s.subscriberCount ?? 0), raw: { views_total: Number(s.viewCount ?? 0), videos: Number(s.videoCount ?? 0) } };
    },
  },
  gumroad: {
    needs: ["GUMROAD_ACCESS_TOKEN"],
    pull: async () => {
      const day = new Date(Date.now() - 864e5).toISOString().slice(0, 10);
      const r = await get(`https://api.gumroad.com/v2/sales?after=${day}&before=${day}`, { Authorization: `Bearer ${env("GUMROAD_ACCESS_TOKEN")}` });
      return { clicks: (r.sales ?? []).length, raw: { sales: (r.sales ?? []).length } };
    },
  },
};

Deno.serve(async (req: Request) => {
  const secret = env("CRON_SECRET");
  if (!secret || !safeEqual(req.headers.get("x-cron-secret") ?? "", secret)) return json({ error: "not allowed" }, 401);
  const db = createClient(env("SUPABASE_URL"), env("SUPABASE_SERVICE_ROLE_KEY"), { auth: { persistSession: false } });
  const day = new Date(Date.now() - 864e5).toISOString().slice(0, 10);
  const out: Record<string, string> = {};
  for (const [channel, src] of Object.entries(sources)) {
    if (src.needs.some((k) => !env(k))) { out[channel] = "not connected"; continue; }
    try {
      const row = await src.pull();
      const { error } = await db.from("channel_metrics").upsert({ channel, day, ...row, raw: row.raw ?? {} }, { onConflict: "channel,day" });
      out[channel] = error ? `failed: ${error.message}` : "ok";
    } catch (e) { out[channel] = `failed: ${String(e).slice(0, 200)}`; }
  }
  await db.from("events").insert({ name: "external_call", props: { job: "ingest-metrics", ...out } });
  return json({ day, ...out });
});

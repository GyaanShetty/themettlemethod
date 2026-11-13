// Places Inner Order members who have no circle into circles of five, by house then timezone.
// Called by the nightly workflow with the cron secret, or by an admin from the War Room.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const env = (k: string) => Deno.env.get(k) ?? "";
const cors = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "authorization, content-type, apikey, x-client-info" };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...cors } });

function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: cors });
  if (req.method !== "POST") return json({ error: "POST only" }, 405);
  const db = createClient(env("SUPABASE_URL"), env("SUPABASE_SERVICE_ROLE_KEY"), { auth: { persistSession: false } });

  const secret = env("CRON_SECRET");
  let allowed = !!secret && safeEqual(req.headers.get("x-cron-secret") ?? "", secret);
  if (!allowed) {
    // Signed in is not enough: the caller must be in the admins table.
    const token = (req.headers.get("authorization") ?? "").replace(/^Bearer /, "");
    const { data: who } = await db.auth.getUser(token);
    if (who?.user) {
      const { data: row } = await db.from("admins").select("user_id").eq("user_id", who.user.id).maybeSingle();
      allowed = !!row;
    }
  }
  if (!allowed) return json({ error: "not allowed" }, 401);

  const { data, error } = await db.rpc("assign_circles");
  if (error) return json({ error: error.message }, 500);
  return json({ placed: data });
});

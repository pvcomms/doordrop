import { get as ecGet } from "@vercel/edge-config";

export const config = { runtime: "edge" };

const EC_ID = process.env.EDGE_CONFIG_ID ?? "";
const KEY = "latest";

function unauthorized() {
  return new Response(JSON.stringify({ error: "unauthorized" }), {
    status: 401,
    headers: { "content-type": "application/json" },
  });
}

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function checkAuth(req: Request): boolean {
  const auth = req.headers.get("authorization") ?? "";
  const token = auth.replace(/^Bearer\s+/i, "");
  return !!process.env.OTP_TOKEN && token === process.env.OTP_TOKEN;
}

export default async function handler(req: Request) {
  if (!checkAuth(req)) return unauthorized();

  if (req.method === "GET") {
    const entry = (await ecGet(KEY)) as {
      otp: string;
      label: string;
      ts: number;
    } | null;
    return json(entry ?? { otp: "", label: "", ts: 0 });
  }

  if (req.method === "POST") {
    const body = (await req.json().catch(() => ({}))) as {
      otp?: string;
      label?: string;
    };
    const otp = (body.otp ?? "").trim();
    if (!otp) return json({ error: "missing otp" }, 400);

    const entry = { otp, label: (body.label ?? "").trim(), ts: Date.now() };

    // Write to Edge Config via Management API
    const vercelToken = process.env.VERCEL_API_TOKEN;
    if (!vercelToken) return json({ error: "VERCEL_API_TOKEN not set" }, 500);

    const patch = await fetch(
      `https://api.vercel.com/v1/edge-config/${EC_ID}/items`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${vercelToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          items: [{ operation: "upsert", key: KEY, value: entry }],
        }),
      },
    );
    if (!patch.ok) {
      const err = await patch.text();
      return json({ error: "edge config write failed", detail: err }, 502);
    }

    return json({ ok: true, entry });
  }

  return json({ error: "method not allowed" }, 405);
}

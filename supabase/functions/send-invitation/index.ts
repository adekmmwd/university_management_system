// Supabase Edge Function: send-invitation
// Sends a branded welcome email with a one-time "Set Password" link.
// Secrets (Supabase):
// - GMAIL_USER
// - GMAIL_APP_PASSWORD
// - APP_BASE_URL
// - INVITE_FUNCTION_SECRET

import nodemailer from "npm:nodemailer@6.9.15";

function requiredEnv(name: string): string {
  const value = Deno.env.get(name);
  if (!value) throw new Error(`Missing required env: ${name}`);
  return value;
}

function stripTrailingSlash(url: string): string {
  return url.endsWith("/") ? url.slice(0, -1) : url;
}

function escapeHtml(input: string): string {
  return input
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function buildEmailHtml(params: {
  recipientName: string;
  inviteUrl: string;
  logoUrl: string;
}): string {
  // Tailwind theme equivalents used in the current dashboard:
  // slate-900: #0f172a, amber-500: #f59e0b, slate-50: #f8fafc, slate-800: #1e293b, slate-200: #e2e8f0
  const fontStack =
    "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, 'Apple Color Emoji', 'Segoe UI Emoji'";

  const name = escapeHtml(params.recipientName || "there");

  return `
  <div style="background:#f8fafc;padding:24px;font-family:${fontStack};color:#1e293b;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:640px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;">
      <tr>
        <td style="background:#0f172a;padding:18px 20px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="vertical-align:middle;">
                <img src="${params.logoUrl}" alt="University logo" width="40" height="40" style="display:inline-block;vertical-align:middle;border-radius:8px;" />
                <span style="display:inline-block;vertical-align:middle;margin-left:10px;font-weight:800;font-size:18px;color:#f59e0b;">UniManage</span>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      <tr>
        <td style="padding:22px 20px;">
          <h1 style="margin:0 0 8px 0;font-size:20px;line-height:1.2;color:#0f172a;">Welcome, ${name}</h1>
          <p style="margin:0 0 16px 0;font-size:14px;line-height:1.5;color:#1e293b;">
            Your UniManage account invitation is ready. Click the button below to set your password.
            This link expires in <strong>48 hours</strong> and can only be used once.
          </p>

          <div style="margin:22px 0;">
            <a href="${params.inviteUrl}" style="display:inline-block;background:#f59e0b;color:#0f172a;text-decoration:none;font-weight:800;font-size:14px;padding:12px 16px;border-radius:10px;">
              Set Password
            </a>
          </div>

          <p style="margin:0;font-size:12px;line-height:1.5;color:#475569;">
            If you did not expect this email, you can ignore it.
          </p>
        </td>
      </tr>
    </table>
  </div>
  `;
}

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    const expectedSecret = requiredEnv("INVITE_FUNCTION_SECRET");
    const providedSecret = req.headers.get("x-invite-secret") || "";
    if (providedSecret !== expectedSecret) {
      return new Response("Unauthorized", { status: 401 });
    }

    const body = await req.json().catch(() => ({}));
    const email = typeof body.email === "string" ? body.email.trim() : "";
    const recipientName = typeof body.name === "string" ? body.name.trim() : "";
    const token = typeof body.token === "string" ? body.token.trim() : "";

    if (!email || !token) {
      return new Response(JSON.stringify({ error: "Missing email or token" }), {
        status: 400,
        headers: { "content-type": "application/json" },
      });
    }

    const baseUrl = stripTrailingSlash(requiredEnv("APP_BASE_URL"));
    const inviteUrl = `${baseUrl}/auth/set-password?token=${encodeURIComponent(token)}`;
    const logoUrl = `${baseUrl}/static/img/logo.png`;

    const gmailUser = requiredEnv("GMAIL_USER");
    const gmailPass = requiredEnv("GMAIL_APP_PASSWORD");

    const transporter = nodemailer.createTransport({
      host: "smtp.gmail.com",
      port: 465,
      secure: true,
      auth: {
        user: gmailUser,
        pass: gmailPass,
      },
    });

    await transporter.sendMail({
      from: `UniManage <${gmailUser}>`,
      to: email,
      subject: "Welcome to UniManage — Set your password",
      html: buildEmailHtml({ recipientName, inviteUrl, logoUrl }),
    });

    return new Response(JSON.stringify({ queued: true }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return new Response(JSON.stringify({ error: message }), {
      status: 500,
      headers: { "content-type": "application/json" },
    });
  }
});

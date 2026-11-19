# Account setup

Public sign-up is supplied by Supabase's free authentication service, not an ephemeral SQLite file or a fake form. The integration is disabled until a real project is configured.

1. Create a free Supabase project in your own account.
2. Copy the Project URL and **publishable key** (or legacy **anon** key) from Project Settings → API. Never use a `service_role` or `sb_secret_` key here.
3. Set these backend environment variables without replacing existing variables:
   - `SUPABASE_URL=https://your-project.supabase.co`
   - `SUPABASE_PUBLISHABLE_KEY=sb_publishable_...` (or `SUPABASE_ANON_KEY` for a legacy anon key).
4. In Supabase Authentication → URL Configuration, use `https://folio-pdf-editor.onrender.com` as the Site URL and allow that origin as a redirect URL. Add your local development origin separately if testing locally.
5. Enable email/password authentication and choose email-confirmation and password policies. The UI requires at least 12 characters; configure the project's minimum length to 12 as well. Supabase's default email sender has rate limits; review its current limits before inviting many users.
6. Redeploy the backend. The sign-in page then offers real public account creation.

Users provide **display name, email address, password and password confirmation**. If email confirmation is enabled, they confirm their email before signing in. Login sessions are managed by the official SDK; the server independently verifies access tokens and restricts PDF sessions to their owner. Account requests go to Supabase. PDFs and their processing remain on the PDF backend.

Existing `FOLIO_PREVIEW_PASSWORD` credentials remain available for private workspace access while public accounts are not configured. The username stays `folio`, and the password is unchanged. The normal web form replaces the browser's native password dialog, with optional 30-day remembered sign-in. Do not remove authentication merely to hide a password prompt.

No project was invented or provisioned on the user's behalf, and no live public sign-up is claimed before the real URL/key have been supplied. The project URL and publishable key are public client configuration; the database password and service-role key are neither required nor requested.

Render's free web service can still show its provider wake-up screen before serving any app HTML. Changing app authentication or adding an animation cannot remove that provider behavior. A separately hosted static frontend can avoid that landing-page screen, but the processing backend may still need to wake up; it requires a separate origin/proxy configuration.

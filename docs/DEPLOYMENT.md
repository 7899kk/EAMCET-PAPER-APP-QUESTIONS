# Deployment and actual costs

## Reliable zero-budget option

Run on your existing computer with `./start.sh`, then use `http://127.0.0.1:8000`. There is no API fee, paid subscription, or hosting bill. Hardware, electricity, storage, and internet still have their ordinary costs. Tesseract and all required app dependencies can be installed for free.

The build serves its own PDF.js worker, standard fonts, character maps, and WASM assets. There are no runtime CDN, web font, or analytics dependencies. Installation needs package downloads; document processing does not need internet access.

## Why this is not deployed as a static Site

This app needs native Python PDF libraries and the Tesseract executable. A static host or a JavaScript edge Worker cannot run this backend as supplied. Publishing just the frontend would not deliver a working editor. No static-only deployment is represented as a complete PDF service.

## Other hosting

You may host the **frontend** on a free static tier, but it still requires a running Python backend. Cross-origin API deployment needs an explicitly configured allowed-origin policy and authenticated HTTPS API; the supplied application intentionally uses one same-origin server. The simplest deployment is a single Linux host that serves both frontend and backend.

A VM or container provider's free allowance may support light testing, but CPU, RAM, request duration, sleep policies, package storage, and egress limits often exclude reliable OCR and larger PDFs. There is no guaranteed always-free public server recommendation here. Check the provider's current plan and billing controls yourself; no paid provider account has been created and no deployment has been made.

Before a public deployment, add authenticated access, per-user quotas/rate limits, native-parser process isolation and hard CPU/memory/time limits, queue long jobs, configure HTTPS and trusted proxy/host headers, and monitor errors without logging document bodies or session tokens. The current app is meant for a trusted local user, not a hardened multi-tenant internet service. Keep one worker or redesign the in-memory session store before scaling.

Expose only the application through a reverse proxy. Do not expose a development Vite server. Do not use wildcard CORS. Preserve same-origin `Origin` checks; account for the reverse proxy's forwarded scheme correctly. Keep the backend's loopback binding when proxying locally.

## Licensing when hosted

The application uses an AGPL PDF engine and the app source is offered under AGPL-3.0-or-later. Supply the corresponding source, build/run instructions, licence text, and third-party notices to network users. Keep OFL fonts under their own font licence and keep PDF.js's distinct asset notices. Do not represent Stirling's current engine as MIT: see the separate licence audit.

## Prepared Render free-tier testing deployment

The project now includes a multi-stage `Dockerfile`, `render.yaml`, and `serve.py`. Docker builds the real React app and runs the Python PDF backend plus Tesseract together on one origin. The blueprint explicitly requests `plan: free` and one instance; it provisions no database or paid disk. No external deployment has been made until a connected Render account returns a successful deployment and its URL.

Connect Render in ChatGPT to let the agent deploy the project to your account. Do not paste provider API keys in chat. If Render needs a Git source repository, a repository must also be made available to that account before deployment. The existing connected GitHub tools can be used if repository creation/source upload is supported and authorized.

Render supports a free testing web service, but it sleeps after 15 minutes without inbound traffic. Waking can take about a minute. Sleeping/restarting clears this app's in-memory PDF sessions: download your edits first. The documented free tier has 512 MB RAM / 0.1 CPU; use small PDFs for initial testing. Heavy OCR may be too slow or exceed memory. Free hours, build minutes, and bandwidth have account-wide quotas. Keep supplementary spending disabled; do not switch to a paid compute plan to finish deployment. Check the provider's dashboard for any account-specific requirements.

The blueprint generates `FOLIO_PREVIEW_PASSWORD` for a private testing login. Browser username: `folio`; obtain the generated password from **your Render service's Environment settings**. Do not commit it to source or put it in the URL. All app/PDF routes require that login when configured; `/api/health` remains accessible for the host's health check. Local runs without the environment variable keep their previous behavior. Render's trusted `RENDER_EXTERNAL_URL` defines the expected browser origin so HTTPS-proxied edits pass the same-origin check. An authenticated download of corresponding source is available at `/source.zip` in Docker deployments.

Hosted uploads travel to Render for processing; they are no longer processed on your personal computer. The app still sends no documents to an external PDF-processing API. This is a password-protected single-user testing deployment, not a hardened multi-tenant public PDF service.

To build locally:

```bash
docker build -t folio-pdf .
docker run --rm -p 10000:10000 folio-pdf
```

Open `http://localhost:10000`. To enable password protection locally, pass a secret via your environment using Docker's `-e FOLIO_PREVIEW_PASSWORD` option. The image runs as an unprivileged user and writes only transient OCR data under `/tmp`.

### Browser login compatibility

The hosted password gate now sets a signed one-hour browser cookie after successful login. It is HTTP-only, SameSite=Strict, and Secure on HTTPS. It is invalid after changing the preview password. Basic authentication remains supported for API clients. API URLs are resolved against the clean origin, so opening a URL containing login credentials does not prevent PDF upload. The configured Render password is unchanged by this fix.

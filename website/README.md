# raute+kopf website

Static coming-soon page. Edit
`public/index.html` and `public/style.css`; the logo is `public/logo.jpg`.
No JavaScript, dependency installation, database, or volume is required.

## Hosting

Served by Caddy on the RauteOS server (Hetzner), straight from `public/`: see
the `{$WEBSITE_HOSTS}` block in `deploy/caddy/Caddyfile` and the read-only mount
in `deploy/compose.yml`. A push to `main` deploys it together with RauteOS.
Caddy also forwards `/onboarding` to the app, for the customer questionnaire.

DNS is managed by STRATO: `raute-kopf.com` and `www.raute-kopf.com` point at the
server's IP. Preserve the existing mail records when changing DNS.

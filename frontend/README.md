# RauteOS frontend

React renders the Desk, Twin and journalist pages inside the existing FastAPI/Jinja shell. The
sidebar, authentication, language cookie, Ask RAUTE and navigation remain owned
by the server. All requests use the same origin.

Use Node 22.22.3 (the version in CI and Docker):

```sh
cd frontend
npm ci
npm run build
npm test
```

Start the Python app as described in `newspulse/README.md`, then open `/desk`.
`npm run dev` watches and rebuilds assets; refresh the browser after a build.
This deliberately uses FastAPI's real session and static serving during local
development, so there is no second port, CORS configuration or auth proxy.

Vite writes hashed assets and `.vite/manifest.json` into
`newspulse/src/newspulse/web/static/react/`. The directory is ignored by git;
Docker builds it in a Node stage before copying it into the Python package.
For wheel distribution, build the frontend before `uv build`.

The JSON contract is `GET /api/v1/desk`, documented by FastAPI at `/docs` and
`/openapi.json`. Change `web/routes/desk_api.py` and its API tests before changing
what components consume. UI lives in `src/components/`; domain calculations stay
in Python. Page translations use the existing server translator and the small
`web/desk_labels.json` key list. Never place secrets in Vite environment variables.

The classic page is always at `/desk?view=classic`. If no frontend has been built,
`/desk` serves it automatically. Bundle failures and API errors expose a link to
that page. Logging an off-tool action uses the original `POST /desk/action`
form and redirects back to the Desk so delivery counts reload from the server.

The Twin is the second React page, at `/client/{id}/twin`. Run
`uv run alembic upgrade head` from `newspulse/` before starting it. It consumes
`/api/v1/clients/{id}/twin` and its statement/import endpoints. The catalogue in
`newspulse/twin_catalog.json` contains questionnaire definitions, not client data.
Old profile, kickoff and guide tools remain linked from the Twin.

The journalist workspace is at `/journalists`. It uses the existing contact book
plus persistent topics, preferences and relationships. From an opportunity, the
research link includes its client, kind and ID. Only an explicit POST starts
provider calls; GET reads the latest dated result. Research metadata is separate
from coverage. Failed or unconfigured providers remain visible in the result.
Run migration `0059_journalist_intelligence` before using this page.

The opportunity list and workspace are at `/client/{id}/opportunities`.
`?kind=detected&context={newsjack_id}` or `?kind=developed&context={angle_id}` opens
one opportunity. Development and activation require explicit POSTs. A GET never
creates an angle or starts a model/provider call. Migration
`0060_opportunity_workspace` stores research attempts, selections and activity;
activity does not count as delivered work on the Desk.

The opportunity activation panel defaults to a customer email and offers ten
formats. Migration `0061_opportunity_assets` is required. Draft and check jobs
run only after explicit requests; sentence evidence links, warnings and stale
checks remain visible beside editable text. Existing pitch approval and sending
are linked from the saved pitch. Draft activity does not increase Desk delivery
counts.

The primary React destinations are `/desk`, `/clients`, `/assets`, `/ask`,
`/client/{id}/overview`, `/client/{id}/actions`, `/client/{id}/opportunities` and
`/client/{id}/twin`. Clients retains `/clients?view=classic` as a fallback.
Ask uses the existing SSE endpoint with explicit global/client/opportunity/asset
context, separate browser-session threads and read-only suggestions. The header
and saved text links supply context; no model request runs just by opening a page.

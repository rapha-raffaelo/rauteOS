# RauteOS frontend

React owns the shared sidebar, top bar and client navigation, plus Desk,
Clients, Assets, Ask RAUTE, Opportunities, Contacts, both archives, Settings, the new-client form and
the complete client Profile (statements, company facts, guide, kickoff,
competition and market signals). FastAPI retains authentication, validation,
data access, integrations and jobs. Jinja hosts the HTML document and safe JSON
bootstrap only for these migrated pages; it does not render their UI bodies.
Older specialist screens such as KI visibility, editorial planning and coverage
maps still render their page bodies on the server, inside the React navigation.
All requests use the same origin.

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
The complete profile is one React page. Legacy profile, kickoff and guide URLs
resolve to the same workspace; no profile submenu is needed.

The contact workspace is at `/contacts`; `/journalists` redirects there. It uses the existing contact book
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

## Shared shell and migrated pages

`src/shell.jsx` renders navigation from `react-shell-data` and client tabs from
`react-tabs-data`. `src/platform/` owns Archive, Settings and Profile components.
`web/react_pages.py` builds allowlisted JSON view models; it never serializes
arbitrary ORM columns, session objects or credentials. Page GETs also accept
`Accept: application/json`, with `Cache-Control: no-store` and `Vary: Accept`.
Existing POST endpoints remain the single validation and persistence layer.
Import preview and kickoff saves consume JSON; kickoff saves update one answer
without replacing other draft inputs. React polls active settings/research jobs.

Build the frontend before starting the application. The migrated pages require
the bundle; Python-only development can still exercise their JSON contracts.

Python UI tests use `tests/react_render.py` to render the actual React components
with React's static renderer. They do not reconstruct the retired Jinja markup.
The helper creates an ignored `frontend/.test-render/` bundle and requires Node
and `npm ci`, just like the production build. Vitest covers interactive behavior;
browser checks cover real form submissions and responsive layout.

## Customer onboarding

The separate `/onboarding#<personal-token>` React page targets a five-minute CEO
onboarding: one public company summary to confirm or correct, followed by five
questions from `RAUTE_OS_INPUT-Master.xlsx` about ambition, positioning, boldness,
market beliefs and confidential plans. Stable field IDs and copy live in
`newspulse/customer_onboarding.py`. Public information is not asked again.

Apply migrations through `0064_onboarding_workflow` before serving the updated
Profile. Creating a customer starts preparation automatically; existing customers
can start it in **Profile → Kunden-Onboarding**. The worker uses the configured
grounded web-research provider and stores sourced findings before creating a link. Explicitly public, sourced existing statements can supplement the snapshot.
If research fails, the agency sees a warning; an empty snapshot blocks link
creation. Missing public facts remain research tasks for the agency. No provider
call happens when a customer opens the link. Internal notes and CEO answers are
never used as public prefills. Each prefill includes its source and research date.

Links expire after 14 days and can be revoked from Profile. Only hashes are
stored; the token remains in the URL fragment and travels in a scoped request
header. Customers see only the prepared public snapshot and their link's answers.
Confirming the summary records the review; corrections are saved as separate
customer statements without overwriting public research evidence.

Each **Speichern & weiter** writes directly to the customer's Twin statements,
attributed to customer onboarding, confidential and requiring external approval.
Confidential strategic plans are restricted to internal use. Existing agency
facts are preserved. Skipped questions are distinct from answers; review and
completion resume from the database. No audio is stored: the browser's speech
service transcribes into editable text, with a disclosure before activation and
typing fallback. Use HTTPS in production. Failed saves retain the current input.
The five-minute duration is a design target, not a measured CEO usability result.

### Automatic Railway workflow

Creating a mandate at `/mandant/neu` persists company details, the contact and a
queued job in one transaction, then opens **Profile → Kunden-Onboarding**.
The web process starts the durable worker independently of the daily scheduler.
The crawler respects robots.txt, public-network restrictions, page/byte limits
and omits news/article paths. Grounded research processes the public A/D workbook
fields in batches. It never guesses private CEO answers or RAUTE hypotheses.
Each accepted answer must cite a crawled or provider-returned source. Raw crawl
excerpts stay in the private job checkpoint; the customer sees a sourced snapshot.

Migration `0064_onboarding_workflow` adds contact fields and the durable job table.
Completed batches and their facts commit together. Expired worker leases can be
reclaimed after a restart; stale workers cannot publish. Failed jobs are resumed
from Profile. No existing customer is automatically re-researched on deployment.

A ready job creates its 14-day customer link automatically. The authenticated
agency view can retrieve/copy the same link after reload, see answer progress and
completion, revoke links and renew expired ones while retaining customer answers.
No email is sent automatically. Contact details can be edited in the same panel.

The link signing key is generated with mode 0600 beside the SQLite database
(`/data/.onboarding-link-key` on Railway). Preserve it with the database during
volume moves/restores; redeploys retain it on the existing `/data` volume. Only
token hashes are stored in invite rows. Browser links carry the token in their
fragment and use a scoped header for the customer API. Agency routes retain the
existing Google allowlist authentication. Do not copy production keys into Git.

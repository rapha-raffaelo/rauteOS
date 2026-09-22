# Railway production release — 10 September 2026

Deployed application commit: `5ffe8eddf116accacb63632f7a76f8b0473e904f`.
Railway deployment: `73dba4ad-ae0a-460d-9066-f1125773df89` — **SUCCESS**.
Service: `pr-scanner`, production.
URL: https://pr-scanner-production.up.railway.app/desk

The release was uploaded from a clean `git archive` of the tested commit.
No local secrets, databases, demo data or dependencies were included. This was a
manual Railway deployment from `codex/react-desk`; GitHub `main` remains at
`c8bd17e`. The service's GitHub source configuration was not changed. Future
Git-based releases need to include these commits and the new migrations.

## Verification

- 3,216 Python tests, 28 React tests and the production frontend build passed.
- Browser checks confirmed developed opportunities in Desk counts and activation
  history on Actions, with no increase in contractual delivery totals.
- Production SQLite online backup:
  `/data/backups/pre-react-20260910T205428Z.sqlite` (9,011,200 bytes).
- Rehearsal on a separate database copy passed before deployment.
- Production migrations completed from `0057_fact_evidence` to
  `0061_opportunity_assets`; SQLite quick check returned `ok`.
- Existing counts were preserved: 12 clients, 94 Twin statements, 3,800 articles,
  3,421 analyses, 1 asset, 4 outreach records and 1 contact.
- All five React entries resolved; all 12 public JS/CSS assets returned HTTP 200.
- Deployed source hashes matched the tested release files.
- Read-only production checks validated Desk, Clients and Assets and all seven
  active client read models. Clients, Assets, Ask, Overview and Actions rendered
  HTTP 200 with React mounts in an internal route check.
- Public unauthenticated workspace/API requests remained protected (HTTP 401);
  the login page and static assets were available.
- The deployed `invoke_with_fallback` returned the expected live response for a
  synthetic verification prompt. No model-generated client record was saved.

No customer emails, approvals or external messages were sent. The broader visual
layout differences from Lucas's PDF remain in `26-lucas-verification.md`; the
Desk-count and Actions-history functional findings are resolved in this release.

## Ask RAUTE and visual refinement release — 2026-09-11

Deployed source commit `0196dcf` from a clean git archive to the same production
service. Railway deployment `dd84ee29-01cf-4345-ae24-b82a921d767b` reached SUCCESS.
Ask RAUTE is absent from the global sidebar and remains in the top-right header;
the Captain drawer and avatar are removed. This release also includes the
workspace/Desk/journalist/evidence layout refinements recorded in the Lucas audit.

Post-deployment read-only checks confirmed five rendered React pages with one
header Ask entry, no sidebar Ask entry and no Captain drawer. All seven active
client read models passed. Fourteen public asset/auth checks passed; source
hashes matched the reviewed release. SQLite quick_check is ok, schema unchanged
at 0061. Clients (12), statements (94), assets (1), outreach (4) and contacts (1)
remain present; the ongoing news collection has 3,867 articles / 3,472 analyses.
No customer messages or release approvals were issued by this verification.

### Navigation fix — 2026-09-11

Source `d8703b9` deployed as `2cc8f393-c2d2-433e-9eda-340fe291bf09`
(SUCCESS). Four primary client tabs, a separate specialist-tool grid, no Ask or
Develop duplicates in the client menu, and corrected mobile top-bar height.
Read-only production render checks passed; public stylesheet and server source
match the reviewed release. Database integrity remains ok, schema unchanged.

### Client overview dashboard — 2026-09-12

Source `ca5c717` deployed as `d4572910-6d37-4e65-9624-9759faefe243`
(SUCCESS). New metric cards, opportunity cards, Twin rail, recent activity and
text empty state replace the bare overview list. Live workbench JS/CSS contain
the new dashboard component and layout. Read-only production renders passed;
database integrity remains ok and schema is unchanged.

### Reviewed AI Twin import — 2026-09-12

Source `bf3996c` deployed as `96feda25-79e0-43c4-b1ba-630e2994ea2b`
(SUCCESS). Public Twin bundle contains the AI import control and routes. Deployed
backend hashes match; read-only AI status requests work for all seven active
mandates and grounded web research is configured. Database integrity is ok;
no migration or production answer generation/commit was performed for the smoke
check. The new workflow was exercised with synthetic data before deployment.

### Simplified primary controls — 2026-09-12

Source `6de080b` deployed as `ea411dc2-2a48-4da0-bbca-17b7dfed287e`
(SUCCESS). Duplicate navigation/actions removed, secondary controls grouped, and
React pages use a single header. Read-only production renders confirm one header
Ask entry and no secondary toolbar across five workbench pages; source hashes and
public Twin bundle match. Database integrity remains ok. No production content
was modified during verification.

### Legacy control consolidation — 2026-09-12

Source `89be4cb` deployed as `a6c849fa-00b5-490c-9c0a-64bf3993b8d6`
(SUCCESS). Manual collection is consolidated in Settings; legacy profile duplicate
and all-client controls are removed. Language access is consistent across pages.
Post-deployment read-only checks passed for seven active clients and five rendered
workbench pages. All checked backend/template hashes and public CSS match the
reviewed source. Database integrity is ok and schema remains
`0061_opportunity_assets`; no production content was changed for verification.

### Focused workspace controls — 2026-09-12

Source `cbcf8db` deployed as `aff13029-7670-4026-b5a1-ca853e2429ad`
(SUCCESS). Desk duplicate task rail removed; saved-text and opportunity selectors
appear only when useful. Text titles lead directly to their editor. All 12 public
JS/CSS files match the reviewed build. Read-only checks passed for seven active
clients and five workbench pages; backend hashes match and database integrity is
ok. Schema unchanged; no production content mutations for verification.

### Consolidated mandate navigation — 2026-09-12

Source `0215df1` deployed as `2997ba61-770d-4e4b-9af4-2e33229a80e3`
(SUCCESS). Six primary tabs replace the separate tool menu. Opportunities and
Profil own their related views; Archiv and KI-Sichtbarkeit are primary tabs.
Production renders verify the six labels, group selector and active parent on
both workspaces. All 12 public built JS/CSS files, shared stylesheet and checked
backend/template hashes match. Seven active clients remain readable; database
integrity is ok and schema is unchanged. No production content mutations were
performed during verification.

### AI import parsing correction — 2026-09-14

Source `2ab03db` deployed as `add74c52-d715-4366-bf35-812ee4ccf74b`
(SUCCESS). Handles a complete JSON code block followed by model commentary,
with safe diagnostic errors and explicit retry. The deployed parser passes the
exact response-format regression probe. All 12 public frontend JS/CSS files and
checked backend hashes match the reviewed release. Read-only checks passed for
seven active clients; database integrity is ok and schema is unchanged. Production
facts and import previews were not modified for verification. A live-provider
probe on an isolated in-memory copy completed with 14 proposals before release.

### Remove Heute selector entry — 2026-09-14

Source `73faf5d` deployed as `2490687e-9020-4b46-bbce-bc28cf3e2d85`
(SUCCESS). Production Opportunities rendering confirms no Heute option; deployed
navigation template hash matches the reviewed source. Database integrity is ok.

### Unified profile without submenus — 2026-09-14

Source `3d61fa0` deployed as `97ab7c8d-c48d-48c0-9361-1f8ad9754fac`
(SUCCESS). All seven active mandates render the four profile sections without a
profile view selector. The six primary tabs remain; Opportunities still omits
Heute. Five workbench pages and import-status reads remain healthy. All 12 public
frontend files, the shared stylesheet and 26 checked server source/template hashes
match the reviewed release. Database integrity is ok; schema remains
`0061_opportunity_assets`. Verification used read-only database access and did not
alter production content.

### Single Kontakte entry — 2026-09-14

Source `7a9970c` deployed as `ce03a83d-fe52-494e-8cc9-fd7e75a82e62`
(SUCCESS). Production renders confirm the Contacts React workspace under
/contacts, title Kontakte, exactly one active Kontakte sidebar entry and no
Journalisten sidebar link. All 12 public frontend files, shared stylesheet and
31 checked server source/template hashes match. Seven unified profiles and five
workbench pages remain healthy; database integrity is ok. No schema changes or
production content mutations were performed for verification.

### Client card edit/delete actions — 2026-09-14

Source `b885189` deployed as `a7f88e36-8047-4b79-a50a-67be0c168ed6`
(SUCCESS). Read-only production checks confirm settings are readable for all
seven active clients, existing profile/workbench pages remain healthy and database
integrity is ok. All 13 public frontend files, the shared stylesheet and 31 checked
server source/template hashes match the reviewed build. Editing and confirmed soft
deletion were verified in isolated local/browser tests; no production client was
edited or removed during verification. Schema unchanged.

### Unified visual system — 2026-09-14

Source `e5b2c6b` deployed as `5e208c53-175b-4612-a2db-61c96bb9ac78`
(SUCCESS). All 13 public frontend files, both shared stylesheets and 32 checked
server source/template hashes match the reviewed release. Production renders
include the fingerprinted studio stylesheet and accessible mobile navigation.
Seven client profiles/settings, Contacts and five workbench pages remain healthy;
database integrity is ok. Frontend architecture remains hybrid React/Jinja.
No production content was changed for verification.

### Refined assistant, profile and opportunity workspaces — 2026-09-14

Source `ea685e9` deployed as `f4524de1-59e1-4ab5-940d-7dfeb55497c9`
(SUCCESS). All 13 public frontend files, both shared stylesheets and 32 checked
server source/template hashes match. Read-only production checks passed for seven
client profiles/settings, Contacts and five workbench pages. Database integrity
is ok. This is a React presentation refinement within the existing hybrid app;
no production content was changed for verification.


### React navigation, archives, settings and complete profile — 2026-09-18

Source `e5147b3` deployed from a clean git archive as
`b9a37a04-5562-4dcb-8580-3007b6e608c9` (SUCCESS). React owns shared navigation,
both archives, settings, the new-client form and the complete unified profile.
Python retains backend jobs and persistence; specialist legacy page bodies remain
Jinja inside React navigation.

Read-only production verification passed for 17 HTML pages and 17 JSON contracts,
including archives/profiles for all seven active mandates, settings and new-client
creation view. Seven bundle entries are available. All 19 public JS/CSS files,
both shared stylesheets and ten checked server source/template hashes match the
reviewed source/build. The navigation roster matches active mandates. SQLite
integrity is ok and schema remains `0061_opportunity_assets`. Verification used
query-only database access and did not mutate production client data.

### Default press release and custom message composer — 2026-09-18

Source `400f256` deployed from a clean git archive as
`07aa2add-25f5-4be4-ab55-9f6e0ba8bdbe` (SUCCESS). Content now starts with the
press release, with a React custom-message composer below it. Preset instructions
are editable; explicit submission streams the draft and actual word count before
saving and checking. New impulse/development jobs attempt their default press
release without replacing an existing text or automatically releasing/sending it.

All 21 public JavaScript/CSS files and both shared stylesheets match the reviewed
build. Read-only production checks passed for all seven active client content
pages, default-format selection and 12 source/template hashes. The new composer
POST endpoint is registered in the production OpenAPI contract. SQLite integrity
is ok, schema remains `0061_opportunity_assets`, and asset counts were unchanged
by verification.

A synthetic production provider probe with no client data returned 11 text events
and one successful completion. The partial-JSON preview decoded the expected
58-character test body. No message was stored, released or sent by this probe.
Local browser checks covered incremental previews, completion, persistent draft
editing, unchanged press releases and responsive layout at 1440px and 390px.

### Automatic preparation and distinct analysis/message areas — 2026-09-18

Source `bf398b3` deployed from a clean git archive as
`f72828ef-1220-4f1a-8e23-e974c9de7b7c` (SUCCESS). Existing impulses now request a
missing default press release automatically when opened, with progress and inline
completion. Existing drafts remain intact. Analysis and messages have distinct
backgrounds, headings and document styling on desktop and mobile.

Read-only production verification passed for all seven active client views,
including the analysis/message separation and both preparation API methods.
All seven latest impulses were eligible for automatic preparation; this check
only read their status and did not generate or change client content. All 21
public JS/CSS files, both shared stylesheets and 12 server source/template hashes
match the reviewed build. SQLite integrity is ok, schema remains
`0061_opportunity_assets`, and the asset count was unchanged by verification.
Local validation passed 83 backend and 51 frontend tests plus the automatic
preparation/editing browser flow at 1440px and 390px.

### Batched AI import and shared design refinement — 2026-09-18

Source `a8d0a4b` deployed successfully as
`6111fe28-af7d-4d8a-bd8d-d21c84170d5a`. Final source `19f0fb5`, including removal
of the conflicting profile-section CSS reset, deployed from a clean archive as
`57878ae7-58ed-41ec-a621-be82d74bb707` (SUCCESS).

The formerly failing Arrakis.finance import completed against the actual
production providers in 360 seconds: 51 answer suggestions, web research included,
no failed batches. These remain an uncommitted review preview. After the final
restart the read-only status endpoint still returned all 51 rows, all marked
Needs Verification. ClientFact count remained 94; SQLite quick_check returned ok.
Both AI import methods are registered. Four backend/style source hashes, all 21
public bundle files and both shared stylesheets match the reviewed checkout.

Validation passed 106 backend and 52 frontend tests plus Vite build. Desktop and
mobile browser checks covered import creation/progress/review/explicit commit on
synthetic data, clients, archive, settings, profile/kickoff, overview and
opportunities. Themed company/competition/market surfaces were checked after
removing the older reset. No JavaScript errors or horizontal overflow were found.

### Durable background drafts and live writing output — 2026-09-19

A SQLite backup was created and quick_check-verified on the existing data volume
before migration `0062_default_drafts`. Source `95fbcc8` deployed as
`286a7518-cf80-4e94-b46c-5d6bd3a25d5b` (SUCCESS), adding the durable queue and
actual streamed preview/word count. The real first pass exposed pre-existing
speaker/dateline/quotation validation failures. Source `d349223` corrected these
and deployed as `4746f374-f7f1-4671-9e69-4d33588ba990` (SUCCESS). Eight failed jobs
were explicitly requeued once after the fix, without restarting existing drafts.

The completed production queue contains 77 ready jobs and 77 saved press releases:
76 initially visible missing impulses plus one newly generated impulse. All seven
active mandates' latest drafts are ready. No queued, running, blocked or failed
jobs remained, and released-press-release count is zero. Status responses remain
no-store and distinguish real writing progress from checks. All 23 public bundle
and shared stylesheet files matched the reviewed build; eight backend hashes and
SQLite integrity were verified.

Final source `e33ed0a` additionally excludes role-only clauses from speaker-name
matching. Final restart verification is recorded below.

Final deployment `57ea106d-159f-46b3-8e2e-ad39fdcae0cc` is SUCCESS. After the
restart, fingerprints of all 77 stored draft titles/bodies/release states matched
the pre-restart snapshot exactly. All seven latest client drafts remain ready;
the ledger contains only 77 ready jobs, with no pending/failed work or regeneration.
Migration version is `0062_default_drafts`, SQLite integrity is ok, all eight
backend hashes and all 23 public JS/CSS/shared stylesheet files match final source.

### Compact profile and opportunity writing — 2026-09-21

Source `25dd0d0` deployed from a clean git archive as
`1e7353fc-5af3-47f7-b5fe-4e03fd46bd38` (SUCCESS). Profile editing now starts with
answer and source directly at the question; company, guide, competition and
market tools remain available in contextual sections. Opportunity workspaces
show existing press releases directly and replace five inner tabs with sections.
Common text formats are one click away, while all ten formats remain available.
Client management and shared buttons use quieter secondary actions.

Validation: 57 frontend tests and the Vite build passed. The targeted
backend/navigation suite passed 124 tests; the additional profile, guide,
workbench, React contract and workspace suite passed 104 tests (workspace coverage
overlaps the first suite). Desktop/mobile Playwright interactions and ten
axe-core scans passed, with no page errors, horizontal overflow or detected
WCAG-2A/AA or WCAG-2.1-AA violations in those states. Details and comparative
measurements are recorded in `ux-assessment-2026-09-21.md`.

Read-only postdeployment checks verified 23 public bundle/style files and 11
server source hashes against the reviewed checkout, including `workspaces.py`.
All seven React entries, 17 page responses and 17 JSON contracts passed. All seven
active mandates remain present, SQLite quick_check is ok, and the schema remains
`0062_default_drafts`. Verification did not generate texts or write profile data.

### Remove empty impulse-page columns — 2026-09-22

Layout source `3f0e767` removes the reserved empty message column, lays out contact
suggestions across the available width and expands press-release display/editing
to the full content width. Contact suggestions form a responsive grid on desktop
and a single list on mobile. Existing message and release forms are unchanged.

The rebuild exposed an AI CLI engine warning: the newly installed Claude Code
requires Node >=22 while Debian provided Node 20. Final source `3772746` uses the
same Node 22.22.3 runtime as the frontend build, and smoke-checks Node and the AI
CLI during image creation. Build output verified Node v22.22.3 and Claude Code
2.1.278 successfully starting. Final clean-archive deployment
`8dc1e277-ae5f-4de0-973f-fe6c1f81b867` is SUCCESS.

Validation: 203 existing asset/outreach/ledger/navigation tests passed. Playwright
checked six synthetic states (with/without written messages, without contacts,
each at 1440px and 390px). No page errors or horizontal overflow. Empty message
containers are absent; stored messages remain visible. Drafts and contact panels
use the full available width. Six desktop contacts take two rows and about 380px
height, compared with 923px previously. Browser artifacts are in
`/tmp/raute-spacing/`; tests did not send messages or generate content.

Read-only production verification passed 24 page responses, including all seven
mandates' impulse pages, 17 JSON contracts, seven React entries, 12 source hashes
including the changed template, and 23 public bundle/style files. SQLite integrity
is ok; schema remains `0062_default_drafts`, with seven active mandates.

### Durable AI import checkpoints and recovery — 2026-09-22

The Arrakis import started at 10:08 UTC had recorded five of six attempted
packages and a suggestion counter of 46 when the earlier deployment restarted
the server. Its answers were still held in process memory. An older preview of
51 suggestions from September 18 remained in SQLite but was hidden by a one-hour
expiry. The 46 in-memory answers could not be recovered.

Source `0be6a9a`, deployed from a clean archive as
`635dac4b-47f9-494e-8c15-3f2f61949014` (SUCCESS), now saves frozen source context,
completed package answers, validated review rows and the next package index.
Each package checkpoint and its review preview are committed together. Startup
recovery rotates the generation token, resumes interrupted jobs and rejects
results from obsolete workers. Explicit resume retains the original input.
AI previews no longer expire in the review/commit API or get removed by file
import cleanup. Completed packages remain reviewable after later failures.

The profile restores import status automatically. Collapsing the panel retains
its state, and a history selector opens older saved previews. No AI suggestion
becomes a live statement without explicit selection and commit; active previews
cannot be committed while still being written. Import input/checkpoint internals
are excluded from public job responses, and imported facts retain verification
and external-use constraints.

Validation passed 60 frontend tests, 61 targeted backend/React-contract tests and
the Vite build. Tests cover interrupted/resumed packages, generation fencing,
startup recovery, expired preview recovery, cross-client scope, cleanup and
explicit review. A Playwright run against an isolated local SQLite database was
interrupted by stopping the process after two packages. Restart finished all six;
only the in-flight third package repeated. Desktop/mobile reload and panel-toggle
checks passed with no page errors or overflow. Artifacts are under
`/tmp/raute-import-*` and `/tmp/raute-browser-check/import-restart.cjs`.

Production startup automatically resumed the authorized Arrakis run using its
saved input; this older run required recalculation because it lacked checkpoints.
Read-only verification at 10:32 UTC found the first package durably saved with 18
review rows in preview `eea304a6-2e19-48e4-8cfd-909791f992c0`. The run was still
processing the remaining packages. The older 51-row preview is separately
accessible through the review API and history. ClientFact count remains 94.
All 23 public bundle/style files, 15 server hashes, 24 page responses and 17 JSON
contracts passed. SQLite integrity is ok; schema remains `0062_default_drafts`.

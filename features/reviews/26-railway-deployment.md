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

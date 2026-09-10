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

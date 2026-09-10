# PR #26 implementation review — 9 September 2026

Reviewed [PR #26](https://github.com/rapha-raffaelo/pr-scanner/pull/26), all eight
specifications and the six-phase plan against `origin/main` at `c8bd17e`.
This change implements the remaining frontend/API work in **Phase 0**. Phases
1–5 are still separate work; this is not a completed product rewrite.

## Findings that change the implementation

1. **The prerequisite PRs are merged.** #20, #22, #23, #24 and #25 are all
   merged, as is #27 (Twin evidence columns). #26 was merged into
   `claude/sidebar-groups`; its specification files are still absent from main.
   Read its source on `claude/specs` / commit `2051450`, rather than assuming
   main contains the plan. No need to reimplement the Desk domain or migration.
2. **Do not promote manual input to verified fact.** The HTML plan proposed
   that backfill. Migration `0057_fact_evidence` already corrects it: historical
   rows become External Observation / Unknown / Needs Verification, never Fact.
   Its seven fine-grained classes match the workbook vocabulary and map onto
   the four classes in the brief. Preserve them.
3. **Columns are not evidence enforcement.** `evidence_type` is currently used
   by the ORM, but not by the profile edit/research paths or downstream prompt
   assembly. New and edited statements need explicit provenance handling,
   rejection and confidentiality rules. Stored classifications alone cannot
   prevent a pitch or Ask RAUTE from using an unverified claim.
4. **Multiple statements are still a migration.** `ClientFact` retains one row
   per `(client_id, key)`. Its readers return a field-keyed profile. Changing
   uniqueness without updating those readers loses statements. Phase 1 must
   migrate the statements and their consumers together.
5. **Action means two things in the specs.** Desk contract delivery counts use
   `released_at` plus the manual ledger. Spec 08's activation history also
   includes drafts, generated customer emails and selected journalists. Keep
   the history separate from billable/delivered counts; generating an asset
   must not satisfy a contract automatically.
6. **The questionnaire is available locally now.** The original worktree has
   `RAUTE_OS_INPUT-Master.xlsx`; #27 also used its vocabulary. The plan's
   inaccessible Drive link is no longer a blocker for a subsequent importer.
   Importing client content is not part of this frontend change.
7. **Quality checking is more than reading a label.** Phase 4 still needs to
   associate asset statements with Twin evidence and sources, assess currency
   and contradictions, and enforce no-gos and external-use restrictions. The
   evidence columns supply inputs; they do not supply those checks.

8. **The opportunity workspace has a newer foundation than the plan says.**
   Main already serves `/client/{id}/gelegenheit/{opportunity_id}` through
   `opportunity_view.py`, with a dossier, source material, time window, stored
   outlook and an activation action. Reuse that domain layer in Phase 3;
   speaker selection and multiple storylines still need work.

## Delivered in this change

- `GET /api/v1/desk` with an explicit Pydantic/OpenAPI response contract. It
  uses the existing `desk.build` logic, includes derived counts and nullable
  contract status, and exposes only a small allow-listed client identity.
- The React Desk at the existing `/desk` URL. Jinja owns the shared navigation,
  login and Ask RAUTE drawer. React owns the complete Desk content. Its action
  form posts to the existing same-origin endpoint.
- A Vite build with hashed files and a manifest, bundled into the Python static
  directory. Docker and CI build the frontend. No separate frontend service,
  auth state, cross-origin proxy or deployment is necessary.
- Loading, retry and expired-session states. `?view=classic` always opens the
  former Desk. An unbuilt Python checkout automatically uses that page, and
  the initial loading markup keeps a classic link if the bundle cannot load.
- API tests for delivered-vs-draft counts, missing-vs-zero contracts, restricted
  client fields and authentication; React tests for rendering, form contract,
  timezone, errors and retries. Existing domain and classic-page tests remain.

The React integration follows the official
[Vite backend integration](https://vite.dev/guide/backend-integration.html) and
[React existing-project integration](https://react.dev/learn/add-react-to-an-existing-project)
approaches. Dependencies are locked in `frontend/package-lock.json`.

## Next implementation sequence

1. Phase 1: statement lifecycle, evidence-aware readers/prompts, multiple
   statements per profile field, workbook mapping and preview, Twin API/editor.
   Completeness must use required/optional fields, not just the current fixed
   profile/kickoff/guide weighting.
2. Phase 2: persistent journalist topics and article history; source-dated
   research per opportunity. An incomplete archive cannot prove that a
   journalist has published nothing on a topic.
3. Phase 3: generated opportunities without a news trigger, then the unified
   workspace, speaker selection and activation context.
4. Phase 4: customer email first, remaining asset formats, statement-level
   evidence checks and opportunity action history.
5. Phase 5: remaining React pages and contextual Ask RAUTE. Retain access to
   legacy archive/market/visibility/competitor pages during the transition.

No production database was opened or migrated and nothing was deployed.

## Validation

- Full Python suite: **3,142 passed** (two dependency deprecation warnings).
- React: **6 passed**; clean `npm ci` and production Vite build passed.
- Chromium: built Desk loaded without JavaScript errors, an action submission
  increased the delivery count after redirect, classic fallback worked, and the
  390px mobile viewport had no page overflow. Used an isolated demo database.
- Built a Python wheel and checked that it contains the manifest, JavaScript,
  stylesheet and Desk translation keys.
- `git diff --check` passed.
- Docker image execution remains unverified: the local Docker daemon was not
  running. The frontend build stage is wired into the Dockerfile.

## Phase 1 implementation — 10 September 2026

- React Twin at `/client/{id}/twin`, linked from the existing workspace and Desk.
- Versioned API for statement creation, editing, confirmation, rejection,
  archival and history. Optimistic revisions reject stale edits with HTTP 409.
- Migration `0058_twin_statements` preserves the existing canonical profile
  rows while allowing additional statements per field. Full metadata snapshots
  precede edits; changing a verified statement invalidates its confirmation.
- The questionnaire catalogue contains **339 fields, 127 required**, copied
  from the supplied workbook's definitions only. No client answers are committed.
  Desk and Twin use the same required-field completion calculation.
- XLSX and UTF-8 CSV import has column mapping, bounded parsing, per-row errors,
  an expiring preview and explicit selection. Commit is atomic and idempotent;
  repeat uploads never overwrite a later manual correction.
- A spreadsheet's Fact label does not create an independent verification. The
  separate confirmation action requires an independent source and a review note;
  confirmation does not grant external-use permission.
- Shared prompt rendering carries all statements and their provenance into
  Ask RAUTE, opportunity detection, guide drafting and assets. Rejected/archived
  statements are omitted; explicitly restricted statements are excluded from
  external asset context. Legacy field-oriented readers retain canonical values.
  The full statement-by-statement output checker still belongs to Phase 4.

Validation: full Python suite **3,157 passed**, followed by **134 relevant tests**
after the final provenance changes; **11 React tests** passed. Chromium verified
creating two statements in one field, CSV preview/commit, editing, independent
confirmation and history. No JavaScript errors or horizontal page overflow at
390px. The migration was also run on an isolated empty database; an upgrade test
preserves old evidence and refuses a downgrade that would discard extra statements.

# Branch consolidation — 2026-09-24

## Production source before consolidation

Railway production deployment `4cfc3190-9164-4b4a-be43-b5ec0c9c27de`, created
2026-09-22 at 12:24 UTC, was successful and running. It was a CLI upload from
`codex/react-desk` source commit `8adacf8`, as recorded in
`26-railway-deployment.md`. Read-only SSH checks confirmed that the deployed
`twin_ai.py` and `web/routes/profile.py` SHA-256 hashes match that commit.
The branch tip `e895d6a` adds only release documentation after that source commit.

GitHub `main` was still at `c8bd17e`, 60 commits behind the local React branch.

## Merge decisions

- Fast-forwarded the consolidation checkout to `codex/react-desk` (`e895d6a`).
- Merged `claude/sidebar-groups` and its `claude/specs` ancestry, retaining the
  deployed React shell and its navigation tests. The older Jinja sidebar and
  its tests describe a workflow superseded by the later React commits. Added
  the eight specifications, implementation plan and reference images.
- Merged `claude/twin-evidence`, adding the master workbook, updated twenty
  kickoff questions and translations. Retained the deployed reviewed import
  implementation, React profile and corresponding tests. The older direct-write
  upload route and parser were superseded by selected preview imports, editable
  AI previews, provenance handling, and XLSX/CSV/PDF support.
- Merged `claude/desk`; its remaining merge ancestry required no file changes.
- Recorded the local `remy/vier-uhren@pre-heal-39db7f8b9b30` backup ancestry with
  an ancestry-only merge. `git log --cherry-pick --right-only --no-merges`
  confirmed there were no unique non-merge patches left to apply.
- All other GitHub branches were already ancestors. Branch references were
  retained; no branches or user working files were deleted.

The merge was assembled in an isolated checkout because the original workspace
contains untracked user documents, including a mockup that differs from the
version in the repository.

## Validation

- 62 frontend tests passed; the Vite production build passed using Node 22.22.3.
- 174 targeted backend tests passed: onboarding questions and clarity, Twin,
  questionnaire round trips, and AI imports.
- Every local and fetched branch tip is an ancestor of the consolidated commit.
- The existing crisis-navigation test expects an HTML `option` while the React
  shell renders links. The failure also reproduces on the pre-merge `e895d6a`
  baseline.

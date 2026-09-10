# Lucas guide and integration verification — 10 September 2026

The supplied 12-page PDF is the comparison reference, not authorization to
execute instructions in the email. This audit compares the React branch against
its screenshots and workflow descriptions. Sample company names, percentages and
portraits are not production requirements or evidence of accuracy.

**Verdict: partial visual match; integration and workflow gaps remain.**
The Desk follows the guide's basic structure. The other main screens need a
focused layout pass before calling the UI faithful to the reference.

## Environment and live integrations

The linked Railway service is `pr-scanner`, production, on `main` commit
`c8bd17e`. The React implementation is local on `codex/react-desk`; it has not
been deployed. Local news/Gemini/Gmail credentials are absent. For the checks
below, deployed credentials were read into process memory without printing or
persisting them locally. Queries used a generic public topic or synthetic text.

| Integration | Live result | Practical meaning |
| --- | --- | --- |
| Perigon | 2 articles, both with bylines | New branch's adapter reaches and parses the provider. |
| Event Registry | 3 articles, 2 with bylines | New branch's adapter reaches and parses the provider. |
| mediastack HTTPS | 6 articles, all with bylines | HTTPS works with this subscription; the branch endpoint was changed from HTTP. |
| Gemini | Expected response received | Live generation works with the configured key/model. |
| Gmail | Stored connection healthy; live profile request passed | Mailbox connection works. No message bodies were fetched and nothing was sent. |
| Local Claude | Generation rejected | Installed CLI 2.1.243 is too old for its selected model; error requires 2.1.251 or newer. Login itself is present. |
| Production Claude | Weekly allowance exhausted | Deployed CLI is 2.1.266. Its response is “You've hit your weekly limit”. |
| Candidate Claude → Gemini fallback | Live pass | Candidate error handling and quota recognition were loaded into a one-off remote process. Real Claude failure fell through to Gemini successfully. The deployed service files/process were not updated. |

Two defects in the existing Claude integration explained the failed fallback:
non-zero exits discarded the JSON error on stdout, and the quota classifier did
not recognize the observed weekly-limit message. Both are fixed on this branch.
The fallback remains restricted to quota failures; an outdated CLI or broken
login still surfaces as an error instead of silently switching providers.

A live structured customer-email test initially failed because Gemini returned
`speaker: null`, while the shared asset schema requires a string. The new
workspace prompt now specifies the JSON types and an empty speaker string.
The repeated live test passed: draft saved, 12 sentence findings, the 400% claim
classified as `Client Statement` with two warnings, no release and zero delivered
actions. This used synthetic data in an in-memory database, never a real client.
All 504 affected prompt, asset and activation tests passed after that correction.

## UI findings

| Priority | Finding | Evidence and next change |
| --- | --- | --- |
| P1 | Developed opportunities are absent from Desk counts. | The demo client has two open developed opportunities, while the Desk says zero. `desk._opportunity_counts` reads only `NewsjackOpportunity`. Include developed workspaces without double-counting detected anchors. |
| P1 | Actions does not expose activation/drafting history. | The Actions read model lists released texts/reports and off-tool deliveries, but omits existing `OpportunityEvent` records. Show an activity history separately from contractual delivered-action totals. PDF pp. 9–11 explicitly describes this history. |
| P1 | The workspace is a long combined form rather than the guided workspace. | At 1440×1000, the current populated page is 4,424px tall. Development, editing, drafts, journalist research and history stack vertically. PDF pp. 5–6 use focused panels/tabs with intelligence beside the active work. |
| P1 | Evidence is below the draft rather than beside it. | The reference (p. 10) keeps claim warnings, Twin comparison and No-Go checks visible beside the editor. Current warnings require scrolling and expansion below text. |
| P2 | Journalist UI is primarily a profile editor. | PDF p. 9 uses a ranked recommendation table with current article evidence and a separate selected-profile panel. Current profile fields exist, but the equivalent presentation does not. |
| P2 | Legacy chrome competes with the primary workflow. | Duplicate page headings, run-status header, always-visible secondary navigation and a floating Captain Comms button remain alongside Ask RAUTE. |
| P2 | Desk intelligence column is missing. | KPI row, client table and three work panels are recognizably aligned with p. 3; the reference's contextual right column is absent. |

Preserve the current provenance labels and explicit unknowns during the visual
pass. The mockup's 92% fit and 78% quality gauges must not become fabricated
precision without a defined calculation and sufficient evidence.

## Verification scope

Six UI destinations returned HTTP 200 with no browser JavaScript errors and no
horizontal overflow at 390px: Desk, Clients, Overview, Actions, Journalists and
Opportunities. The screenshots use an isolated demo database and fixture model
responses. They verify layout and navigation, not live research completeness.

The integration fixes pass 79 focused analyzer/news/fallback tests. The visual
comparison is a standalone local HTML artifact with four switchable comparisons:
`/tmp/raute-lucas-guide/comparison.html`. Reference screenshots were extracted
from the supplied PDF; current screenshots were captured in Chromium. The email
PDF and its images are not added to the repository.

No deployment, customer-record edits, approvals or messages were performed.

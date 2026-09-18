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

## Deployment readiness follow-up

The two functional P1 findings are now fixed: Desk includes open developed
opportunities without double-counting detected anchors, and Actions shows
workspace activation/drafting history separately from delivered work. Regression
checks verify dismissal/closure, client scoping and unchanged delivery totals.
The broader visual differences remain documented above.

Pre-deployment checks: 3,216 Python tests, 28 React tests and the frontend build
passed. A SQLite online backup was saved on the production volume, and migrations
0057 through 0061 were rehearsed on a copy. Integrity checks passed and existing
client, statement, article, analysis, asset, outreach and contact counts matched.

## Visual refinements and assistant consolidation — 2026-09-11

Removed the Captain Comms drawer, floating button, avatar and palette. Ask RAUTE
is the single assistant, reached from the top-right header and contextual links;
its redundant global sidebar entry was removed at the user's request. Existing
client/portfolio session conversations migrate only into the matching Ask scope.
Browser dictation and explicit read-aloud now live in Ask; Escape, context changes
and leaving the page stop voice activity. Streaming and provider fallback remain.

The React shell suppresses duplicate page titles and collapses specialist tools.
Desk adds a factual decisions/Twin-gaps rail. Opportunity workspaces use separate
views for overview, strategy, journalist research, texts/evidence and history;
mounted panels preserve unsaved edits across view changes. Development and text
creation use disclosures. Evidence sits beside the selected text editor, and
asset links open the text view and the requested saved text. Journalist research
uses a comparison table; profiles show their summary before the editing form.
No invented fit percentages or automatic approvals/sending were added.

Validation: 30 React tests and production build passed. The full Python run had
3,209 passes and one old palette-reference failure; after fixing that reference,
all 146 targeted styles/shell/assistant/i18n/auth/workbench tests passed. Chromium
checks passed at 1440px and 390px with no page errors or horizontal overflow,
including contextual Ask streaming, asset deep links and retained workspace edits.
Visual captures remain local under /tmp/raute-lucas-guide/refined-*.png.
These are structural refinements toward the references, not pixel-identical
reproductions: mockup-only scores, fabricated recommendations and imagery are
not presented as real data.

### Navigation consolidation — 2026-09-11

Client navigation now has four primary destinations: Overview, Opportunities,
Twin and Actions. Removed the repeated Ask RAUTE and development links from this
menu; the header assistant and development control on Opportunities remain.
Specialist links expand into a separate responsive grid instead of extending the
tab row. The grid opens on specialist pages and marks the current destination.
React page titles suppress the duplicate server header directly in the template.
The wrapping mobile top bar now grows with its contents to prevent overlap.

Validation: 92 shell/style/workbench tests passed; Chromium at 1440px and 390px
confirmed navigation, collapse/expand behavior, active specialist routes, absence
of duplicate heading/Ask entry, no page errors and no horizontal overflow.

### Client overview dashboard — 2026-09-12

Replaced the unstructured overview text/link list with a dedicated ClientOverview
component: mandate header, four factual metric cards, opportunity cards with
status and full titles, recent text rows with a designed empty state, a Twin
progress/gaps panel, and recent activity. Counts retain existing delivery and
unknown-contract semantics. The classic Desk fallback is shown only if the
React bundle is unavailable. No backend data or provider behavior changed.

Validation: production build, 30 React tests and seven workbench backend tests
passed. Chromium checks at 1800, 1280 and 390 pixels used long titles comparable
to the reported screenshot, verified empty texts, opportunity navigation, no
horizontal overflow or JavaScript errors. Existing Desk/Actions delivery checks
also passed. Screenshots are local at /tmp/raute-overview-{width}.png.

### AI Twin import — 2026-09-12

Added “Mit KI importieren” to the Twin. A background job combines mandate data,
active Twin statements, up to five stored guide documents, optional pasted source
text, and optional grounded profile web research. Public web research receives
only mandate metadata, not private source documents. The bounded mapping pass
proposes up to 100 answers to currently empty catalogue fields with source IDs.
Unknown fields/citations are discarded; unsupported questions remain open.

A per-client job slot prevents concurrent requests and supports reload/resume.
Results expire and use the existing reviewed import ledger; no schema change.
Nothing enters the Twin until explicit selection and commit. Commit rechecks
manual answers, is idempotent and keeps provenance. AI answers are Derived Insight,
Needs Verification, not independently verified, and require external approval;
stricter source confidentiality/internal-only restrictions propagate. No existing
answer is replaced. Web failures and worker interruptions are visible.

Validation: 76 targeted Twin/profile/auth tests passed, followed by all 11 AI
import tests including source-permission propagation; 32 React tests and build
passed. Chromium exercised start/background completion, reload/resume, explicit
selection/commit and mobile overflow on isolated demo data. A live Gemini probe
using only a fictional company and an in-memory database produced proposals;
one selected answer was imported and remained unverified. No production Twin
was changed during verification.

### Control simplification — 2026-09-12

Reviewed Desk, client list/overview, Assets, Twin, opportunity/activation workspaces,
journalists, Ask and shared navigation. Removed repeated Ask links on Desk,
opportunity overview and asset lists, duplicate opportunity entry points on the
client overview/list, and redundant legacy-page footer links in built React views.
Primary React pages now use one header bar; language selection is in the sidebar
footer, and manual news collection remains reachable in Settings.

Twin keeps AI import and statement editing prominent; spreadsheet/profile input
and statement history/rejection/archiving are grouped as secondary actions.
Independent confirmation is offered only with a suitable source and no existing
confirmation. Text editors keep save/check/approval prominent; copying and saved
text advice are grouped. Saved/released texts no longer invite redundant writes
or checks. Opportunity storyline suggestions use one picker, and active
workspaces save choices without a repeated activation button. Approval access
remains in the texts view. Ask suggestions appear before conversation starts;
conversation deletion and speech-stop appear only when applicable, with read-aloud
on the latest answer. Source/evidence details and approval controls remain.

Validation: 33 React tests, production build and 112 shell/style/i18n/workbench
checks passed. Chromium verified six primary pages at desktop/mobile sizes,
secondary controls, history access, storyline selection, text-specific Ask context,
conditional chat controls and manual-run access in Settings. No data was deleted
or production actions invoked during this audit.

### Legacy control consolidation — 2026-09-12

Extended the audit to profile, news, archive and Settings. Removed the global
news-collection button from legacy headers; Settings now has the single explicit
run form, disabled while collection is active. Live run status and polling remain.
Language selection uses the same sidebar control across both frontend families.
Removed the profile's duplicate Twin link, all-client research action inside a
single-client screen, and second submit button for the same profile form. A lone
contradiction now has one discard action; bulk discard remains for multiple rows.
Profile save, per-client research, questionnaire and provenance remain available.
Removed unused header-button styles and fixed a mobile profile-label overflow.

Validation: 290 targeted Python checks passed (281 unaffected checks plus all nine
run-status checks after updating the legacy-header expectation). Chromium checked
six primary and four legacy pages, including desktop/mobile overflow, single
Settings trigger, profile save, Twin navigation, language access, source history
and conditional Ask controls. Verification used isolated demo data; no production
research, sending, collection or profile writes were triggered.

### Focused workspace controls — 2026-09-12

Removed the Desk's duplicate Intelligence rail: its decision and Twin links
already appear in the three work lists. The mandate table and lists now use the
available width. Asset titles open their saved text directly, without a repeated
"Text öffnen" line. Removed the client list's legacy-portfolio management detour;
Settings remains in the sidebar. Overview activity only offers "Alle" when its
four-row preview omits events.

Text selection appears only with multiple saved texts; a stale text ID falls back
to the first available draft, keeping both editor and selector consistent.
Opportunity type filtering appears when the list contains different types or a
filter is already selected, so an active filter can always be cleared.

Validation: 33 React tests, production build and 64 workbench/shell checks passed.
Chromium verified six primary pages at desktop/mobile sizes and exercised single
and multiple text selection, stale links, asset-title navigation and mixed-type
opportunity filters with isolated responses. Desk screenshots reviewed. No
production content mutations were used for verification.

### Consolidated mandate navigation — 2026-09-12

Implemented the requested six primary tabs: Overview, Opportunities, Profil,
Actions, Archiv and KI-Sichtbarkeit. Removed the separate specialist-tool menu.
Opportunities owns Chancen, Heute, Impulse, Issues and Plan; declared crises remain
reachable there and an open crisis is flagged on the primary Opportunities tab.
Profil owns the former Twin (Wissen & Aussagen), company/kickoff/guide material,
Wettbewerb and Marktumfeld. A compact view selector shows only the current group's
views, with a no-JavaScript link fallback. Each legacy route highlights its parent
group; existing routes and content links remain valid.

Renamed Twin in user-facing React views, the classic Desk, page title, progress
labels, Ask suggestions and import/help text to Profil. Removed the duplicate
legacy-profile link from the import toolbar now that the group selector owns it.
Data models, field identities and import/approval behavior are unchanged.

Validation: 33 React tests and production build passed. 158 targeted Python
checks passed (95 unaffected checks plus 63 crisis/profile checks after updating
translations and the consolidated destination expectation). Chromium visited 13
mandate routes on desktop/mobile and exercised every Opportunities/Profile view
selector destination. Verified primary selection, direct Archive/Visibility
access, AI import access and the renamed overview. Screenshots reviewed. No
production content was modified for verification.

### AI import response parsing fix — 2026-09-14

Reproduced the reported background failure against the real configured providers
using an in-memory SQLite copy of the affected mandate. The model returned a
complete JSON code block followed by commentary; the previous fence stripper
left the closing fence/commentary in the string and json.loads raised Extra data.
The worker swallowed that exception and persisted only the generic retry message.

The importer now accepts plain JSON or one complete fenced JSON block with
surrounding commentary. Truncated, ambiguous and invalid response lists still
fail; field/source validation, the 100-answer limit, human-answer precedence and
review-before-commit remain. Malformed field-key types are skipped safely. Worker
failures record a specific safe code/message and diagnostic call locations without
logging source text, model output or exception messages. The UI marks failures as
alerts and offers an explicit retry while retaining entered context.

Validation: 40 backend Twin/import tests and all 34 React tests passed; production
build passed. Browser checks covered failed-job resume, explicit retry, retained
input, preview/source review and required selection at desktop/mobile sizes. A
second real-provider run on the isolated data copy returned the same extra-text
format and completed with 14 reviewable proposals under the patched parser.
No production facts, job statuses or previews were changed during these probes.

### Remove Heute from opportunity views — 2026-09-14

Removed Heute from the Opportunities view selector, including the no-JavaScript
links. Existing daily-view deep links still work and retain the Opportunities
parent tab; they omit the selector rather than falsely selecting Chancen.
Validation: 68 shell checks passed. Browser verified the four remaining options,
Issues navigation and returning from an existing daily-view link to Opportunities.

### Single profile page without submenus — 2026-09-14

Removed the profile view selector. Wissen & Aussagen, company/kickoff/guide
material, Wettbewerb and Marktumfeld now render as visible sections of one
profile page. Shared escaped template fragments retain the existing form handlers
and source metadata. Legacy company links render the same page; competitor and
market links redirect to their corresponding sections. Opportunities retains its
existing selector without Heute.

The embedded statements view initially shows five questions, with search, filters
and incremental loading, so the other profile sections remain reachable. Added
responsive section styling and retained the AI import and questionnaire controls.
No database schema or generation behavior changed.

Validation: 253 targeted backend checks and 34 React tests passed; production
build passed. Included an escaping regression check for stored profile text.
Chromium checked all four sections, legacy links, questionnaire open/close,
incremental question loading, primary navigation, unique input IDs and mobile
overflow. Desktop/mobile screenshots reviewed. Production content was not changed
for verification.

### Single Kontakte navigation entry — 2026-09-14

Removed the duplicate Journalisten sidebar item and named the shared workspace,
page title, breadcrumb and profile summary Kontakte/Kontaktprofil. The Contacts
entry opens the React workspace at /contacts; /journalists redirects there while
preserving contact selection and opportunity research context. Updated opportunity
links to the canonical destination. Existing contact form/history deep links and
Python-only fallback remain functional; both views use the same contact records.
No database or research behavior changed.

Validation: 153 backend contact/history/navigation/journalist checks and 34 React
tests passed; production build passed. Browser verification exercised creation,
profile saving, search, legacy redirects with selection, old edit links reading
the same data, a single active Kontakte sidebar entry and mobile overflow. Desktop
screenshot reviewed. Browser writes were restricted to the local demo database.

### Edit and delete from every client card — 2026-09-14

Added Bearbeiten and Löschen to each active mandate card. Editing opens a focused
modal for name, industry, country, quarterly commitment and monitoring terms.
The API reuses client CRUD validation, rejects stale form snapshots and preserves
unexposed preferences. Invalid values remain in the modal for correction.
Successful actions reload the roster and sidebar so names and counts stay aligned.

Deletion requires a separate named confirmation with Cancel focused by default.
It uses the existing soft-deactivation service: removes the client from the active
roster and monitoring while retaining archive/profile/work history, with recovery
through Settings. The dialog states these semantics. The sidebar now lists active
mandates only. Unknown IDs and competitors cannot use these card actions.

Validation: 110 backend client/workbench/shell checks and 37 React tests passed;
production build passed. Browser exercised actions on every card, persisted edits,
monitoring preservation, sidebar updates, cancellation/Escape, confirmation,
selected-client removal and responsive modal layout. Centered desktop and mobile
screenshots reviewed. All editing/deletion probes used local demo/test databases;
production verification will remain read-only.

### Consistent visual system across React and server views — 2026-09-14

The frontend remains hybrid: React/JavaScript owns Desk, Clients, Contacts,
Opportunities, Assets, Ask and the primary workbench/statement views. Python/Jinja
still renders the shell, archive, visibility, settings and parts of the unified
profile. This release changes presentation, not that architecture.

Refined the shared palette and contrast, typography, navigation states, controls,
cards, tables and spacing. A fingerprinted studio stylesheet shares the visual
language across both rendering systems. Reusable React page headings and empty
states replace inconsistent local headers. Clients now have structured cards with
identity, truthful profile completion, opportunity count and quarterly delivery;
edit/delete remain on every card. Client search has an explicit empty state.
Opportunity/contact master-detail columns now have useful widths and aligned tops.

Mobile navigation collapses behind a labelled toggle with expanded state, Escape
support and a visible-link fallback when JavaScript is disabled. No new model
calls, generation actions, database writes or decorative invented metrics.

Validation: 133 backend shell/workbench/style/contact checks and 37 React tests
passed; production build passed. Browser verified ten main React/server pages at
1600 and 390 pixels, plus Ask and Actions, without horizontal overflow or JavaScript
errors. Exercised card actions, search and empty states, modal cancellation,
workspace tabs, AI import access, mobile menu/keyboard behavior and no-JS fallback.
Desktop/mobile screenshots reviewed. Production verification remains read-only.

### Refined assistant, profile and opportunity workspaces — 2026-09-14

After verifying the previous visual release was actually served, refined the
remaining form-like workspaces within the same reduced design direction.
Ask RAUTE now has a context bar, welcome/suggestion area, distinct conversation
messages and a dedicated composer. Streaming, explicit submission, speech and
context-isolated history behavior are preserved. Profile progress is structured
into completeness, answered fields and independently confirmed statements; empty
question cards are more compact. All provenance and approval information remains
visible. Opportunity overview now reads as one briefing with a separate evidence
and review column, retaining source limitations and timing qualifiers.

The frontend remains hybrid React/Jinja; this change does not claim a full
JavaScript migration. No backend, database or model behavior was changed.
Validation: all 37 React tests and the production build passed. Desktop/mobile
browser checks exercised Ask submission with the synthetic local stream and
context isolation, profile editor/import access and opportunity tabs, with no
horizontal overflow or JavaScript errors. Screenshots reviewed.


### React navigation, archives, settings and complete profile — 2026-09-18

React now renders the sidebar, header and client tabs on every page. The global
and client archives, settings and complete unified client profile use React
components with allowlisted JSON view models. Profile includes company facts,
provenance and disagreements, guide documents and drafting, kickoff answers,
competitors, Share of Voice and market signals. Existing authenticated Python
POST handlers retain validation and persistence. Python continues to run the
integrations and background jobs; Jinja only hosts these pages' document and
escaped JSON bootstrap. Specialist bodies such as KI visibility and editorial
planning remain server-rendered and are explicitly documented as such.

The six client tabs and single top-right Ask RAUTE entry are preserved. Contacts
appears once, the profile has no submenu, and Opportunities has no Heute option.
Settings job polling and failed saves retain draft input; import preview retains
the selected file without committing. Kickoff saves/clears update one answer and
its progress without losing draft answers elsewhere. Sources and approval states
remain visible. ORM serialization is explicit and excludes credentials.

The Python UI suite renders the actual React components for semantic checks;
it no longer assumes the browser UI is emitted as Jinja HTML. New contracts cover
safe bootstrap escaping, client isolation, proposal serialization and kickoff
JSON writes. React tests cover navigation, draft retention, failed saves and URL
safety. Browser checks passed on seven routes each at 1440px and 390px without
JavaScript errors or horizontal overflow. Local synthetic-data interactions
verified client/profile/guide saves, import preview, isolated kickoff saves and
clears, and mobile navigation. Desktop/mobile screenshots were reviewed.

The standalone new-client form also uses React, with the same three inputs and
server validation. Its mobile duplicate-name flow preserves website and country.

Validation: 44 React tests and the production build passed. The complete Python
run exercised 3,275 cases: 3,251 passed, while 24 exposed a test-renderer bug that
truncated legacy headers/nested layouts. After filling the original document's
React mount points instead, all 24 passed on rerun; broader checks passed 234
legacy/navigation cases and nine run-status cases. Migration/new-client checks
passed 20 cases. No outstanding failing test remains. Two existing dependency
deprecation warnings remain (Starlette test client and feedparser).


### Press release as the default impulse content — 2026-09-18

The Impulse Content area presents one press-release draft directly. Removed the
six-format picker, checkboxes, bulk-write controls and tab JavaScript. Existing
other texts remain accessible in collapsed sections with their editing, review
and release controls. Missing historical drafts have one creation action; missing
required profile fields remain visible and never trigger invented facts.

New impulses from the sweep, refresh and manual development jobs include the
default press release. Explicit plan/newsjack activation starts it in the existing
background worker. A page GET never starts model calls. Blank format selections
now request only the missing press release; explicit legacy integrations remain
compatible. Automatic generation keeps any stored draft or release, including a
text saved while the models were working. Failed writing retains the impulse.
Approval, delivery and sending remain explicit actions.

Writing/review redirects and package polling now retain the selected impulse,
fixing an older issue where editing or writing a historical entry opened the
latest one. Isolated browser checks cover desktop/mobile layout, existing-text
access, the single fallback action and automatic content after opportunity
development, with no JavaScript errors or horizontal overflow.


### Custom message composer and live writing progress — 2026-09-18

A React composer now sits immediately below the default press release. Customers
can start with Kundenmail, LinkedIn-Post, Statement, Talking Points or Q&A,
then edit the full instruction before explicitly choosing “Eigene Nachricht
schreiben”. No custom text is generated on page load or preset selection.

The authenticated POST streams decoded draft-body previews and actual word counts.
An indeterminate progress bar covers writing and checking; completion is shown
only after persistence. There is no invented percent-of-text estimate. Claude's
partial-message events are supported without duplicating its final message, and
a watchdog stops silent subprocesses at the configured timeout. Slow/disconnected
readers cannot grow the progress queue without limit.

Custom messages use the existing grounded asset writer, schema validation,
source checking and guide checking. A saved draft survives checker failure.
An existing custom draft has an explicit replacement notice and version check;
a changed or released text cannot be silently overwritten. The press release
stays intact. Stored custom drafts remain editable in the existing content pane,
and the completion link reloads and opens that pane. Checks that finish after a
human edit no longer attach their verdict to different words.

Validation: the preceding default-content changes passed the complete Python
suite (3,280 tests). After adding streaming and the composer, 526 focused backend
tests passed; the final changed-path run passed 77 tests. All 47 frontend tests
and the production Vite build passed. Synthetic browser verification passed at
1440px and 390px: streamed partial text, actual word count, progress completion,
persistence, editing link, preserved press release, and no JavaScript errors or
horizontal overflow. No production client data was used for generation tests.

### Prepare existing impulses automatically; separate analysis and messages — 2026-09-18

Opening an existing impulse now automatically requests its missing press release
through a dedicated POST. A React status component polls a read-only endpoint
and inserts the completed draft without reloading the page or discarding custom
message instructions. Existing, edited and released texts are returned intact.
Busy jobs defer preparation; failed jobs require an explicit retry so repeated
page visits do not repeatedly spend model calls. Required missing profile facts
remain visible with a link to complete them. Server-side page GETs remain read-only.

The analysis has its own slate background and heading. A separate “Nachrichten &
Texte” heading, accent divider and document icon introduce white document panels
with larger body text. The custom composer and existing editing/review controls
remain available underneath.

Validation: 83 backend tests, 51 frontend tests and production Vite build passed.
Synthetic browser checks verified automatic preparation without a creation click,
only one start request, progress, preserving custom instructions during completion,
saved-draft editing, different visual surfaces and no JS errors or horizontal
overflow at 1440px and 390px. Final document styling was also checked in both widths.

### Resilient AI profile import and shared UI refinement — 2026-09-18

Reproduced the Arrakis.finance import failure in production without committing
facts: the all-fields request timed out after 138 seconds overall (120-second
model limit). Its command argument contained about 95 KB of catalog and sources.
The importer now maps compact field metadata in batches of up to 60 questions,
retains successful batches after individual provider/parse failures, reports
partial completion, and publishes research/mapping/validation progress. A stale
or expired worker stops before another provider call. Source validation,
confidentiality inheritance, protection of human answers and explicit review
before committing remain enforced. The CLI receives prompts through stdin,
avoiding operating-system argument-size limits for larger source documents.

The import panel opens immediately under its action and scrolls into view. Its
controls wait for persisted status restoration; polling is sequential and
cancelled on unmount. Progress reflects completed question batches, not invented
time-based percentages.

Shared buttons now distinguish primary, secondary and destructive actions with
consistent sizing, softer corners, restrained shadows and visible keyboard focus.
Knowledge, company, competition and market sections have distinct surfaces and
heading accents. Filters, settings cards and opportunity lists use quieter neutral
surfaces. Mobile layouts and reduced-motion preferences remain supported.

Validation: 106 backend tests and 52 frontend tests passed; production Vite build
passed. Browser checks at 1440px and 390px covered clients, archive, client archive,
settings/editing and profile/kickoff, with no JS errors or horizontal overflow.
An isolated synthetic import completed through submit, progress, review, explicit
selection and persisted fact refresh. Verified primary-button computed styles and
reviewed desktop/mobile screenshots. Live import verification follows deployment.

Production verification: the actual Arrakis.finance import completed in 360
seconds with 51 reviewable suggestions, including web research, and no failed
batches. The status endpoint restores all 51 rows with `Cache-Control: no-store`.
Every suggestion requires verification; the ClientFact count stayed at 94.
No generated suggestion was committed. Additional browser checks covered overview,
opportunities and all three lower profile sections at both widths. Removed an
older React CSS reset that otherwise suppressed the shared section surfaces.

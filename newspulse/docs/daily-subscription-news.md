# Daily Claude web research

The existing scheduler runs at `NEWSPULSE_DAILY_AT` (default 06:10 Europe/Berlin).
Registry feeds, per-company Google News RSS, topic radar and configured news APIs
continue unchanged. `NEWSPULSE_DAILY_AI_NEWS=1` adds actual Claude WebSearch and
WebFetch research for every active non-competitor mandate, covering the past day.
OpenAI is not used. No second scheduler is needed.

Claude receives company name, aliases, industry, themes, alert topics, website and
relevant shared knowledge snippets. The user explicitly authorized this scope.
The existing Claude subscription login is used; there is no paid API fallback.
Only WebSearch and WebFetch are enabled in the research subprocess.

Up to ten articles per mandate are accepted. Each URL must appear in the CLI's
actual tool results; publication timestamps must include a timezone and fall
inside the search window. The model extracts timestamps and summaries from sources;
these are not independently certified. Undated, old, future and unobserved links
are rejected. Normal matching, deduplication and analysis still decide what is
stored and shown to a mandate.

The `web_research` table in `/data/daily-news-search.sqlite3` records local date,
mandate, status, raw response, tool-observed sources, accepted articles and reject
count. A unique key claims each daily research before invoking Claude. Successful
results are reused on reruns; failed/interrupted attempts remain visible for that
day instead of silently triggering repeated calls. The following day retries.
Keep this ledger in the normal data backup. Failures mark the main run partial
but do not stop the normal news pipeline or another mandate's research.

Set `NEWSPULSE_DAILY_AI_NEWS=0` to disable only this supplement. Research cannot
guarantee exhaustive coverage; publication timestamps missing from a source are
not invented. It does not bypass paywalls, send mail or publish content.

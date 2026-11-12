# Gemini spending in RauteOS

RauteOS reads reported monthly costs from the standard or detailed Google Cloud
Billing BigQuery export. It filters by an exact project ID and service IDs.
The displayed amount is `SUM(cost) + SUM(credits.amount)`, in the export currency.
Credits here are billing discounts/adjustments, not purchased prepaid top-ups.
The period is the usage month in Europe/Zurich, not the invoice month. Costs include
all applications using the selected project/services, not only RauteOS calls.

## One-time Google Cloud setup

1. In the billing account linked to the Gemini API project, open **Billing export**
   and enable the **standard usage cost export** to a BigQuery dataset. Record the
   full generated table ID and the dataset location (for example EU).
2. Create a dedicated read-only identity for RauteOS. Grant **BigQuery Data Viewer**
   on that dataset and **BigQuery Job User** on the project containing the export.
   Configure Google Application Default Credentials on the server. Prefer workload
   identity federation; if using a service-account credential file, keep it outside
   the repository, with restricted file permissions, and never paste it into chat.
   On the current deployment, a file in `/srv/rauteos/data/` is mounted under `/data/`.
   Set `GOOGLE_APPLICATION_CREDENTIALS=/data/<credential-file>.json` in the protected
   server environment, then recreate the app container to load the environment.
3. Identify the Gemini project ID and exact Gemini service IDs from the export.
   Inspect `project.id`, `service.id`, and `service.description`; avoid using a
   broad service such as all Vertex AI if it also contains non-Gemini workloads.
4. In **Einstellungen → KI-Verbindungen → Gemini → BigQuery verbinden**, enter the
   table ID, Gemini project ID, service IDs and dataset location. Save and load costs.

The source is not connected merely because the Gemini API key works. The key does
not grant BigQuery billing access. Missing rows mean "no reported data", never an
assumed zero. Initial export/backfill and subsequent cost reporting can take time.

## Refresh and query limits

Costs load when the Gemini settings card opens and refresh every 15 minutes while
that page is visible. The server caches attempts for 15 minutes, including failures,
so repeated clicks do not create extra queries. Saving source settings clears the
cache. Queries are read-only, parameterized, limited to 1 GB billed bytes per query,
and have a 20-second server job timeout and 25-second result wait. A timeout attempts
to cancel the job. There is no background refresh while the page is closed.

On failures, a previous successful result for the same source/month remains visible
with its original timestamp and an error. The first new month does not reuse last
month's amount. Mixed currencies are rejected rather than combined or converted.
No automatic prepaid-balance estimate is made: the former manual balance is retained
in storage but is not a top-up ledger and is no longer displayed.

Google references:
- https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery-setup
- https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery-tables/standard-usage
- https://docs.cloud.google.com/billing/docs/how-to/split-charging-cycle

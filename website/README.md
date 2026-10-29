# raute+kopf website

Static coming-soon page served by nginx, independently of RauteOS. Edit
`public/index.html` and `public/style.css`; the logo is `public/logo.jpg`.
No JavaScript, dependency installation, database, or volume is required.

## Railway

- Project: `pretty-wonder` (`f84bbc25-cdb2-4e34-8f08-b66e1201fd5d`)
- Environment: `production`
- Service: `raute-website` (`1c3dd03f-19b8-4239-84d3-cf52ffb98e3b`)
- Public URL: https://raute-website-production.up.railway.app
- Custom domain: https://www.raute-kopf.com (DNS verified and HTTPS valid)
- Root domain: `raute-kopf.com` (STRATO redirect and HTTPS still pending)

Deploy from the repository root, uploading only this directory:

```sh
railway up website --path-as-root --project f84bbc25-cdb2-4e34-8f08-b66e1201fd5d --service raute-website --environment production
```

The service uses CLI uploads; GitHub autodeploy is not configured. Always specify
the service so the existing RauteOS service is not affected.

## Domain setup

DNS is managed by STRATO. Use `www.raute-kopf.com` for the Railway site,
with the root domain redirected through STRATO. Both domains are registered
in Railway. The www domain is verified with a valid certificate as of
2026-10-18. The root domain still serves STRATO's placeholder over HTTP and
fails HTTPS; its redirect must be completed in STRATO.

In STRATO's DNS settings for `raute-kopf.com`, configure:

| Type | Name | Value |
| --- | --- | --- |
| CNAME | `www` | `jw0t60f6.up.railway.app` |
| TXT | `_railway-verify.www` | `railway-verify=4bc70d4669d1832d84c6804804e215679f6444d7b0f58052fe606c77a636a17d` |

For the root domain, use STRATO's external 301 redirect to
`https://www.raute-kopf.com/`. Ensure HTTPS is enabled for the root-domain
redirect in STRATO too. Preserve existing mail records. Railway provisions
HTTPS for www after DNS and ownership validation succeed.

The earlier apex CNAME instructions do not apply to STRATO: it supports CNAME
records for subdomains, while Railway has no static IP for an apex A record.

See [STRATO DNS documentation](https://www.strato.de/faq/domains/wie-kann-ich-bei-strato-meine-dns-eintraege-verwalten/),
[STRATO redirects](https://www.strato.de/faq/domains/alles-zur-domainumleitung/), and
[Railway domain documentation](https://docs.railway.com/cli/domain).

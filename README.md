# RauteOS

PR-Arbeitsplatz für Kundenprofile, Unternehmensnews, Issues/Krisen, Opportunities,
Impulse und Medienmonitoring. Das Backend verwendet FastAPI und SQLAlchemy;
die interaktiven Oberflächen verwenden React und Vite.

## Lokal starten

Voraussetzungen: Python 3.11+, uv und Node 22.22.3 (siehe `frontend/.nvmrc`).

```sh
cd frontend
nvm use
npm ci
npm run build
cd ../newspulse
uv sync --frozen
uv run alembic upgrade head
uv run newspulse-web
```

Die Anwendung ist anschließend unter `http://127.0.0.1:8000` erreichbar.
Konfiguration: [Backend-Dokumentation](newspulse/README.md) und
[Beispielkonfiguration](newspulse/.env.example).

## Tests

```sh
cd frontend
nvm use
npm test
cd ../newspulse
uv run pytest -q
```

Auch die Python-Tests rendern React-Komponenten; dafür muss die oben genannte
Node-Version im `PATH` stehen. Externe KI-Aufrufe werden in der Testsuite ersetzt.

## Struktur

- `frontend/`: React-Oberflächen und Komponententests.
- `newspulse/`: Backend, Datenmodell, Migrationen und Tests.
- `features/`: fachliche Spezifikationen und Referenzentwürfe.
- `deploy/`: Deployment-Konfiguration; benötigt separat eingerichtete Secrets.

Lokale Datenbanken, Zugangsdaten, Logs und Testausgaben gehören nicht ins Repository.
Der Datenbestand wird mit Alembic migriert; eine neue Installation enthält keine
Kundendaten. Details zum Betrieb stehen in der
[Deployment-Dokumentation](newspulse/docs/deployment.md).

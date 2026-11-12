# 12 Medien → Themen → Assets

Neuer Ablauf für die Kundenseite, ersetzt den Reiter „Aktivitäten“.
Mockup: https://claude.ai/artifact/6PcVfPHDbGYv1YSseWsc4V (vier Bildschirme).

```
Medien (alle Treffer zu Kunde und Keywords)
  → ★ favorisieren  ────────────┐
                                ▼
Themen (aus Medien ★ oder Vorschlag von RAUTE)
  → Deep Dive beim Darüberfahren: Was ist passiert? · Warum relevant? · Pitch · Ansprechpartner
  → „Thema aktivieren“
                                ▼
Assets (aktivierte Themen)
  → Kundenmail · Statement · Pressemitteilung · Gastbeitrag · Pitch · Custom
  → RAUTE schreibt einen Entwurf, Lucas bearbeitet ihn im Fenster
  → Speichern · Kopieren · Senden (vorerst gesperrt)
  → Export als Word oder PDF nach Google Drive: Kunden › <Kunde> › Assets
```

Rechts neben den Themen steht die **Agenda** (bisher „Redaktionsplan“) als
Zeitstrahl mit Details beim Darüberfahren.

## Was im Code schon steht

| Mockup | Vorhanden | Wo |
|---|---|---|
| Treffer zum Kunden | Artikel mit Analyse für den Kunden | `web/routes/client.py` `_archive_conditions` |
| Treffer zu Keywords | gesammelt als `TopicHit`, aber nicht im Medien-Reiter gelistet | `job._fetch_topics`, `client.py:636` (nur Zahl) |
| Vorschläge von RAUTE | erkannte Chancen (`NewsjackOpportunity`, nur `belegt`) und entwickelte Impulse (`Angle`) | `workspaces.listings`, `opportunities_api` |
| Deep Dive | Arbeitsplatz je Chance: Begründung, Storyline, Sprecher, Kontakte | `OpportunityWorkspace`, `GET /api/v1/…/opportunities/{kind}/{id}` |
| Passende Journalisten | Vorschlag mit Belegen | `pitch.targets_for`, `opportunity.recipients` |
| „Thema aktivieren“ | `POST …/opportunities/{kind}/{id}/activate` | `opportunities_api.py:155` |
| Asset-Arten | Kundenmail, Pitch, Statement, Pressemitteilung, Gastbeitrag, Eigene Aktion (+ Q&A, Interviewangebot, LinkedIn, Briefing) | `activation.FORMATS`, `assets.WORKSPACE_FORMATS` |
| KI-Entwurf | Auftrag mit gespeichertem Kontext, Gegenprüfung durch den Reviewer, Lektor | `activation.run`, `assets._proofread` |
| Im Fenster bearbeiten und speichern | `PUT …/{text_type}/{text_id}` mit Versionsschutz | `activation_api.py:122`, `assets.py` (`STALE_EDIT`) |
| Senden | Freigabekette bis Gmail-Entwurf | `outreach`, `gmail_link` |
| PDF | reportlab ist Abhängigkeit, PDFs gibt es schon (Fragebogen, Berichte) | `twin_questionnaire.pdf`, `report.py` |
| Agenda-Daten | Redaktionsplan mit Monats-Hooks | `plan.py`, `plan_hooks`, `/plan` → `/opportunities#redaktionsplan` |

Der Umbau ist deshalb vor allem eine **neue Oberfläche über bestehende
Bausteine**. Neu im Backend sind nur: Keyword-Treffer im Medien-Reiter, der
Stern als Weg zum Thema, der Deep Dive für favorisierte Artikel, Word-Export
und Google Drive.

## Was vorher entschieden oder gebaut werden muss

1. **Google Drive (Blocker nur für den Drive-Export).**
   - Ein neuer OAuth-Scope `drive.file`: RauteOS sieht dann nur Dateien, die es
     selbst angelegt hat. Der Code behandelt jeden neuen Scope bewusst als
     Entscheidung (`gmail_link.py`, DEC-4). Der Google-Client muss den Scope im
     Zustimmungsbildschirm führen, und wer verbindet, muss neu zustimmen.
   - Welches Konto ist die Ablage: ein Firmen-Drive (Shared Drive) oder das
     Drive einer Person?
   - Gibt es den Ordner „Kunden“ schon, und wie heißen die Kundenordner? RauteOS
     sollte fehlende Ordner anlegen und die Ordner-ID je Kunde speichern.
2. **Word-Export.** `pyproject.toml` hält fest, dass `.docx` bewusst noch nicht
   unterstützt wird. Dafür kommt `python-docx` als neue Abhängigkeit dazu.
3. **Was ein „Thema“ im Datenmodell ist.** Vorschlag: kein neues Modell. Ein
   favorisierter Artikel wird ein `OpportunityWorkspace` mit neuem
   `context_kind = "article"`. Status `draft` heißt Thema, `active` heißt
   aktiviert. Dafür muss `workspaces.anchor` den neuen Typ kennen.
4. **Absprache mit der parallelen Sitzung.** Sie baut gerade an Medien-Reiter
   (`MediaReload`, Archiv als Medien-Tab), Aufgaben und Einstellungen. Phase 2
   fasst dieselben Dateien an und sollte nicht gleichzeitig laufen.

Senden bleibt vorerst gesperrt, das braucht keine Vorarbeit.

## Phasen

Jede Phase ist für sich lauffähig und wird einzeln deployt. Lucas sieht nie
einen halben Umbau.

### Phase 1: Navigation und Agenda
- Kundenreiter: `Medien · Themen · Assets` statt `Medien · Aktivitäten`
  (`frontend/src/shell.jsx`, Eintrag `chancen`). `/opportunities` leitet auf
  `/themen` um, alte Links bleiben gültig.
- „Redaktionsplan“ heißt überall „Agenda“, auch in i18n und Desk.
- Agenda als Zeitstrahl rechts neben den Themen: kommende Termine aus
  `plan_hooks` und Assets mit Datum, Details beim Darüberfahren und per
  Tastatur (`:focus-within`). Keine `<details>`-Dreiecke.
- Tests: Reiterleiste, Umleitung, Agenda-Darstellung.

### Phase 2: Medien zeigt Kunde und Keywords
- Abfrage im Medien-Reiter = Artikel mit Analyse für den Kunden **oder** mit
  `TopicHit` für den Kunden. Jede Zeile trägt ihre Herkunft:
  „über den Kunden“ oder „Keyword ‚…‘“.
- Filter: Alle · Über den Kunden · Zu den Keywords · je Keyword.
- Stern je Zeile: `POST /client/{id}/themen` mit `article_id` legt das Thema
  an und schreibt, wer favorisiert hat. Ein zweiter Klick nimmt das Thema
  zurück, solange es nicht aktiviert ist.
- Tests: Keyword-Treffer erscheinen, Filter, Stern legt genau ein Thema an.

### Phase 3: Themen mit Deep Dive
- Liste aus drei Quellen: favorisierte Artikel, erkannte Chancen (`belegt`),
  entwickelte Impulse. Filter: Alle · ★ Aus Medien · Vorschläge von RAUTE ·
  Aktiviert.
- Deep Dive:
  - **Bei Vorschlägen** aus den bestehenden Feldern: Begründung, Storyline,
    Sprecher, `opportunity.recipients`.
  - **Bei favorisierten Artikeln** schreibt der Designer nach dem Stern im
    Hintergrund einen Deep Dive: neues Prompt `prompts/themen_deep_dive.txt`,
    Antwort als JSON mit `was`, `warum`, `pitch`. Die Ansprechpartner kommen
    aus `pitch.targets_for`, nie erfunden.
  - Fehlt etwas, steht dort „bitte ergänzen“.
- Anzeige beim Darüberfahren und per Fokus. „Thema aktivieren“ nutzt den
  bestehenden `activate`-Aufruf.
- Tests: Deep Dive aus beiden Quellen, Aktivieren ändert den Status, kein
  erfundener Journalist.

### Phase 4: Assets
- Neue Seite `/client/{id}/assets`: links die aktivierten Themen, rechts deren
  Assets und „Neues Asset“ mit Kundenmail, Statement, Pressemitteilung,
  Gastbeitrag, Pitch und Custom (= `custom`, mit Freitext-Auftrag).
- Entwurf über `activation.run`. Bearbeiten im Fenster über den bestehenden
  `PUT`. **Speichern** speichert, **Kopieren** legt den Text in die
  Zwischenablage, **Senden** ist sichtbar und gesperrt („bald“).
- Pressemitteilung: Umschalter raute+kopf- oder Kunden-Logo (Logo liegt schon
  in `logos.py`).
- Tests: alle sechs Arten anlegbar, Speichern mit Versionsschutz, Senden
  gesperrt.

### Phase 5: Export
- Download zuerst: PDF (reportlab) und Word (`python-docx`) je Asset und als
  ganzes Thema (alle Assets und der Deep Dive in einem Dokument).
- Danach Google Drive: Datei in `Kunden › <Kunde> › Assets` ablegen, Link im
  Thema speichern. Voraussetzung: Punkt 1 oben.
- Tests: beide Formate erzeugen, Drive über einen Test-Doppelgänger.

### Phase 6: Aufräumen
- Alte Aktivitäten-Seite (`OpportunitiesPage.jsx`) und ihre Tests entfernen.
- Desk-Links „Relevante Chancen“ zeigen auf Themen und heißen so.

## Offene Fragen an Lucas und Raphael
- Bleiben Issues & Krisen ein eigener Reiter, oder ein Filter unter Themen?
- Soll ein verworfenes Thema verschwinden oder unter „Verworfen“ liegen?
- Wer darf aktivieren: beide, oder nur die Person, die das Thema favorisiert hat?

## Stand der Umsetzung (12.11.2026)

Alle sechs Phasen sind gebaut. Abweichungen und Entscheidungen beim Bauen:

- **Thema = Impuls mit Arbeitsplatz.** Der Stern legt einen `Angle` mit
  `OpportunityWorkspace` an (`data.origin = "medien"`, `starred_by`,
  `article_id`), Modul `themen.py`. Kein neues Datenmodell, keine Migration.
- **Medien** hat zwei Ansichten statt einer gemischten Liste: „Über <Kunde>“
  und „Zu den Keywords“ (`?quelle=keywords`, Filter `&keyword=`).
- **Drive:** Ablage im gemeinsamen Ordner „7. Assets“
  (`NEWSPULSE_DRIVE_ASSETS_FOLDER`, Standard ist die ID aus dem Link), je
  Kunde ein Unterordner, beim ersten Export angelegt. Verbunden unter
  Einstellungen › Allgemein › Google Drive, über den schon registrierten
  Gmail-Callback (der `state` beginnt mit `drive.`). Scope ist `drive`, weil
  `drive.file` nicht in einen fremden Ordner schreiben darf.
- **Logo im Export:** noch nicht. Logos liegen nur als URL vor; Word und PDF
  tragen den Kundennamen im Kopf.
- **Senden** ist sichtbar und gesperrt.
- **Belegprüfung** („Aussagen prüfen“) ist aus dem alten Panel in den Editor
  unter Assets übernommen.

## Nachgezogen (12.11.2026, abends)

Abgleich mit dem Mockup, die Lücken geschlossen:

- **Deep Dive auf der Karte** beim Darüberfahren und per Fokus, wie im Mockup,
  mit „Passende Ansprechpartner“ (`workspaces.recipients`). Die Detailseite
  („Details ansehen“) bleibt für den ganzen Text und die Quellen.
- **Editor als Seite:** Logo, Rubrik mit Datum, Titel und Text auf einem Blatt.
  Umschalter Ohne · raute+kopf · Kunden-Logo, je Asset im Browser gemerkt;
  Word und PDF tragen das gewählte Logo im Kopf (`?logo=` bzw. `logo` beim
  Drive-Export).
- **Alte Impuls-Seite** (`/client/{id}/advice`): Ein Aufruf im Browser landet
  im Thema bzw. in dessen Assets (`advisory.new_flow_href`). Die Seite selbst
  und ihre Fragmente bestehen noch für den Code, der sie abruft; entfernen
  ist der nächste Schritt.

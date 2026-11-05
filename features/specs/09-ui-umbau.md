# 09 UI-Umbau nach dem rauteOS-Prototyp

> bitte mache einen plan zur überarbeitung dass die UI elemente alle so wie in
> den bildern angelegt sind. […] also das aktuelle Design sollte der Helle Modus
> sein und der Dunkle Layout sollte neu werden. Wir können dann oben ein kleinen
> Button mit einem Licht haben um zwischen hell und dunkel umzustellen.

Vorlage: der klickbare Prototyp „rauteOS v0.1“ vom 3. November 2026
(`index.html`, README und fünf Screenshots: Desk, Story Workspace, Mobile Desk,
Client Workspace, Media CRM). Der Prototyp ist ein Referenzmodell, keine
Codebasis. Übernommen werden Aufbau und Aussehen, nicht sein Code.

## Festlegungen

1. **Zwei Modi, ein Aufbau.** Navigation, Reiter und Seitenaufbau sind in
   beiden Modi gleich. Der Modus wechselt nur Farben, Radien und Schatten.
2. **Hell = das heutige RauteOS.** Violetter Akzent, helle Seitenleiste.
   Standard für jeden, der nichts umstellt.
3. **Dunkel = der Prototyp-Look.** Schwarze Seitenleiste `#181a19`, Lime
   `#d5f563` als Auswahl und für Ask RAUTE, heller Inhalt `#f5f6f4`, schwarze
   Hauptknöpfe, Radius 16 px.
4. **Ein Licht-Button oben rechts** schaltet um. Die Wahl gilt pro Browser
   und wird gesetzt, bevor die Seite gezeichnet wird (kein Aufblitzen).
5. **Farben nur über Tokens.** Jede Farbe einer App-Seite kommt aus den
   Tokens in `app.css`. Ein Test (`test_theme.py`) hält das fest. Druck- und
   PDF-Dokumente sowie die Kundenseite des Fragebogens bleiben immer hell.
6. **Lime ist eine Fläche, nie Schrift.** Auf Hell ist es unlesbar. Als
   Textfarbe dient im Dunkel-Modus ein Olivgrün `#5a6f45`.
7. **Nichts Leeres in der Navigation.** LinkedIn und Sales CRM erscheinen erst,
   wenn es sie gibt (siehe Schritt 6).
8. **Das Desk-Briefing** entsteht zuerst ohne Modellaufruf aus den Zahlen, die
   der Desk schon hat. Ein KI-Briefing folgt, wenn es gewünscht ist.

## Zuordnung heute → Prototyp

| Prototyp | Heute | Schritt |
|---|---|---|
| **Arbeitsplatz** · Desk | Desk | 3 |
| Aufgaben | Braucht Entscheidung / In Arbeit (Desk) | 6 |
| Kunden | Clients + Mandanten in der Seitenleiste | 2 |
| **Kommunikation** · Intelligence | News Heute + Opportunities aller Mandanten | 2 |
| Stories & Content | Assets, Workbench, Opportunity-Workspace | 4 |
| Media & Relationships | Kontakte / Journalisten | 5 |
| LinkedIn | gibt es nicht | 6 |
| **Wachstum** · Sales CRM | gibt es nicht | 6 |
| Unten: Nutzer, Archiv, Einstellungen | Archiv, Einstellungen | 2 |

Mandanten-Reiter (Client Workspace):

| Prototyp | Heute |
|---|---|
| Überblick | Overview |
| Wissen | Profil (21 Recherche-Themen, 22 Kundenfragen, Kontakte) |
| Strategie | Guide, Wettbewerb, Marktumfeld |
| Chancen | Opportunities, Impulse, Issues |
| Umsetzung | Plan, Texte, Krise |
| Wirkung | KI-Sichtbarkeit, Berichte, Archiv |

Alte Adressen leiten auf ihre neue Stelle weiter.

## Schritte

Jeder Schritt wird einzeln gebaut, getestet, in Hell und Dunkel angesehen
und ausgerollt. Ein Schritt ist erst fertig, wenn er live ist.

- [x] **1. Zwei Modi und Licht-Button**
  - Alle festen Farben in App-Stylesheets und Seitenvorlagen durch Tokens ersetzen.
  - Hell-Tokens = heutige Werte, Dunkel-Tokens = Prototyp.
  - Rahmen (Seitenleiste, Kopfzeile, Knöpfe) über eigene Tokens, damit er in beiden Modi stimmt.
  - Licht-Button in der Kopfzeile, Wahl vor dem ersten Zeichnen setzen.
  - Test gegen neue feste Farben; Test für den Button.
- [x] **2. Navigation wie im Prototyp**
  - Seitenleiste in Gruppen Arbeitsplatz / Kommunikation, Bereiche umbenennen.
  - „Intelligence“ als Seite über alle Mandanten (News Heute + Opportunities).
  - Nutzerbereich unten mit Archiv und Einstellungen.
  - Kopfzeile: Pfad, Suche (⌘K), Ask RAUTE, Licht-Button, Sprache.
  - Handy: Leiste unten (Desk, Kunden, Intel, Stories, Aufgaben).
- [x] **3. Desk wie im Prototyp**
  - Kopf „Guten Morgen, …“, Briefing-Kasten, vier Kennzahlen.
  - „Heute priorisiert“, „Relevante Chancen“, „Das braucht Deine Aufmerksamkeit“, Rückmeldungs-Kacheln.
- [x] **4. Client Workspace mit sechs Reitern**
  - Reiter Überblick · Wissen · Strategie · Chancen · Umsetzung · Wirkung, Weiterleitungen.
  - Überblick: Unternehmen + Geschäftsziel, Laufende Stories, Leistungen, Wirkung, Nächste Schritte.
- [ ] **5. Stories & Content und Media & Relationships**
  - Story-Karten, Schrittleiste Analyse → Storyline → Assets → Medien → Outreach → Ergebnisse, Editor mit Seitenspalte.
  - Kontakte dreispaltig: Liste, Profil, Journalisten-Fit.
- [ ] **6. Neue Bereiche (eigene Specs)**
  - Aufgaben, LinkedIn, Sales CRM brauchen eigene Datenmodelle. Erst Spec, dann Bau.

## Stand

**Schritt 1, 5. November 2026.** Rund 390 feste Farben in `app.css`,
`studio.css`, den Frontend-Stylesheets und elf Seitenvorlagen laufen jetzt über
Tokens; `test_theme.py` verhindert neue. Hell trägt die bisherigen Werte,
Dunkel die des Prototyps, der Rahmen hat eigene Rollen-Tokens (`--side-*`,
`--action`, `--assist`, `--mark`). Der Licht-Button sitzt rechts neben DE/EN
und merkt sich die Wahl im Browser (`raute-theme`); ohne Wahl gilt Hell.

**Schritt 2, 5. November 2026.** Seitenleiste in den Gruppen Arbeitsplatz
(Desk, Kunden) und Kommunikation (Intelligence, Stories & Content, Media &
Relationships); die Mandantenliste bleibt darunter, Archiv und Einstellungen
unten. Pfadzeile und Seitentitel tragen die neuen Namen. Suche mit ⌘K. Am
Handy eine Leiste unten (Desk, Kunden, Intel, Stories, Medien); „Aufgaben“
kommt mit Schritt 6. Intelligence ist vorerst die bisherige News-Heute-Seite;
die Zusammenführung mit den Opportunities aller Mandanten folgt in Schritt 3.

**Schritt 3, 5. November 2026.** Desk mit Gruß nach Tageszeit (Vorname nur,
wenn die Login-Adresse mit einem beginnt), Datum, Briefing-Kasten aus den
eigenen Zahlen (offene Entscheidungen, Krisen, die ersten zwei wartenden
Mandanten, offene Chancen; „Briefing vertiefen“ öffnet Ask RAUTE), vier
Kennzahlen, „Heute priorisiert“ (Entscheidungen), „Relevante Chancen“ (neu:
offene Opportunities aller Mandanten über `workspaces.listings`), „Das braucht
Deine Aufmerksamkeit“ (In Arbeit) und drei Kacheln. Der Mandantenüberblick aus
Spec 02 bleibt darunter. Ein KI-Briefing ist noch offen (Festlegung 8).

**Schritt 4, 5. November 2026.** Sechs Reiter (Überblick, Wissen, Strategie,
Chancen, Umsetzung, Wirkung); unter jedem stehen seine Seiten als Ansichten
(Strategie: Guide, Wettbewerb & Markt, Medienkarte; Chancen: Opportunities,
Issues, Heute; Umsetzung: Plan, Impulse, Krise; Wirkung: KI-Sichtbarkeit,
Berichte, Archiv). Alle Adressen bleiben gleich, nur die Zuordnung ist neu.
Der Überblick zeigt „Das Unternehmen“ (Recherche-Thema 05 und Kundenfrage 02
als Geschäftsziel), Laufende Stories, Aktuelle Texte, Leistungen im Quartal,
Wirkung, Nächste Schritte (die Desk-Entscheidungen des Mandanten) und das
Profil. Die Leitfragen im internen Kundenfragebogen sind entfernt.

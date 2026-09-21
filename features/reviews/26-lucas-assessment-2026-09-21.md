# Assessment: Lucas’ MLP/MVP-Briefing

Stand: 21. September 2026. Referenz: Lucas’ E-Mail vom 9. September, bereitgestelltes PDF mit zwölf Seiten einschließlich Mockups.

## Ergebnis

Für alle acht Bausteine existieren Implementierungen. Die funktionale Vollständigkeit ist jedoch noch nicht erreicht: Journalistenempfehlungen, die Verbindung der Text- und Prüfverfahren sowie die Reihenfolge von Kundenmail und Aktivierung bleiben zu verbessern.

**Klargestellter Auftrag:** Lucas pflegt Kundeninhalte, Belege, Kontakte und Vertragsziele separat ein. Leere Profile oder fehlende Vertragswerte sind deshalb keine Implementierungslücken. Bewertet wird, ob das Tool die benötigten Eingabe-, Verarbeitungs- und Arbeitsfunktionen bereitstellt.

Die nächsten Schritte sollten die verbleibenden Funktionslücken schließen und den vollständigen Ablauf mit repräsentativen Testdaten prüfen. Das kann unabhängig von Lucas’ Befüllung erfolgen. Eine prozentuale Fertigstellungszahl wäre ohne gewichtete Abnahmekriterien irreführend.

## Grundlage und Prüfgrenzen

- PDF vollständig gelesen; eingebettete Desk-, Opportunity- und Medien-Mockups zusätzlich visuell geprüft.
- Aktuellen Implementierungsstand in `codex/react-desk`, Commit `9bb85ad`, geprüft. Das ursprüngliche Arbeitsverzeichnis auf `main` liegt auf einem anderen Stand und wäre allein keine geeignete Bewertungsgrundlage.
- Railway meldet Deployment `57ea106d-159f-46b3-8e2e-ad39fdcae0cc` vom 19. September als erfolgreich. Acht Backend-Dateien des Hintergrundentwurfs stimmen mit dem geprüften Checkout überein. Datenbankschema `0062_default_drafts`, SQLite-Integritätsprüfung erfolgreich.
- Produktionszahlen am 21. September ausschließlich lesend abgefragt, mit `PRAGMA query_only=ON`. Keine Entwürfe neu erzeugt, keine Kundendaten verändert und nichts versendet.
- 55 gezielte Tests für Profil, Journalisten, Opportunity-Workspace und Aktivierung erfolgreich. Der erste Lauf verwendete versehentlich Node 20 und scheiterte in vier React-Rendering-Tests am Build; mit der vorgesehenen Node-Version 22.22.3 bestanden alle 55 Tests.
- Keine neue vollständige Browserabnahme und keine neuen Live-Anfragen an KI- oder Nachrichtenanbieter. Ältere erfolgreiche Live-Tests werden unten ausdrücklich als solche bezeichnet.

## Abgleich der acht Bausteine

| Baustein / PDF | Bereits umgesetzt | Noch offen oder eingeschränkt | Bewertung |
| --- | --- | --- | --- |
| **1. Client Twin**, S. 1–2 | Kundenverwaltung; 339 Fragebogenfelder plus 17 bestehende Profilfelder; 127 Pflichtfelder; XLSX-/CSV-Import mit Vorschau; KI-Antwortvorschläge; mehrere Aussagen pro Feld; Quelle, Stand, Confidence, Vertraulichkeit, Herkunft und externe Nutzung; Bearbeitung, Bestätigung, Verwerfen, Historie und Vollständigkeit. | Website-/Dokumentenrecherche, Guide und Fragebogen sind mehrere Schritte, noch kein durchgehend geführtes Onboarding. Dokumentimport unterstützt PDF/TXT/Markdown, kein DOCX. | **Geforderte Profilfunktionen vorhanden; Onboarding vereinfachbar.** |
| **2. Desk**, S. 2–3 | Aktive Kunden, monatliche Actions, Quartalszusage vs. Lieferung, erkannte und entwickelte Opportunities, Entscheidungen, laufende Arbeit und Profillücken. Entwürfe werden nicht als Lieferung gezählt. | Vertragsziele können eingetragen werden. Die rechte Intelligence-Spalte aus dem Mockup fehlt. Sie ist ein visueller Wunsch, kein fehlender Grundbaustein des beschriebenen Dashboards. | **Kern umgesetzt.** |
| **3. Ask RAUTE**, S. 3 | Globaler, Kunden-, Opportunity- und Asset-Kontext; Profil und Kommunikationsguide; Quellen, Auswahl und historische Prüfungen; Streaming und getrennte Gesprächskontexte. Zugang oben rechts. | Antworten sind beratend. Textänderungen werden nicht direkt als geprüfte Asset-Version übernommen; Gespräche liegen im Browser-Session-Speicher, nicht als gemeinsames dauerhaftes Teamwissen vor. Direkte Übernahme wäre eine sinnvolle Erweiterung, aber im Briefing nicht ausdrücklich als Speicherfunktion gefordert. | **MVP-Kern umgesetzt.** |
| **4. Opportunity Intelligence**, S. 3–5 | Automatische Erkennung und aktive Entwicklung ohne einzelne News. Entwicklung berücksichtigt Profil/Positionierung und recherchiert Markt, Wettbewerb, Politik/Regulierung, Studien/Daten und Medienlage. Quellen und Recherchefehler werden gespeichert. | Recherche beruht auf begrenzten Trefferlisten und Auszügen. Entwicklung braucht derzeit einen vom Nutzer eingetragenen Recherchefokus. Eine vollständige Abnahme mit repräsentativen Testdaten und aktuellen Rechercheergebnissen steht aus; fehlende produktive Nutzung ist keine Funktionslücke. | **Beide Modi gebaut; automatische Fokuswahl und Abnahme offen.** |
| **5. Opportunity Workspace**, S. 5–6 | Anlass, Relevanz, Timing, Quellen, Risiken, Storylines, Sprecher, Kontakte, ACTIVATE und Aktivitätsverlauf. | Bei erkannten/älteren Anlässen sind einzelne Felder generische Rückfalltexte, z. B. „Aktuelles Nachrichtenfenster“. Moderne Opportunities und bisherige Impuls-/Freigabeseiten bleiben unterschiedliche Arbeitswege. | **Weitgehend umgesetzt, noch nicht durchgängig konsolidiert.** |
| **6. Generate Asset / Activation**, S. 6–7 | Alle zehn verlangten Formate einschließlich Kundenmail, individuellem Pitch und eigenem Auftrag. Gespeicherte Storyline, Sprecher, Profil, Medium/Kontakt, Artikel und Beziehungshistorie gehen in die Erstellung ein. Editor, Prüfungen, automatische Pressemitteilungen und eigener Composer vorhanden. | Kundenfreigabe führt beim Pitch auf den bisherigen Workflow. Für erkannte Opportunities verlangt die API zunächst ACTIVATE, bevor selbst die Kundenmail erstellt werden kann; Lucas beschreibt die Kundenmail vor der eigentlichen Aktivierung. Automatisch erstellte Texte sind nicht vollständig in denselben Editor-/Prüfverlauf eingebunden. | **Formate umgesetzt; zusammenhängender Freigabeablauf teilweise offen.** |
| **7. Media & Journalist Intelligence**, S. 7–9 | Kontaktprofile mit Ressort, Themen, Spezialgebieten, Storytypen, Unternehmen, Präferenzen und Beziehungsstatus; Artikelhistorie; Kontakt-/Antwortverlauf. Aktuelle Recherche je Opportunity über konfigurierte Anbieter mit sechs Wochen Zeitfenster, Artikelbelegen und Begründung. | Ranking zählt vor allem passende Stichwörter/Artikel. Keine tiefe, quellenbasierte Bewertung des konkreten Angles, aktueller Interessen, Wettbewerberbezug und empfohlenen Formats im Sinne von Lucas’ Beispiel. Artikel-/Anbieterabdeckung ist begrenzt. | **Grundlage vorhanden; größte fachliche Funktionslücke.** |
| **8. Quality / Evidence Light**, S. 9–10 | Im Opportunity-Editor: Aussagenklassifikation, verknüpfte Profilbelege und Quellen, Alterswarnungen, Widersprüche, No-Gos und veraltete Prüfungen nach Änderungen. Unternehmensclaims werden nicht automatisch zu bestätigten Fakten. | Automatische Pressemitteilungen und eigener Composer nutzen bestehende Gegenlese-/Guide-Prüfungen statt desselben aussagenweisen Prüfdatensatzes. Aktualitätsgrenzen sind pauschal; semantische Prüfungen brauchen menschliche Kontrolle. | **Gefordertes Minimum im neuen Editor vorhanden; noch nicht einheitlich für alle Textwege.** |

Codebelege: [Twin](../../newspulse/src/newspulse/twin.py), [Import](../../newspulse/src/newspulse/twin_import.py), [KI-Import](../../newspulse/src/newspulse/twin_ai.py), [Desk](../../frontend/src/components/DeskPage.jsx), [Ask-Kontext](../../newspulse/src/newspulse/assistant_context.py), [Opportunity-Entwicklung](../../newspulse/src/newspulse/opportunity_development.py), [Workspace](../../newspulse/src/newspulse/workspaces.py), [Aktivierung](../../newspulse/src/newspulse/activation.py), [Journalisten](../../newspulse/src/newspulse/journalists.py), [Belegprüfung](../../newspulse/src/newspulse/asset_evidence.py).

## Produktionsbeobachtungen – keine Bewertung der Inhaltsbefüllung

Die folgenden Zahlen dokumentieren den Prüfstand. Profil-, Kontakt- und Vertragsbefüllung liegt bei Lucas und ist keine Voraussetzung für die technische Fertigstellung. Fehlende Nutzung begrenzt lediglich die vorhandene Live-Evidenz. Der dokumentierte Erzeugungsfehler bleibt dagegen ein technischer Befund.

| Befund am 21.09.2026 | Bedeutung |
| --- | --- |
| 7 aktive Kunden; jeweils **1 von 127 Pflichtfeldern**, jeweils **0 unabhängig bestätigte Aussagen** | Die Eingabe- und Prüfwerkzeuge sind vorhanden; die Befüllung übernimmt Lucas. Insgesamt gibt es 94 Profil-Aussagen; die niedrige Pflichtfeldquote bedeutet nicht, dass überhaupt keine weiteren Informationen gespeichert sind. |
| Quartalszusage bei allen sieben Kunden leer | Der Desk kann den zugesagten Leistungsumfang nicht beurteilen. Das ist Lucas’ spätere Konfiguration, kein fehlendes Zählverfahren. |
| 1 Kontakt, 0 zusätzliche Journalistenprofile, 0 gespeicherte opportunitybezogene Journalistenrecherchen | Der anspruchsvollste Teil des Briefings ist produktiv noch nicht mit einer nutzbaren Datenbasis erprobt. |
| 0 Datensätze der neuen Opportunity-Entwicklung, 2 Workspaces, 1 abgeschlossener Asset-Lauf, 3 Workspace-Ereignisse | Kein Nachweis einer breiten Nutzung des neuen Gesamtworkflows. Das bedeutet nicht, dass ältere Impuls- und Newsfunktionen keine Ideen erzeugt hätten. |
| 79 gespeicherte Pressemitteilungen, 79 Hintergrundjobs erfolgreich, 1 fehlgeschlagen | Hintergrundvorbereitung funktioniert überwiegend, aber nicht lückenlos. |
| Neuester Zalando-Entwurf, Angle 81: fehlgeschlagen, weil auch nach zweitem Versuch kein Boilerplate-Absatz mit „Über“ begann | Konkretes aktuelles Zuverlässigkeitsproblem. Die anderen sechs neuesten Kundenentwürfe sind vorhanden. Keine automatische Wiederholung während dieses Assessments ausgelöst. |
| 0 freigegebene Pressemitteilungen | Vorbereitete Texte sind keine ausgelieferten Leistungen. |

Der KI-Profilimport wurde am **18. September** mit Arrakis.finance erfolgreich live geprüft: 51 Antwortvorschläge in etwa sechs Minuten. Die Vorschläge wurden dabei bewusst nicht übernommen. Das belegt eine erfolgreiche Ausführung nach der Reparatur, nicht die dauerhafte Verfügbarkeit einer alten Vorschau oder vollständige Profile. Quelle: [Deploymentprotokoll](26-railway-deployment.md).

## Übergreifende Lücken im Kernworkflow

### Ein Text, ein Workspace, eine Prüfung

`activation.read()` lädt die bearbeitbaren Texte über `OpportunityAssetRun`. Der Hintergrundprozess speichert dagegen über `assets.produce()` direkt ein Asset. Solche Texte können im allgemeinen Asset-/Aktivitätskontext verlinkt sein, erscheinen aber nicht automatisch mit demselben Bearbeitungs- und Aussagenprüfverlauf im Activation-Editor. Auch der eigene Composer ist ein separater Erstellungsweg.

**Nötig:** Alle Entwürfe derselben Opportunity zusammenführen; dieselben Quellen, Prüfergebnisse, Versionen und Freigabeschritte zugänglich machen. Existierende Texte dabei übernehmen, nicht neu erzeugen.

Belege: [Activation-Lesemodell](../../newspulse/src/newspulse/activation.py), [Hintergrundentwürfe](../../newspulse/src/newspulse/default_drafts.py), [Composer](../../newspulse/src/newspulse/web/routes/custom_drafts.py), [Activation-API](../../newspulse/src/newspulse/web/routes/activation_api.py).

### Action-Historie ist vorhanden; Rückführung von Wissen fehlt

Aktivierung, Auswahl, Texterstellung und Prüfung erzeugen Ereignisse. Freigegebene Leistungen und externe Leistungen werden separat gezählt. Kontaktverläufe und Antworten sind ebenfalls vorhanden. Diese Anforderungen sind nicht neu zu bauen.

Eine allgemeine Strecke „Aus Gespräch/Antwort/Action wurde neues Wissen gewonnen → Vorschlag für Profil oder Journalistenpräferenz → menschlich prüfen → übernehmen“ habe ich nicht gefunden. Lucas nennt diese Rückführung auf S. 12 ausdrücklich als idealen Zusatz. Sie sollte deshalb nach dem Kernworkflow kommen.

Ideenwiederholungen werden durch frühere Titel im Prompt und exakten Titelvergleich reduziert. Im bisherigen Pitchsystem gibt es Hinweise auf bereits angesprochene Empfänger derselben Geschichte. Eine verlässliche semantische Wiederholungserkennung über umformulierte Ideen und sämtliche Workflows hinweg ist damit noch nicht erreicht.

Belege: [Actions](../../newspulse/src/newspulse/web/routes/workbench.py), [Pitchhistorie](../../newspulse/src/newspulse/pitch.py), [Outreach](../../newspulse/src/newspulse/outreach.py), [Entwicklungslogik](../../newspulse/src/newspulse/opportunity_development.py).

### UI: deutlich näher am Ablauf, aber noch zwei Produktgenerationen

Desk/Clients/Assets, Ask RAUTE oben rechts sowie die konsolidierten Kundenreiter sind vorhanden. Profil statt Twin, Kontakte statt Journalisten und zusätzliche Archiv-/KI-Sichtbarkeitsreiter entsprechen späteren Nutzerentscheidungen. Diese Abweichungen von Lucas’ ursprünglichen Namen sind keine Fehler.

Navigation, Archiv, Einstellungen und das konsolidierte Profil sind inzwischen React. Einige Fachseiten, insbesondere Teile des bisherigen Impuls-/Freigabeworkflows, bleiben Python/Jinja mit React-Komponenten. React allein ist kein Abnahmekriterium des Briefings.

Zum Mockup fehlen vor allem die kompakte Medienempfehlung mit ausgewähltem Kontakt daneben sowie die Desk-Intelligence-Spalte. Wichtiger als deren Nachbau ist, die vorhandenen Wege zu reduzieren: Opportunities bietet weiterhin Chancen/Impulse/Issues/Plan als Ansichten; global existieren unter „Weitere Werkzeuge“ noch Heute und Portfolio. Das ist Restkomplexität, kein vollständig fehlendes Menü.

Die Prozentwerte für Medien-Fit und Qualität in Lucas’ Mockups sollten nicht ohne belastbare Berechnung nachgebaut werden. Quellenbasierte Begründungen erfüllen den Zweck besser.

Belege: [React-Navigation](../../frontend/src/shell.jsx), [Profil](../../frontend/src/platform/ProfilePage.jsx), [Workspace-Oberfläche](../../frontend/src/components/OpportunitiesPage.jsx), [Texteditor](../../frontend/src/components/ActivationPanel.jsx).

## Empfohlene Reihenfolge und Abnahmekriterien

| Priorität | Arbeitspaket | Fertig, wenn … |
| --- | --- | --- |
| **P1** | Funktionsabnahme mit repräsentativen Testdaten vorbereiten | Ein isolierter Testkunde deckt Fragebogen, Belege, Sprecher, Positionierung, No-Gos, Vertragsziele und Kontakte ab. Erstellen, Bearbeiten, Importieren und Weiterverarbeiten funktionieren ohne Befüllung echter Kundenakten. |
| **P0** | Zuverlässigkeit der Erzeugung abschließen | Der Zalando-Fehler ist nachvollzogen und behoben; fehlgeschlagene Entwürfe sind sichtbar und gezielt wiederholbar; vorhandene Texte bleiben erhalten. |
| **P1** | Arbeitswege und Qualitätsprüfung vereinheitlichen | Automatische Pressemitteilung und manuell erzeugter Text erscheinen im selben Opportunity-Workspace mit derselben Belegprüfung; Kundenmail, Kundenzustimmung, Aktivierung und spätere Freigabe sind verständliche getrennte Schritte. |
| **P1** | Journalistenempfehlung fachlich verbessern | Für einen realen Anlass werden konkrete aktuelle Artikel genannt und daraus Themen-/Angle-Fit, passendes Format und Ansprache begründet; Kontaktverlauf wird berücksichtigt; fehlende Treffer werden nicht als Publikationsfreiheit ausgegeben. |
| **P1** | Vollständigen Funktionsablauf abnehmen | Ein erkannter und ein aktiv entwickelter Anlass durchlaufen mit Testdaten Profil → Begründung → Medienrecherche → individueller Pitch → Claims-Prüfung → Action-Historie. Kundenmail vor Aktivierung möglich; Recherchefokus auf Wunsch aus dem Profil ableitbar; kein Entwurf zählt als Lieferung. Reale Anbieter separat prüfen; Fixtures belegen allein keine Recherchequalität. |
| **P2** | Erkenntnisse und Wiederholungen besser nutzen | Neue Erkenntnisse können mit Herkunft zur Übernahme vorgeschlagen werden; ähnliche frühere Ideen/Pitches werden workflowübergreifend angezeigt. |
| **P2** | Verbleibende Oberfläche vereinfachen | Ein klarer Weg je Aufgabe; Medienauswahl und Belege direkt beim Text; keine konkurrierenden alten und neuen Einstiegspunkte. |

## Bewusst kein fehlender MVP-Umfang

Lucas stellt auf S. 1 und 12 Ops, Sales, Customer Success, Finance, Management, große Performance-Messung, komplexes Relationship Scoring, GEO und automatischen Versand zurück. Diese Dinge sind für die Abnahme dieses Briefings nicht nachzubauen. Bereits vorhandene Zusatzfunktionen können bestehen bleiben, sollten aber nicht den Kernworkflow dominieren.

**Empfehlung:** Nächster Meilenstein ist ein funktional vollständiger und getesteter PR-Ablauf. Vorrang haben zuverlässige Erzeugung, einheitliche Text- und Prüfwege, Kundenmail vor Aktivierung und bessere Journalistenempfehlungen. Profilbefüllung durch Lucas läuft separat. Die Rückführung neuer Erkenntnisse bleibt der im Briefing als optional beschriebene Folgeschritt.

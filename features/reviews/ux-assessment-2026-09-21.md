# UX-Prüfung und Vorschlag zur Vereinfachung

21. September 2026. Ziel: weniger Entscheidungen und klarere Arbeitswege bei unverändert verfügbarem Funktionsumfang.

## Durchgeführte Browserprüfung

Playwright/Chromium gegen eine isolierte lokale Instanz des aktuellen Frontends mit drei synthetischen Mandanten. Ansichten Clients, Profil und Opportunity auf 1440 × 960 und 390 × 960 Pixeln geprüft. Im Profil eine Aussage geöffnet; im Workspace Strategie und Texterstellung geöffnet. Keine KI-Aufträge oder Produktionsänderungen ausgeführt. Schreibanfragen im Browser blockiert.

- Keine JavaScript-Seitenfehler und kein horizontaler Seitenüberlauf in diesen Ansichten.
- Das Profil ist im Testszenario 6.800 Pixel auf Desktop und 9.121 Pixel auf Mobilgeräten hoch, obwohl zunächst nur fünf Fragebogenfelder angezeigt werden.
- Der Editor einer einzelnen Aussage zeigt zwölf Eingabefelder. Auf Mobilgeräten ist das Formular allein etwa 1.446 Pixel hoch.
- Opportunities hat neben der globalen Navigation Kundenreiter, eine Ansichtsauswahl und fünf Workspace-Reiter.
- Bei drei Kunden stehen sechs Verwaltungsbuttons dauerhaft auf den Karten: je Bearbeiten und Löschen.
- Der Textgenerator bietet zehn Formate als Dropdown. Der Einstieg in den eigentlichen Text liegt unter mehreren Ebenen von Überschriften und Navigation.

Die Messwerte hängen von Testdaten und Bildschirmgröße ab. Diese Prüfung belegt die beobachtete Struktur und das Rendering, nicht die subjektive Zufriedenheit realer Anwender oder die Qualität generierter Inhalte.

## Konkrete Gestaltung

| Bereich | Empfohlene Änderung | Funktionsumfang erhalten durch … |
| --- | --- | --- |
| Profil | Zunächst lesbares Kundenprofil mit kompakten Themenabschnitten. Bearbeitung direkt an der betreffenden Aussage. | Aussage und Quelle zuerst; weitere Metadaten bei Bedarf öffnen. Herkunft, Vertraulichkeit und externe Nutzbarkeit bleiben sichtbar, auch wenn ihre Eingaben eingeklappt sind. Alle Fragen bleiben durchsuchbar. |
| Opportunities | Ein Arbeitsbereich für Anlass, Text und relevante Belege. Klare nächste Aktion statt mehrerer gleichwertiger Navigationsleisten. | Medienrecherche und Sprecherwahl als kontextbezogene Werkzeuge im selben Arbeitsbereich; Historie als ergänzender Bereich. Nachrichten, Issues und Plan behalten ihre Funktionen, werden aber als Inhalte/Filter eingebunden statt konkurrierende Oberflächen zu bilden. |
| Texterstellung | Vorhandene Pressemitteilung direkt zeigen. Kundenmail, Pitch oder eigener Text über wenige klare Vorlagen erreichbar. | Weitere Formate bleiben in einer zusätzlichen Auswahl verfügbar. Quellenprüfung und Freigabestatus bleiben beim Text. |
| Buttons | Eine hervorgehobene Hauptaktion pro aktivem Arbeitsbereich: etwa „Text erstellen“, „Änderungen speichern“ oder „Freigabe vorbereiten“. | Sekundäre Aktionen ruhig darstellen; seltene Verwaltungsaktionen in ein beschriftetes Aktionsmenü. Status darf nicht wie ein Button aussehen. |
| Clients | Kundenkarten führen ins Mandat; Verwaltung bekommt einen ruhigen gemeinsamen Einstieg. | Bearbeiten und Löschen bleiben erreichbar; Löschen behält seinen Bestätigungsdialog. |
| Visuelle Hierarchie | Weniger ineinander verschachtelte Karten, kürzere Einleitungen, größere zusammenhängende Arbeitsflächen. | Quellen, Unsicherheit und Fehler nicht entfernen, sondern dort anzeigen, wo sie für die Entscheidung relevant sind. |

Nicht bloß jedes zusätzliche Element in „Mehr“-Menüs verschieben: Das reduziert sichtbare Buttons, kann aber die Zahl der Klicks und die Suche erhöhen. Häufige Aufgaben sollen direkt erreichbar werden; seltene Optionen dürfen zurücktreten.

## Prüfung eines überarbeiteten Entwurfs

Erst Profil und Opportunity als zusammenhängenden Prototyp umsetzen, dann das Muster auf weitere Ansichten übertragen. Vergleich auf denselben Testdaten:

1. Einen Kunden öffnen, eine Aussage ändern und ihre Quelle prüfen.
2. Eine Chance verstehen und eine Kundenmail vorbereiten.
3. Einen passenden Kontakt wählen und einen individuellen Pitch bearbeiten.
4. Einen Prüfhinweis nachvollziehen und die Freigabe vorbereiten.

Playwright prüft Erreichbarkeit, Tastaturbedienung, Fokus, erhaltene Eingaben, Fehlerzustände, Navigation und responsive Darstellung. Klickfolgen und Scrollwege werden vorher/nachher verglichen. Ein zusätzlicher Accessibility-Check mit axe-core ist sinnvoll, wurde in dieser ersten Prüfung aber nicht ausgeführt.

Lucas und Raphael sollten anschließend dieselben Aufgaben kurz ohne Erklärung durchgehen. Dabei interessieren vor allem Suchpausen, Fehlklicks und Stellen, an denen unklar ist, welcher Schritt als Nächstes folgt. Automatisierte Tests ersetzen diese Nutzerbeobachtung nicht.

Lokale Prüfarbeitsdateien: `/tmp/raute-ux-assessment/results.json` und Screenshots im selben Verzeichnis; Testskript `/tmp/raute-browser-check/ux-audit.cjs`. Diese temporären Dateien sind kein dauerhaftes Testarchiv.

## Umgesetzt und geprüft

- Profil: kompakte Aussagenliste mit Editor direkt an der Frage. Antwort und Quelle zuerst; Herkunft, Vertraulichkeit und externe Nutzbarkeit bleiben sichtbar. Weitere Metadaten sind aufklappbar. Firmenangaben, Kommunikations-Guide, Wettbewerb und Marktumfeld bleiben vollständig erreichbar. Bestehende Sprunglinks öffnen die zugehörigen Bereiche.
- Opportunity: fünf zusätzliche Workspace-Reiter durch Abschnitte im selben Arbeitsbereich ersetzt. Vorbereitete Pressemitteilungen erscheinen direkt, auch vor dem ersten Speichern der Workspace-Auswahl. Das Laden ist ausschließlich lesend. Anlass, Quellen, Sprecher, Kontakte und Historie bleiben erreichbar.
- Texterstellung: Kundenmail, Pitch und eigener Text direkt auswählbar; alle zehn Formate bleiben verfügbar. Ungespeicherte Kontextänderungen verhindern die Erstellung mit veralteter Auswahl. Gespeicherte Texte, Belegprüfung und Freigabewege bleiben erhalten.
- Clients: Bearbeiten und Löschen unter einem beschrifteten „Verwalten“-Menü; bestehender Löschdialog bleibt erhalten. Gemeinsame Buttons und mobile Bedienflächen vereinheitlicht.
- Chancen, Impulse, Issues und Plan sind direkt verlinkt. Ihre fachlichen Datenmodelle und Arbeitsabläufe wurden in diesem Schritt nicht zusammengeführt. Auch das backendübergreifende Belegmodell und semantisches Kontaktmatching sind keine Bestandteile dieser UI-Änderung.

Vergleich mit denselben synthetischen Daten: Profilhöhe Desktop 6.800 → 2.045 Pixel, mobil 9.121 → 2.845 Pixel. Aussage-Editor zunächst drei statt zwölf Eingabefelder. Die Messung beschreibt dieses Testszenario, keine pauschale Verbesserung jeder Seite.

Playwright prüfte Desktop und Mobilgerät, Tastaturbedienung der Kundenverwaltung, Abbruch des Löschdialogs ohne Schreibanfrage, Inline-Bearbeitung einschließlich Metadaten, Sprunglinks in eingeklappte Bereiche, lesendes Laden gespeicherter Pressemitteilungen und die Sperre bei ungespeicherter Storyline. Eingaben blieben beim Speichern des Kontextes erhalten. Lokale Schreibtests verwendeten ausschließlich eine isolierte Datenbank. Keine KI-Generierung wurde ausgelöst.

axe-core meldete keine WCAG-2A/AA- oder WCAG-2.1-AA-Verstöße in den zehn geprüften Zuständen (Clients, Profil, Aussage-Editor, vorbereitete Pressemitteilung, Workspace-Werkzeuge jeweils auf Desktop und Mobilgerät). Keine JavaScript-Seitenfehler oder horizontaler Überlauf. Dies ersetzt keine vollständige Accessibility-Prüfung oder Beobachtung realer Nutzer.

Prüfarbeitsdateien: `/tmp/raute-ux-after/results.json`, `/tmp/raute-ux-after/interactions.json` und Screenshots im selben Verzeichnis. Automatisierte Regressionstests liegen im Repository.

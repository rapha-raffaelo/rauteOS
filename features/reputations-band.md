# Das Band: die Lage, das Issue, die Szenarien und die Entscheidung

prefix: RIS

**Type:** feature
**Complexity:** 5
**Estimated Duration:** ~3 Wochen
**Risk:** medium
**Scope:** newspulse, risiko, issues, stakeholder, entscheidung
**Test Strategy:** Unit-Tests über die Ablesung gegen die bestehende In-Memory-SQLite-Fabrik, mit eingespeister Uhr statt gepatchtem Zeitmodul; die Stufenrechnung, die Richtung und die Abweichung vom eigenen Median werden gegen von Hand gezählte Fixtures geprüft und nie gegen sich selbst; die Falsch-Alarm-Regel bekommt einen eigenen Test, der eine einzelne negative Meldung einspeist und prüft, dass das Mandat auf Beobachtung stehen bleibt, weil das die teuerste Fehlleistung dieser Funktion wäre; ein Test, dass eine zweite Ablesung am selben Tag die erste aktualisiert statt eine zweite anzulegen; ein Test je erzeugtem Papier, dass ein fehlender Beleg zur Auslassung führt statt zu einer erfundenen Zahl, Person oder Frist, mit eingespeister Erzeugung; ein Test, dass ein Auslöser genau einmal feuert und nach dem Feuern nicht erneut; ein Strukturtest über die neuen Prompt-Dateien, dass sie ihre Blöcke komponieren und keinen davon ausschreiben; `TestClient`-Abdeckung für das Band einschließlich des Zustands, in dem jedes Mandat ruhig ist, für das Register einschließlich des leeren Registers, für die Stakeholder-Karte und für das Entscheidungspapier; Golden-File-Test auf das gerenderte Entscheidungspapier eines gesäten Issues. Kein Test ruft ein Modell auf und kein Test geht ins Netz.

## Context

Das Werkzeug beantwortet die Frage, was heute passiert ist, inzwischen sehr genau.
Es findet die Berichterstattung, ordnet sie einem Mandat zu, bewertet Tonalität und
Wichtigkeit, gruppiert sie zu Stories mit Aufgriffszahl, und über der Schwelle
schlägt es seit Kurzem eine Krise vor, die als Objekt mit Anfang, gerechneter Stufe
und Ende geführt wird.

Was es nicht beantwortet, ist die Frage davor: wie steht es eigentlich um dieses
Mandat. Der einzige Ort, an dem heute so etwas wie ein Zustand steht, ist das rote
Kärtchen in der Seitenleiste, und das zählt die Alarme des laufenden Tages. Um
Mitternacht ist es wieder weg. Ein Vorwurf, der am Montag, am Mittwoch und am
Freitag auftaucht, erscheint als drei Kärtchen an drei Tagen und nie als eine Sache,
die drei Wochen alt wird. Genau das ist aber der Unterschied zwischen normaler
Kritik und einem Issue, und das Erkennen dieses Unterschieds ist der Zweck, für den
diese Engine beschrieben wurde.

Damit fehlt zwischen zwei Zuständen alles. Unterhalb der Krisenschwelle gibt es das
Kärtchen von heute. Oberhalb gibt es die Krisenseite. Dazwischen liegt der Bereich,
in dem eine Agentur den größten Teil ihrer Zeit verbringt: etwas ist im Gange, es
ist noch keine Krise, jemand muss sich merken, dass es läuft, und in vier Wochen
muss nachvollziehbar sein, seit wann es läuft und was sich verändert hat.

Der Auftrag benennt zugleich die Gefahr, die dabei entsteht: „Die Engine soll
ausdrücklich nicht bei jeder negativen Erwähnung Alarm auslösen." Ein Band, das
jeden Morgen rot ist, ist nach zwei Wochen ein Band, das niemand mehr liest, und es
hätte dann aktiv geschadet, weil es die Aufmerksamkeit verbraucht, die für den einen
Morgen gebraucht wird, an dem es zu Recht rot ist. Deshalb wird jede Stufe in diesem
Band gerechnet und nicht geschätzt, und deshalb steht die Regel, unter der ein
Mandat die unterste Stufe verlässt, ausdrücklich in der Abnahme: eine einzelne
negative Meldung reicht nie.

Vier Größen dafür stehen bereits in gespeicherten Zeilen und müssen nicht beschafft
werden: die Zahl der unabhängigen Medien an einer Story, die Reichweitenklasse des
Mediums aus der bestehenden Rangliste, der Anteil negativer Tonalität, und ob das
Mandat namentlich genannt ist. Die Krisenstufe rechnet heute schon daraus. Dieses
Band setzt dieselbe Rechnung eine Etage tiefer an und lässt sie über die Zeit
laufen, womit zwei Dinge geschenkt entstehen: eine Richtung, weil es eine
Vorgeschichte gibt, und eine Abweichung, weil ein Mandat gegen seinen eigenen Median
gemessen werden kann statt gegen einen Wert, der für alle gilt.

Was hier bewusst nicht gebaut wird, ist der zweite Teil des Auftrags. Social
Listening, parlamentarische Vorgänge und Behördenmonitoring sind eigene
Datenquellen mit eigenen Schnittstellen, Lizenzfragen und einem eigenen
Abgleichsweg, weil eine Drucksache kein Unternehmen nennt, sondern eine Branche.
Das ist eine eigene Spezifikation und keine Story hier. Dieses Band liest, was das
Werkzeug bereits sieht, und ist so gebaut, dass eine weitere Signalquelle später
eine Eingangsgröße mehr ist und keine zweite Oberfläche.

## Inventory

- **INV-01**: Public Affairs Ribbon auf dem Dashboard
- **INV-02**: Reputation & Crisis Engine
- **1**: Reputationsrisiken kontinuierlich beobachten
- **2**: Issues frühzeitig erkennen
- **3**: Signalstärke bewerten
- **4**: False Positives reduzieren
- **5**: Krisenlevel klassifizieren
- **6**: Krisendynamik erkennen
- **7**: Krisenverlauf prognostizieren
- **8**: Szenarien entwickeln
- **9**: Trigger für Szenarien definieren
- **10**: Faktenlage aufbauen
- **11**: Chronologie erstellen
- **12**: Source of Truth für die Krise definieren
- **13**: Widersprüche erkennen
- **14**: Informationslücken erkennen
- **15**: Stakeholder identifizieren
- **16**: Stakeholder priorisieren
- **17**: Informationsbedürfnisse je Stakeholder bestimmen
- **18**: Kommunikationsreihenfolge empfehlen
- **19**: Holding Statements vorbereiten
- **20**: Krisenstatements vorbereiten
- **21**: Q&As für Krisensituationen entwickeln
- **22**: Worst Case Questions entwickeln
- **23**: Antwortlogik entwickeln
- **24**: Messaging House für Krisen entwickeln
- **25**: Unternehmenshaltung bestimmen
- **26**: Reaktionsoptionen entwickeln
- **27**: Don't Feed the Story erkennen
- **28**: Reaktionsgeschwindigkeit bestimmen
- **29**: Medienanfragen priorisieren
- **30**: Journalistenprofile im Krisenfall nutzen
- **31**: Mediennarrative erkennen
- **32**: Narrative Shift erkennen
- **33**: Falschinformationen erkennen
- **34**: Gerüchte bewerten
- **35**: Social-Media-Dynamik bewerten
- **36**: Medien- und Social-Dynamik verbinden
- **37**: Politische Eskalation erkennen
- **38**: Regulatorische Eskalation erkennen
- **39**: Mitarbeiterkrisen berücksichtigen
- **40**: Executive Reputation beobachten
- **41**: Produktkrisen unterstützen
- **42**: Cyber- und Datenschutzkrisen unterstützen
- **43**: M&A- und Transaktionsrisiken unterstützen
- **44**: Restrukturierungs- und Insolvenzkommunikation unterstützen
- **45**: Krisenkommunikationsplan erstellen
- **46**: Krisenrollen definieren
- **47**: Eskalationswege definieren
- **48**: Krisenbereitschaft prüfen
- **49**: Crisis Readiness Score erstellen
- **50**: Krisensimulationen vorbereiten
- **51**: Medienfragen simulieren
- **52**: Stakeholderreaktionen simulieren
- **53**: Krisensimulation auswerten
- **54**: Dark Sites und vorbereitete Krisenassets verwalten
- **55**: Issue Register führen
- **56**: Risk Heatmap erstellen
- **57**: Reputationsbaseline aufbauen
- **58**: Reputationsveränderungen erkennen
- **59**: Issue zu Opportunity unterscheiden
- **60**: Kritische Branchenentwicklungen für Kunden übersetzen
- **61**: Konkurrenzkrisen beobachten
- **62**: Crisis War Room unterstützen
- **63**: Entscheidungsvorlagen erstellen
- **64**: Krisenkommunikation über Kanäle koordinieren
- **65**: Aktualisierungsrhythmus definieren
- **66**: Stakeholderreaktionen nach Kommunikation beobachten
- **67**: Wirkung einzelner Krisenmaßnahmen bewerten
- **68**: Strategie während einer Krise anpassen
- **69**: Krisenende erkennen
- **70**: Recovery Phase vorbereiten
- **71**: Post Crisis Review erstellen
- **72**: Crisis Learnings speichern
- **INV-03**: Cross-Functional Crisis Handoff
- **INV-04**: Crisis Decision Packet
- **INV-05**: Prebunking und Misinformation Preparedness

## Decisions

### DEC-1: Wie liest sich das Band?  [mock]
**Status:** open
**Recommend:** B
**Locks as:** das Layout, gegen das das Band gebaut und geprüft wird
- **A · Eine Zeile je Mandat** Das ganze Portfolio steht immer da, ruhige Mandate blass. Vollständig, und man sieht auf einen Blick, dass nichts übersehen wurde. Es kostet an einem normalen Morgen den halben oberen Bildschirm für die Aussage, dass nichts los ist.
  `features/mocks/band-zeilen.html`
- **B · Nur die auffälligen, dahinter eine Zählzeile** Ein Mandat erscheint erst, wenn es die unterste Stufe verlässt; der Rest steht als „neun Mandate ruhig" in einer Zeile. An einem normalen Morgen ist das Band eine Zeile hoch, und an dem Morgen, an dem etwas ist, ist es das Erste auf der Seite. Der Preis: die Abwesenheit einer Kachel ist eine Aussage, die man lesen können muss.
  `features/mocks/band-auffaellige.html`
- **C · Ein Balken über die volle Breite** Ein Streifen, in Segmente je Zustand geteilt, das Portfolio als Verhältnis. Sofort erfassbar und in der Sekunde wertlos, in der man wissen will, welches Mandat gemeint ist.
  `features/mocks/band-balken.html`

### DEC-2: Woraus entsteht der Zustand eines Mandats?  [options]
**Status:** locked
**Chosen:** A
**Recommend:** A
**Locks as:** die Rechenregel der Ablesung in RIS-01
- **A · Gerechnet aus gespeicherten Zeilen** Medienzahl, Reichweitenklasse, Tonalitätsanteil, namentliche Nennung, offenes Issue, offene Krise. Jede Stufe ist von Hand nachrechenbar, und zwar in genau der Stunde, in der jemand sie nachrechnen möchte. Es bedeutet auch, dass das Band nur sieht, was in Zeilen steht, und einen Unterton nicht erkennt, den ein Mensch im dritten Absatz gelesen hätte.
- **B · Ein Modell schätzt die Stufe** Liest die Beiträge und benennt die Lage, mit allem, was ein Modell an Kontext mitbringt. Liefert eine Zahl, die niemand nachrechnen kann, die zwischen zwei Tagen ohne neuen Anlass springt, und die vor einem Kunden nicht zu verteidigen ist.
- **C · Gerechnet, das Modell darf um eine Stufe korrigieren** Die Rechnung setzt die Stufe, ein Modell darf sie mit schriftlicher Begründung um genau eine Stufe heben oder senken. Fängt den Fall, den die vier Größen nicht sehen, und macht die Korrektur sichtbar. Es verdoppelt den Erklärungsaufwand für jede Stufe und schiebt die Frage, warum ein Mandat gestern gelb und heute grün war, in eine Modellantwort.

### DEC-3: Wer eröffnet ein Issue?  [options]
**Status:** locked
**Chosen:** A
**Recommend:** A
**Locks as:** die Regel, unter der ein Issue entsteht, in RIS-02
- **A · Das Werkzeug schlägt vor, ein Mensch eröffnet** Wiederholt sich ein Thema, erscheint ein Vorschlag mit der Begründung, worin die Wiederholung besteht. Sonst passiert nichts, bis jemand ihn annimmt. Dieselbe Regel, unter der eine Krise erklärt wird, und ein Fehlvorschlag kostet einen Klick.
- **B · Das Werkzeug eröffnet selbst** Über der Wiederholungsschwelle entsteht das Issue und läuft mit. Nichts geht verloren, auch wenn morgens niemand hinsieht, und das Register füllt sich innerhalb eines Monats mit Themen, die niemand je angefasst hat, womit es genau die Liste wird, die man nicht mehr liest.
- **C · Nur von Hand** Der Berater legt an, was er für ein Issue hält. Immer richtig und immer unvollständig, weil das Erkennen der Wiederholung über Wochen genau die Arbeit ist, die abgenommen werden soll.

### DEC-4: Wie kommt ein neues Signal an ein bestehendes Issue?  [options]
**Status:** locked
**Chosen:** B
**Recommend:** B
**Locks as:** der Zuordnungsweg in RIS-02
- **A · Mechanisch über Story und Thema** Teilt ein neuer Beitrag die Story-Gruppe oder das Thema eines offenen Issues, hängt er daran. Billig, deterministisch, testbar, und blind für denselben Vorwurf in anderen Worten, was der häufige Fall ist.
- **B · Mechanisch gefundene Kandidaten, das Modell entscheidet** Die Story- und Themenüberschneidung sammelt die Kandidaten ein, ein Modell entscheidet über Zugehörigkeit und schreibt einen Satz dazu, warum. Erkennt denselben Vorwurf in neuer Formulierung, und jede Zuordnung ist hinterher lesbar begründet. Kostet einen Modellaufruf je Kandidatenpaar und braucht die Regel, dass eine unbegründbare Zuordnung nicht gespeichert wird.
- **C · Von Hand zuordnen** Der Berater hängt an, was dazugehört. Fehlerfrei und in der Woche, in der es zählt, unerledigt.

### DEC-5: Woraus darf ein Szenario-Auslöser bestehen?  [options]
**Status:** locked
**Chosen:** A
**Recommend:** A
**Locks as:** die Auslöserregel in RIS-04
- **A · Nur maschinell prüfbare Bedingungen** Ein Auslöser wird aus einer geschlossenen Menge gewählt: ein zweites unabhängiges Medium, ein Medium der obersten Reichweitenklasse, das Mandat in einer Überschrift, eine Medienanfrage im verbundenen Postfach, eine benannte Person des Managements. Der Lauf prüft sie und meldet, wenn eine zutrifft. Ein Auslöser, der nur schön formuliert ist, wird nie ausgelöst und ist deshalb keiner.
- **B · Freier Text** Das Modell formuliert die Bedingung in Prosa, ein Mensch erkennt sie, wenn sie eintritt. Deckt jede denkbare Lage ab und verlagert das Beobachten zurück auf den Menschen, der es ohne Werkzeug schon heute nicht schafft.
- **C · Geschlossene Menge plus freie Notiz** Die prüfbare Bedingung feuert, daneben steht ein Satz für das, was sich nicht prüfen lässt. Vollständiger, und es entstehen zwei Klassen von Auslösern, von denen die eine funktioniert und die andere aussieht, als würde sie es auch.

### DEC-6: Wie liest sich das Register?  [mock]
**Status:** open
**Recommend:** A
**Locks as:** das Layout, gegen das Register und Heatmap gebaut und geprüft werden
- **A · Die Liste zuerst, die Heatmap daneben** Offene Issues nach Dringlichkeit, jedes mit Alter, letzter Bewegung und Zahl der angehängten Signale. Die Heatmap steht als kleiner Block daneben und wird groß, wenn es genug Issues für ein Bild gibt. Die Liste ist das, womit gearbeitet wird.
  `features/mocks/issues-liste.html`
- **B · Die Heatmap zuerst** Wahrscheinlichkeit gegen Wirkung als Feld, die Liste darunter. Beeindruckt im Kundengespräch und ist bei vier Issues ein Diagramm mit vier Punkten, das drei davon übereinander legt.
  `features/mocks/issues-heatmap.html`
- **C · Zwei Spalten nach Zustand** Links, was beobachtet wird, rechts, was aktiv bearbeitet wird, verschiebbar dazwischen. Macht die Arbeit sichtbar und drängt zu einer Pflege, für die im Krisenmonat niemand Zeit hat.
  `features/mocks/issues-spalten.html`

## Stories

### RIS-01: Die Ablesung und das Band

Aus der Berichterstattung eines Mandats wird eine Zahl je Tag, und aus den Zahlen
aller Mandate wird die eine Zeile, mit der der Morgen anfängt.

Die Stufe wird gerechnet, nicht geschätzt, aus den vier Größen, die ohnehin in
gespeicherten Zeilen stehen: Zahl der unabhängigen Medien an einer Story,
Reichweitenklasse aus der bestehenden Rangliste, Anteil negativer Tonalität, und ob
das Mandat namentlich genannt ist. Die Krisenstufe rechnet heute schon so. Hier
läuft dieselbe Rechnung eine Etage tiefer und über die Zeit.

Die wichtigste Regel dieser Story ist die, die nach oben bremst. Eine einzelne
negative Meldung hebt kein Mandat über Beobachtung, gleich wie groß das Medium ist.
Dafür braucht es zwei unabhängige Medien, eine Wiederholung an einem zweiten Tag,
oder eine Analyse der Kategorie `krise` ab Importance 8. Ohne diese Bremse ist das
Band nach zwei Wochen Dekoration, und dann hat es die Aufmerksamkeit verbraucht, die
für den einen Morgen gebraucht wird, an dem es zu Recht rot ist.

Weil je Mandat und Tag genau eine Ablesung gespeichert wird, entstehen zwei Dinge
ohne zusätzliche Arbeit: die Richtung, weil es eine Vorgeschichte gibt, und die
Abweichung, weil ein Mandat gegen seinen eigenen Median gemessen werden kann statt
gegen eine Schwelle, die für ein Stadtwerk und einen Konzern dieselbe wäre. Die
Leiter hat fünf Sprossen, und die Sprosse Issue bleibt unbesetzt, bis das Register
aus RIS-02 sie besetzt.

**Covers:** INV-01, 3, 4, 5, 6, 58
**Decisions:** DEC-1, DEC-2

**Acceptance:**
  - Der Sweep schreibt je Mandat und Tag genau eine Ablesung mit Zustand, den vier Eingangsgrößen und dem Zeitpunkt; ein zweiter Lauf am selben Tag aktualisiert sie, statt eine zweite anzulegen
  - Die Leiter hat fünf Sprossen: ruhig, Beobachtung, Issue, Risiko, Krise; jede wird gerechnet, nie von einem Modell gesetzt, und ein Test prüft die Rechnung gegen ein von Hand gezähltes Fixture
  - Eine einzelne negative Meldung hebt ein Mandat nie über Beobachtung; dafür braucht es zwei unabhängige Medien, eine Wiederholung an einem zweiten Tag, oder eine Analyse der Kategorie `krise` ab Importance 8, und diese Regel hat einen eigenen Test
  - Eine offene Krise setzt den Zustand auf Krise, ohne dass die Rechnung ihn absenken kann
  - Die Richtung wird aus den letzten sieben Ablesungen gerechnet und als Wort gezeigt: steigend, stabil, fallend; Farbe allein trägt nie eine Aussage
  - Ein Mandat gilt als verändert, wenn seine Ablesung den Median seiner letzten dreißig überschreitet; die Abweichung wird in der Zeile benannt
  - Das Band entspricht dem in der Band-Entscheidung festgelegten Mock und steht auf Heute über der Tagesberichterstattung
  - Sind alle Mandate ruhig, nimmt das Band eine Zeile ein und zeigt keine leeren Kacheln
  - Ein Mandat ohne Berichterstattung im Fenster ist ruhig und nicht unbekannt; die Ablesung sagt, dass nichts vorlag
  - Alle sichtbaren Zeichenketten liegen deutsch und englisch in `i18n.py` vor

**Files:** `newspulse/src/newspulse/reputation.py` (new), `newspulse/src/newspulse/models.py`, `newspulse/migrations/versions/0044_reputation_reading.py` (new), `newspulse/src/newspulse/config.py`, `newspulse/src/newspulse/job.py`, `newspulse/src/newspulse/web/routes/today.py`, `newspulse/src/newspulse/web/templates/today.html`, `newspulse/src/newspulse/web/templates/partials/reputation_band.html` (new), `newspulse/src/newspulse/i18n.py`, `newspulse/src/newspulse/web/static/app.css`, `newspulse/tests/test_reputation.py` (new), `newspulse/tests/test_reputation_band.py` (new), `newspulse/tests/test_migration.py`

### RIS-02: Das Issue-Register und die Heatmap

Die Sache, die drei Wochen alt wird. Ein Issue ist der Gegenstand, der heute im
Werkzeug fehlt: kein Beitrag, keine Krise, sondern das Thema, das sich wiederholt
und das jemand im Blick behalten muss.

Der Wert liegt im Anhängen, nicht im Anlegen. Ein Vorwurf am Montag und derselbe
Vorwurf am Freitag sind heute zwei Kärtchen; danach sind sie zwei Signale an einer
Zeile, die ein Alter hat, eine letzte Bewegung und eine Zahl. Genau daraus besteht
die Aussage, dass etwas wächst.

Wahrscheinlichkeit und Wirkung werden vorgeschlagen und von einem Menschen gesetzt,
und die Zeile zeigt, wer sie gesetzt hat, so wie es das Profil für jede
recherchierte Angabe schon tut. Eine vom Modell gesetzte Eintrittswahrscheinlichkeit
sieht aus wie eine Messung und ist eine Meinung.

Ein Issue, das eskaliert, wird zur Krise und übergibt dabei seine Vorgeschichte, so
dass die Zeitleiste der Krise nicht am Tag der Erklärung beginnt, sondern an dem
Tag, an dem das erste Signal auflief. Das ist der Grund, warum das Register vor
allem anderen kommt.

**Depends on:** RIS-01
**Covers:** 2, 55, 56
**Decisions:** DEC-3, DEC-4, DEC-6

**Acceptance:**
  - Ein Vorschlag entsteht, wenn sich ein Thema wiederholt: zwei Stories an zwei verschiedenen Tagen, oder eine Story und ein datiertes Marktsignal derselben Sache; der Vorschlag nennt, worin die Wiederholung besteht
  - Ein Vorschlag ändert sonst nichts, bis ein Mensch ihn annimmt; verwerfen lässt dieselbe Wiederholung nicht erneut vorschlagen
  - Ein Issue trägt Beschreibung, Wahrscheinlichkeit, Wirkung, Frühindikatoren, Owner, Status, Eröffnung und letzte Bewegung
  - Wahrscheinlichkeit und Wirkung werden vorgeschlagen und von einem Menschen gesetzt; die Zeile zeigt, wer den Wert gesetzt hat
  - Ein neues Signal wird einem offenen Issue zugeordnet, statt ein zweites anzulegen; jede Zuordnung trägt eine gespeicherte Begründung, und eine unbegründbare Zuordnung wird nicht gespeichert
  - Ein offenes Issue hebt den Zustand des Mandats im Band mindestens auf die Sprosse Issue
  - Das Register entspricht dem in der Register-Entscheidung festgelegten Mock
  - Die Heatmap zeigt offene Issues nach Wahrscheinlichkeit und Wirkung; ein Issue, dem einer der beiden Werte fehlt, steht in einer benannten Spalte daneben und nie im Ursprung des Feldes
  - Aus einem Issue heraus lässt sich eine Krise erklären; die Krise übernimmt die Signale und den Eröffnungszeitpunkt des Issues als Beginn ihrer Chronologie
  - Ein geschlossenes Issue verlangt einen Grund und bleibt mit allen Signalen lesbar
  - Alle sichtbaren Zeichenketten liegen deutsch und englisch in `i18n.py` vor

**Files:** `newspulse/src/newspulse/issues.py` (new), `newspulse/src/newspulse/models.py`, `newspulse/migrations/versions/0045_issues.py` (new), `newspulse/src/newspulse/prompts/issue_link.txt` (new), `newspulse/src/newspulse/crisis.py`, `newspulse/src/newspulse/reputation.py`, `newspulse/src/newspulse/job.py`, `newspulse/src/newspulse/web/routes/issues_view.py` (new), `newspulse/src/newspulse/web/templates/client_issues.html` (new), `newspulse/src/newspulse/web/templates/_client_tabs.html`, `newspulse/src/newspulse/web/app.py`, `newspulse/src/newspulse/i18n.py`, `newspulse/src/newspulse/web/static/app.css`, `newspulse/tests/test_issues.py` (new), `newspulse/tests/test_issues_view.py` (new)

### RIS-03: Die Stakeholder-Karte

Wer es erfährt, in welcher Reihenfolge, und was jede Gruppe eigentlich wissen will.

Die Karte steht am Mandat und nicht am Issue. Wer die Anwohner eines Standorts sind
und welcher Verband für diese Branche spricht, ändert sich nicht mit dem Anlass, und
eine Karte, die bei jedem Vorfall neu erfunden wird, ist bei jedem Vorfall zur
Hälfte falsch. Vorgeschlagen wird sie aus dem, was das Profil hergibt, bearbeitet
wird sie von einem Menschen, und jede Zeile zeigt, wer sie gesetzt hat.

Am Issue hängt dann nur die Auswahl: welche Gruppen dieser Anlass betrifft, in
welcher Reihenfolge sie erfahren sollten, und in einem Satz je Gruppe, was sie
wissen will. Die Reihenfolge ist eine Empfehlung mit Begründung. Gespeichert wird
die Reihenfolge des Menschen, denn sie hängt an Recht, Vertrag und Beziehung, und
davon sieht das Werkzeug einen Teil nicht.

Eine Gruppe ohne benannten Ansprechpartner ist die wichtigste Zeile der Karte und
keine leere Stelle. Sie verlinkt dorthin, wo sie nachgetragen wird, so wie es der
fehlende Krisenkontakt auf der Krisenseite schon tut.

**Depends on:** RIS-02
**Covers:** 15, 16, 17, 18

**Acceptance:**
  - Je Mandat gibt es eine stehende Stakeholder-Karte mit Gruppe, Betroffenheit, Einfluss, Ansprechpartner und Kanal
  - Die Karte wird aus dem Profil vorgeschlagen und von einem Menschen bearbeitet; jede Zeile zeigt, wer sie gesetzt hat, und eine von Hand gesetzte Zeile wird von keinem Vorschlag überschrieben
  - Zu einem Issue oder einer Krise entsteht eine Auswahl aus der stehenden Karte, mit Begründung je Gruppe, warum sie betroffen ist
  - Je ausgewählter Gruppe steht in einem Satz, was diese Gruppe wissen will; der Satz stützt sich auf gespeicherte Angaben und erfindet keine Betroffenheit
  - Die vorgeschlagene Reihenfolge ist als Empfehlung gekennzeichnet, umsortierbar, und gespeichert wird die Reihenfolge des Menschen
  - Eine Gruppe ohne Ansprechpartner erscheint als benannte Lücke mit Link ins Profil, nicht als leere Zeile
  - Ein Mandat ohne Profilangaben bekommt keine erfundene Karte, sondern den Satz, was ihm fehlt, mit dem Link dorthin
  - Alle sichtbaren Zeichenketten liegen deutsch und englisch in `i18n.py` vor

**Files:** `newspulse/src/newspulse/stakeholders.py` (new), `newspulse/src/newspulse/models.py`, `newspulse/migrations/versions/0046_stakeholders.py` (new), `newspulse/src/newspulse/prompts/stakeholder_map.txt` (new), `newspulse/src/newspulse/profile.py`, `newspulse/src/newspulse/web/routes/issues_view.py`, `newspulse/src/newspulse/web/routes/profile.py`, `newspulse/src/newspulse/web/templates/client_issues.html`, `newspulse/src/newspulse/web/templates/partials/stakeholder_map.html` (new), `newspulse/src/newspulse/i18n.py`, `newspulse/src/newspulse/web/static/app.css`, `newspulse/tests/test_stakeholders.py` (new)

### RIS-04: Szenarien, Auslöser und Reaktionsoptionen

Was als Nächstes passieren könnte, woran man merkt, dass es passiert, und was man
dann tut.

Drei Verläufe je Issue, und jeder ist ausdrücklich ein Szenario und nie eine
Prognose. Eine Wahrscheinlichkeit steht als Wort und nicht als Prozentzahl, weil
eine Prozentzahl aus einem Modell eine Genauigkeit behauptet, die es nicht gibt, und
weil genau diese Zahl später zitiert wird.

Der Auslöser ist das, was ein Szenario von einem Aufsatz unterscheidet. Er wird aus
einer geschlossenen Menge von Bedingungen gewählt, die der Lauf tatsächlich prüfen
kann: ein zweites unabhängiges Medium, ein Medium der obersten Reichweitenklasse,
das Mandat in einer Überschrift, eine Medienanfrage im verbundenen Postfach, eine
namentlich genannte Person des Managements. Trifft eine zu, steht das am Issue und
wird einmal gemeldet, und danach nicht wieder.

Unter den Reaktionsoptionen steht immer „nicht reagieren", mit derselben Bewertung
wie jede andere. Ein Werkzeug, das nur Handeln vorschlagen kann, schlägt Handeln
vor, und der teuerste Fehler in diesem Fach ist die Stellungnahme, die einer Sache
erst die Öffentlichkeit verschafft, die sie noch nicht hatte. Die Empfehlung nennt
außerdem eine Geschwindigkeit aus einer festen Menge, damit „schnell" und „sofort"
nicht dasselbe bedeuten.

**Depends on:** RIS-03
**Covers:** 7, 8, 9, 26, 27, 28
**Decisions:** DEC-5

**Acceptance:**
  - Zu einem Issue entstehen drei Szenarien: bester, wahrscheinlicher und schlechtester Verlauf, jedes mit betroffenen Stakeholdern aus der Karte und dem Kommunikationsbedarf
  - Die Wahrscheinlichkeit steht als Wort aus einer festen Menge und nie als Prozentzahl
  - Jedes Szenario trägt mindestens einen Auslöser aus der geschlossenen Menge maschinell prüfbarer Bedingungen; ein Szenario ohne prüfbaren Auslöser wird nicht gespeichert
  - Trifft eine Bedingung zu, wird das am Issue vermerkt und einmal benachrichtigt; ein bereits ausgelöster Auslöser feuert nicht erneut, auch nicht nach einem Neustart
  - Es entstehen mindestens drei Reaktionsoptionen, darunter immer „nicht reagieren", jede mit Nutzen, Risiko und Eskalationspotenzial
  - Die Empfehlung nennt eine Geschwindigkeit aus der Menge: sofort, innerhalb einer Stunde, heute, innerhalb von 24 Stunden, vorbereiten und beobachten, keine Reaktion
  - Jedes Szenario ist im Text als Szenario gekennzeichnet; ein Test mit eingespeister Erzeugung prüft, dass ein als Tatsache formulierter Verlauf verworfen wird
  - Das Modell liefert keine Zahl und kein Datum, die nicht in einer benannten Zeile stehen
  - Der Block, der die Szenarienhaltung trägt, steht in den neuen Prompts und ist in keinem von ihnen ausgeschrieben
  - Alle sichtbaren Zeichenketten liegen deutsch und englisch in `i18n.py` vor

**Files:** `newspulse/src/newspulse/scenarios.py` (new), `newspulse/src/newspulse/models.py`, `newspulse/migrations/versions/0047_scenarios.py` (new), `newspulse/src/newspulse/prompts/scenarios.txt` (new), `newspulse/src/newspulse/prompts/response_options.txt` (new), `newspulse/src/newspulse/blocks/scenario_discipline.txt` (new), `newspulse/src/newspulse/brain.py`, `newspulse/src/newspulse/job.py`, `newspulse/src/newspulse/notify.py`, `newspulse/src/newspulse/web/routes/issues_view.py`, `newspulse/src/newspulse/web/templates/client_issues.html`, `newspulse/src/newspulse/i18n.py`, `newspulse/tests/test_scenarios.py` (new), `newspulse/tests/test_brain.py`

### RIS-05: Das Entscheidungspapier

Eine Seite, die eine Entscheidung möglich macht, und danach das Dokument, das
belegt, worauf sie beruhte.

Es steht in vier Teilen, und die Trennung zwischen ihnen ist der ganze Wert:
belegt, unbestätigt, offen, widersprüchlich. Jeder als belegt geführte Satz löst auf
eine gespeicherte Zeile auf: einen Beitrag, eine Analyse, ein Profilfeld, ein
Marktsignal, eine Mail. Was das nicht tut, steht unter unbestätigt oder gar nicht.

Ein Widerspruch wird nur gemeldet, wenn beide Seiten benennbar sind. Ein
freigegebener Text von uns gegen eine heutige Behauptung, ein Profilfeld gegen eine
Zahl in der Berichterstattung. Ein gemeldeter Widerspruch ohne zweite Seite ist
schlimmer als kein gemeldeter Widerspruch, weil er in einer Krise geglaubt wird.

Die Lücken sind der Teil, den ein Mensch unter Druck nicht selbst zusammenträgt.
Kein Sprecher im Profil, kein Krisenkontakt, keine bestätigte Zahl der Betroffenen,
kein Entscheider benannt: jede Lücke steht als Zeile mit dem Link dorthin, wo sie
geschlossen wird.

Am Ende steht, was jetzt zu entscheiden ist, wer entscheidet und bis wann. Trägt das
Papier keine dieser drei Angaben, ist das die erste Zeile darauf und nicht das
Fehlen einer Zeile. Das Papier wird gespeichert, wie es zum Zeitpunkt der
Entscheidung aussah, samt der getroffenen Entscheidung und der Person, denn im
Nachhinein ist genau das die Frage, die gestellt wird.

**Depends on:** RIS-04
**Covers:** INV-04, 10, 12, 13, 14, 63

**Acceptance:**
  - Das Papier entsteht auf Knopfdruck zu einem Issue oder einer Krise und trägt: was passiert ist, was belegt ist, was unbestätigt ist, was offen ist, welche Widersprüche bestehen, welche Optionen es gibt, wer bis wann entscheidet
  - Jeder als belegt geführte Satz trägt die Kennung der Zeile, aus der er stammt; ein Satz ohne auflösbaren Beleg erscheint unter unbestätigt oder gar nicht, und ein Test mit eingespeister Erzeugung prüft das
  - Die Quellenordnung ist festgelegt und im Papier sichtbar: bestätigte interne Angabe, Behörde oder Originaldokument, verifizierter Medienbericht, alles Übrige
  - Ein Widerspruch wird nur gemeldet, wenn beide Seiten als gespeicherte Zeilen benannt sind; ein Widerspruch mit nur einer Seite wird nicht gemeldet
  - Fehlende Angaben stehen als benannte Lücken mit Link dorthin, wo sie nachgetragen werden
  - Fehlen Entscheider oder Frist, steht das oben auf dem Papier und nicht als Leerstelle
  - Das Papier wird mit seinem Stand gespeichert; die getroffene Entscheidung und die entscheidende Person werden daran vermerkt und sind später lesbar
  - Ein neues Papier zum selben Issue ersetzt das alte nicht, sondern tritt daneben
  - Das Papier ist herunterladbar, und die heruntergeladene Fassung enthält keine Links zurück in die Anwendung
  - Ein Golden-File-Test über ein gesätes Issue macht jede Formulierungsänderung als Diff prüfbar
  - Alle sichtbaren Zeichenketten liegen deutsch und englisch in `i18n.py` vor

**Files:** `newspulse/src/newspulse/decision.py` (new), `newspulse/src/newspulse/models.py`, `newspulse/migrations/versions/0048_decision_packet.py` (new), `newspulse/src/newspulse/prompts/decision_packet.txt` (new), `newspulse/src/newspulse/blocks/evidence.txt`, `newspulse/src/newspulse/brain.py`, `newspulse/src/newspulse/web/routes/issues_view.py`, `newspulse/src/newspulse/web/templates/decision_packet.html` (new), `newspulse/src/newspulse/reporting.py`, `newspulse/src/newspulse/i18n.py`, `newspulse/tests/test_decision.py` (new), `newspulse/tests/fixtures/decision/` (new)

## Deferred

- **INV-02**: not selected
- **INV-03**: not selected
- **INV-05**: not selected
- **1**: not selected
- **11**: not selected
- **19**: not selected
- **20**: not selected
- **21**: not selected
- **22**: not selected
- **23**: not selected
- **24**: not selected
- **25**: not selected
- **29**: not selected
- **30**: not selected
- **31**: not selected
- **32**: not selected
- **33**: not selected
- **34**: not selected
- **35**: not selected
- **36**: not selected
- **37**: not selected
- **38**: not selected
- **39**: not selected
- **40**: not selected
- **41**: not selected
- **42**: not selected
- **43**: not selected
- **44**: not selected
- **45**: not selected
- **46**: not selected
- **47**: not selected
- **48**: not selected
- **49**: not selected
- **50**: not selected
- **51**: not selected
- **52**: not selected
- **53**: not selected
- **54**: not selected
- **57**: not selected
- **59**: not selected
- **60**: not selected
- **61**: not selected
- **62**: not selected
- **64**: not selected
- **65**: not selected
- **66**: not selected
- **67**: not selected
- **68**: not selected
- **69**: not selected
- **70**: not selected
- **71**: not selected
- **72**: not selected

## Summary

Heute kennt das Werkzeug zwei Zustände für ein Mandat: ein rotes Kärtchen, das um
Mitternacht verfällt, und eine erklärte Krise. Dazwischen liegt der Bereich, in dem
die Arbeit tatsächlich stattfindet, und dort hat das Werkzeug bisher kein
Gedächtnis. Derselbe Vorwurf am Montag, am Mittwoch und am Freitag sieht aus wie
drei Meldungen an drei Tagen.

Danach beginnt der Morgen mit einer Zeile, die für jedes Mandat sagt, wie es steht,
in welche Richtung es sich bewegt und ob das für dieses Mandat ungewöhnlich ist.
Die Zeile ist an einem normalen Morgen eine Zeile hoch, denn ein Band, das jeden Tag
Alarm schlägt, ist nach zwei Wochen keines mehr. Jede Stufe darauf ist gerechnet und
lässt sich vor einem Kunden nachrechnen.

Was sich wiederholt, wird zu einem Issue: einer Zeile mit Alter, Owner und einer
wachsenden Zahl angehängter Signale, die zeigt, dass etwas größer wird, statt es
jeden Morgen neu zu entdecken. Wird daraus eine Krise, bringt das Issue seine
Vorgeschichte mit, so dass die Chronologie nicht am Tag der Erklärung beginnt.

Dazu kommt, was in der Stunde gebraucht wird, in der entschieden werden muss: wer
betroffen ist und in welcher Reihenfolge er es erfährt, drei mögliche Verläufe mit
Auslösern, die das Werkzeug selbst prüft, Reaktionsoptionen einschließlich der
Option zu schweigen, und ein Papier, das belegte Fakten, unbestätigte Angaben,
offene Fragen und Widersprüche sauber trennt und benennt, wer bis wann entscheidet.
Das Papier bleibt gespeichert, wie es aussah, als die Entscheidung fiel.

Nicht in diesem Bau: alles, was eine neue Datenquelle braucht. Parlamentarische
Vorgänge, Behördenmeldungen und Social Listening sind eine eigene Spezifikation, und
das Band ist so gebaut, dass eine weitere Signalquelle darin eine Eingangsgröße mehr
ist und keine zweite Oberfläche.

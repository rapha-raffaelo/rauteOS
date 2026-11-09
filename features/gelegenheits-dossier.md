# Das Gelegenheits-Dossier: eine Seite je Gelegenheit

prefix: GEL

**Type:** feature
**Complexity:** 3
**Estimated Duration:** ~1 Woche
**Risk:** low
**Scope:** newspulse, newsjack, web
**Test Strategy:** `TestClient`-Abdeckung über die neue Seite gegen die bestehende In-Memory-SQLite-Fabrik, mit eingespeister Uhr statt gepatchtem Zeitmodul, so dass Fenster und Restzeit deterministisch prüfbar sind; die Dringlichkeitszahl wird gegen ein von Hand gerechnetes Fixture geprüft und nie gegen sich selbst; je ein Test für den leeren Zustand (keine Texte, keine Autoren, keine Kontakte), für die ausgelaufene und für die verworfene Gelegenheit; ein Test, dass ein GET auf das Dossier keine Zeile schreibt, indem er die Zeilenzahlen vor und nach dem Aufruf vergleicht; ein Test, dass beim Rendern kein Modell gerufen wird, über einen eingespeisten Backend, der bei Aufruf wirft; für den Anstrich ein Durchlauf über jede bestehende Route, der nach der Änderung weiter 200 erwartet, und ein Test, der jeden Verweis der neuen Kopfleiste aufruft und keine 404 zulässt. Kein Test ruft ein Modell auf und kein Test geht ins Netz.

## Context

Die schnelle Spur findet eine Marktgeschichte, prüft, ob das Mandat dazu Stehen hat,
und legt eine Gelegenheit an. Sichtbar wird davon ein Kärtchen auf Heute: die
Schlagzeile, wer sie zuerst hatte, wie viele Medien sie tragen, wie lange das
Fenster noch läuft, ein Satz zum Stehen, zwei Knöpfe. Das Kärtchen ist eine
Zehn-Sekunden-Entscheidung, und dafür ist es genau richtig gebaut.

Danach hört es auf. Wer wissen will, worum es in der Geschichte eigentlich geht,
welche Beiträge sie tragen, wer sie geschrieben hat, ob davon jemand im Kontaktbuch
steht, welche Texte am Anlass schon hängen, was davon geprüft ist und was als
nächstes zu tun wäre, klickt sich durch fünf Seiten: Heute, Texte, Kontaktbuch,
Profil, Guide-Prüfung. Das Werkzeug weiß alles davon. Es hat nur keinen Ort, an dem
es zu dieser einen Geschichte zusammensteht. Und weil das Fenster in Stunden
gerechnet wird, ist das Zusammensuchen genau die Arbeit, für die keine Zeit ist.

Diese Funktion baut diesen Ort: ein Dossier je Gelegenheit, erreichbar vom Kärtchen
auf Heute und von der Liste der abgeschlossenen Gelegenheiten auf der
Mandantenseite. Es liest ausschließlich, was gespeichert ist. Es legt keinen Anlass
an, ruft kein Modell und erzeugt keinen Text, weil eine Seite, die beim bloßen
Ansehen Geld kostet, nicht die Seite ist, die man vier Mal am Vormittag öffnet.

Der Entwurf, der dem Papier zugrunde liegt, zeigt drei Dinge, für die es im
Werkzeug keine gespeicherte Zeile gibt, und sie sind hier bewusst anders gelöst.
Eine Zeitleiste, die bis ins nächste Quartal vorausschaut, wäre eine Schätzung, die
niemand nachrechnen kann; an ihrer Stelle steht die Chronik, die aus Zeitstempeln
gelesen wird und rückwärts belegt statt vorwärts rät. Anspruchsgruppen-Chips je
Geschichte setzen ein Urteil voraus, das nirgends steht. Und eine Leiste aus
Engines, die einander mit Häkchen bestätigen, beschreibt eine Architektur, die es
nicht gibt: das Werkzeug hat Module, keine Motoren, und ein Häkchen, hinter dem
kein Lauf steht, ist die teuerste Art von Vertrauen. Was an ihre Stelle tritt, ist
eine Leiste, in der jede Kachel auf einer gespeicherten Zeile mit Datum steht und
dahin verlinkt, wo sie entstanden ist.

Was am Entwurf trägt und übernommen wird, ist die Kernidee: eine Gelegenheit ist
kein Kärtchen, sondern ein Vorgang, und ein Vorgang hat eine Seite.

## Decisions

### DEC-1: Wie liest sich das Dossier?  [mock]
**Status:** locked
**Chosen:** A
**Recommend:** C
**Locks as:** das Layout, gegen das die Seite gebaut und geprüft wird
- **A · Die Kommandozentrale** Der eingereichte Entwurf, nah nachgebaut: violetter Akzent, Kopfleiste mit Suche und Ask RAUTE, Reiter mit Symbolen, Kopf mit Dringlichkeitsplakette und Statuswahl, darunter die Herkunftsleiste, sechs Kacheln in zwei Reihen, rechts RAUTE Intelligence, unten die Entscheidungsspur mit Pfeilen. Zeigt in einem Blick am meisten, und verteilt die Frage „was tue ich jetzt“ auf viele Kästen.
  `features/mocks/gelegenheit-kommandozentrale.html`
- **B · Die Chronik** Eine Spalte, alles in zeitlicher Ordnung: der Ursprungsbeitrag, jeder Aufgriff, jeder eigene Schritt, und ganz oben der nächste. Wer später fragt, warum an diesem Tag so entschieden wurde, liest die Seite von oben. Verliert dafür den Überblick über den Stand.
  `features/mocks/gelegenheit-chronik.html`
- **C · Zwei Spalten** Links, was über das Thema läuft, ohne uns. Rechts, was wir dagegen gesetzt haben. Dazwischen der Kasten, der benennt, worauf noch nichts von uns läuft. Dieselbe Teilung, die auf der Krisenseite schon steht, einmal ins Positive gedreht: der Abstand zwischen den Spalten ist die Gelegenheit, und die Seite zeigt ihn, statt ihn ausrechnen zu lassen.
  `features/mocks/gelegenheit-zwei-spalten.html`

### DEC-2: Bekommt eine Gelegenheit eine Zahl?  [options]
**Status:** locked
**Chosen:** A
**Recommend:** A
**Locks as:** ob und wie eine Dringlichkeit auf der Seite steht
- **A · Gerechnet, und die Rechnung ist abrufbar** Eine Zahl von 0 bis 100 aus drei gespeicherten Größen: Verbreitung (Zahl der Medien, gedeckelt bei acht, bis 40 Punkte), Frist (verbrauchter Anteil des Fensters, bis 40 Punkte), Stehen (belegt, 20 Punkte). Die Plakette zeigt wie in der Vorlage nur die Zahl; die drei Summanden stehen am Zeiger und in der Herkunftsleiste unter „Score berechnet von“. Sortiert mehrere Gelegenheiten über mehrere Mandate hinweg und ist von Hand nachrechenbar.
- **B · Keine Zahl** Nur die drei Angaben selbst: vier Medien, 27 von 48 Stunden übrig, Stehen belegt. Nichts kann falsch gewichtet sein, und niemand kann zwei Gelegenheiten vergleichen, ohne sie beide zu lesen.

### DEC-3: Woher kommt die Zeitleiste?  [options]
**Status:** locked
**Chosen:** B
**Recommend:** B
**Locks as:** was die Zeitachse auf der Seite zeigt
**Hinweis:** Von A auf B gewechselt, weil der gewählte Mock die Zeitleiste nach vorn zeigt („Heute, 2 bis 7 Tage, 1 bis 2 Wochen, Q2 2025“). Das kostet je Gelegenheit einen Modellaufruf bei der Erkennung.
- **A · Rückwärts, aus Zeitstempeln** Die Beiträge der Story und die eigenen Schritte (Gelegenheit angelegt, Anlass geöffnet, Text geschrieben, Text geprüft, Brief heraus) in einer Reihe, alles aus gespeicherten Zeitstempeln gelesen. Kostet nichts, ist immer richtig, und ist hinterher der Beleg, wann was entschieden wurde. Beantwortet nicht die Frage, die ein Berater am Vormittag stellt.
- **B · Vorwärts, geschätzt** Ein Modell schätzt die kommenden Entscheidungspunkte („2 bis 7 Tage: Verbände positionieren sich“). Das ist die Kachel aus der Vorlage, und sie beantwortet genau die Frage, wegen der man die Seite öffnet: wie lange habe ich noch. Sie wird einmal bei der Erkennung geschrieben und mit der Gelegenheit gespeichert, nicht bei jedem Aufruf, sonst kostet Ansehen Geld. Die Kachel trägt sichtbar, dass sie eine Einschätzung ist und wann sie entstand, damit sie nicht wie die belegten Zeilen daneben gelesen wird.

### DEC-5: Was steht als Zahl neben einem Journalisten?  [options]
**Status:** locked
**Chosen:** B
**Recommend:** B
**Locks as:** woraus die Zahl in den Medienempfehlungen besteht
- **A · Nur der Rang und sein Grund** Platz 1 bis 3 und darunter, woher die Empfehlung kommt: „schrieb diese Story heute 08:42“ oder „schreibt über das Feld“. Nichts wird gerechnet, nichts kann falsch gewichtet sein, und die Kachel sieht anders aus als die Vorlage.
- **B · Eine gerechnete Passung von 0 bis 100** Aus drei gespeicherten Größen: hat diese Person die Story selbst geschrieben, wie oft sie im Feld der letzten 90 Tage auftaucht, und ob ein Kontakt hinterlegt ist. Sieht aus wie die Vorlage, ordnet 17 Namen in eine Reihenfolge, die ein Mensch nicht im Kopf hat, und ist nachrechenbar. Nie ein Modellaufruf, weil eine geschätzte Passung zu einer Person die Art Zahl ist, die niemand prüft und trotzdem alle glauben.
- **C · Gar keine Zahl** Drei Namen, sonst nichts. Am wenigsten Angriffsfläche, und die Frage „wen zuerst“ bleibt beim Berater.

### DEC-6: Woher kommt die Relevanz für Zielgruppen?  [options]
**Status:** locked
**Chosen:** A
**Recommend:** A
**Locks as:** worauf die Chips unter der Storyline stehen
- **A · Die Anspruchsgruppen des Mandats** Die Gruppen, die im Mandat hinterlegt sind, in der gespeicherten Reihenfolge. Kostet nichts, steht auf gepflegten Zeilen, und sagt „für diese Gruppen arbeiten wir“, nicht „diese Geschichte berührt genau sie“.
- **B · Je Geschichte geurteilt** Ein Modell entscheidet, welche der Gruppen diese eine Story berührt, und die Chips färben sich danach. Das ist die Aussage, die die Vorlage macht, und sie ist die nützlichere. Ein zusätzlicher Modellaufruf je Gelegenheit, zusammen mit der Zeitleiste aus DEC-3 auf einen Aufruf gebündelt.

### DEC-4: Bekommt das ganze Werkzeug den neuen Anstrich?  [options]
**Status:** locked
**Chosen:** A
**Recommend:** A
**Locks as:** wie weit die Gestaltung aus der Vorlage reicht
- **A · Das Aussehen gilt überall** Farbwerte, Kopfleiste mit Suche und Ask RAUTE, Reiter mit Symbolen und der Kachelstil wandern in die gemeinsame Grundlage. Die neue Seite sieht dann aus wie die Vorlage, weil die Umgebung es tut, und jede bestehende Seite erbt es mit. Ein Anstrich über ein laufendes Werkzeug, das Lucas täglich benutzt, und deshalb eine eigene Geschichte mit eigenen Tests.
- **B · Nur die neue Seite** Die Gestaltung bleibt auf das Dossier begrenzt. Kein Risiko für die zwölf bestehenden Seiten, und dafür eine Seite, die neben ihren Nachbarn wie ein Fremdkörper steht, weil Rahmen und Inhalt aus zwei Entwürfen stammen.

## Stories

### GEL-01: Das Dossier zur Gelegenheit

Eine Seite unter `/client/{client_id}/gelegenheit/{id}`, die alles zusammenstellt,
was das Werkzeug zu dieser einen Geschichte für dieses eine Mandat weiß.

Sie liest und schreibt nichts. Das ist die tragende Eigenschaft und nicht eine
Sparsamkeit: der bestehende Weg vom Kärtchen zum Text legt beim Klick einen Anlass
an, und eine Seite, die dasselbe beim Ansehen täte, würde für jede angeschaute
Gelegenheit einen Anlass hinterlassen, den niemand wollte. Das Dossier zeigt einen
vorhandenen Anlass, wenn es einen gibt, und sonst den Knopf, der ihn anlegt.

Der nächste Schritt wird aus dem Zustand gelesen, nicht geschätzt. Kein Anlass
heißt Text schreiben, ein Anlass ohne Text heißt Format wählen, ein ungeprüfter
Text heißt Prüfung, ein geprüfter Text ohne Brief heißt senden. Das ist eine
Zustandsmaschine über gespeicherte Zeilen und kein Modellaufruf, und sie ist damit
das einzige auf der Seite, das dem Berater sagt, was er tun soll, ohne es zu raten.

Eine ausgelaufene oder verworfene Gelegenheit bleibt lesbar. Sie verliert die
Knöpfe und bekommt an ihrer Stelle die Zeile, wann und woran sie endete, weil die
Frage hinterher immer ist, was zu dem Zeitpunkt bekannt war.

Der Mock ist die Vorlage, und er zeigt das ganze Zielbild: die Umgebung, die
Menüpunkte und die Reiter, die es zum Teil noch nicht gibt. Zu dieser Geschichte
gehört alles ab dem Zurück-Verweis: Kopf mit Plakette und Statuswahl, die
Herkunftsleiste, die Reiter auf der Seite, die sechs Kacheln, die Spur unten.
Seitenleiste, Kopfleiste und die oberste Reiterreihe sind der bestehende Rahmen;
ihr Aussehen regelt DEC-4 und GEL-03, ihre Namen bleiben die des Werkzeugs.

Die Reiter auf der Seite sind keine acht neuen Unterseiten. Gebaut werden die,
die auf etwas führen: „Situation“ ist diese Seite, „Positionierung“, „Medien“,
„Assets“, „Quality“ und „GEO & AI Visibility“ führen auf die Mandatsseiten, die es
gibt. „Performance“ und „Historie“ stehen in der Vorlage und bleiben draußen,
solange nichts dahinter liegt: ein Reiter, der auf nichts führt, ist schlimmer als
einer, der fehlt.

**Decisions:** DEC-1, DEC-2, DEC-3, DEC-5, DEC-6

**Acceptance:**
  - `GET /client/{client_id}/gelegenheit/{id}` rendert das Dossier für eine Gelegenheit mit Stehen `belegt`; eine unbekannte Id, eine fremde Mandantenzuordnung und eine Zeile mit `duenn` oder `keins` geben jeweils 404
  - Die Statuswahl im Kopf zeigt den Zustand, der aus vorhandenen Zeilen folgt (offen, aktiv sobald ein Anlass hängt, ausgelaufen, verworfen), und legt keine neue Spalte an; „Aktivieren“ öffnet den Anlass und ist derselbe Vorgang wie „Text schreiben“ auf dem Kärtchen
  - Ein Aufruf der Seite schreibt keine Zeile: ein Test vergleicht die Zeilenzahlen von `angles`, `assets` und `newsjack_opportunities` vor und nach dem Aufruf, und ein eingespeister Analyse-Backend, der bei Aufruf wirft, bleibt ungerufen
  - Die Quellenliste führt alle Beiträge der Story, älteste zuerst, je Zeile mit Medium, Zeitpunkt und dem gespeicherten Autor, wo einer vorliegt; der Ursprungsbeitrag ist als Ursprung markiert
  - Die Plakette neben der Überschrift zeigt eine Zahl von 0 bis 100, gerechnet nach DEC-2 aus Medienzahl, verbrauchtem Fensteranteil und Stehen; die drei Summanden sind am Zeiger und in der Herkunftsleiste lesbar, und ein Test prüft die Zahl gegen ein von Hand gerechnetes Fixture
  - Die Zeitleisten-Kachel folgt DEC-3; fällt die Wahl auf die Schätzung, wird sie einmal bei der Erkennung geschrieben und gespeichert, nie beim Aufruf der Seite, und trägt sichtbar, dass sie eine Einschätzung ist und wann sie entstand
  - Die Zielgruppen-Chips unter der Storyline folgen DEC-6 und stehen in beiden Fällen auf gespeicherten Zeilen, nie auf einer Liste, die im Template steht
  - Die Spur unten führt die Beiträge der Story und die eigenen Schritte (Gelegenheit erkannt, Stehen geprüft, Anlass geöffnet, jeder Text mit Fassung und Prüfzustand, jeder freigegebene Brief, jede Antwort) in einer nach Zeit sortierten Reihe zusammen, jeder Eintrag mit Uhrzeit und Urheber
  - Die Kachel „Empfohlene nächste Schritte“ wird aus dem Zustand gelesen, nicht geschätzt: kein Anlass gibt „Text schreiben“, ein Anlass ohne Text gibt „Format wählen“, ein ungeprüfter Text gibt „Prüfung starten“, ein geprüfter Text ohne Brief gibt „senden“; die Einstufung hoch oder mittel folgt daraus, ob der Schritt den nächsten blockiert
  - Die Medienliste kommt aus `pitch.py`, ordnet nach DEC-5, nennt je Person die Herkunft der Empfehlung und ob ein Kontakt hinterlegt ist, und zeigt nie eine abgeleitete Adresse
  - Das Kärtchen auf Heute und die Liste der abgeschlossenen Gelegenheiten auf der Mandantenseite verlinken auf das Dossier; eine ausgelaufene oder verworfene Gelegenheit rendert ohne Handlungsknöpfe und nennt stattdessen Zeitpunkt und Grund des Endes
  - Eine Gelegenheit ohne Texte, ohne gespeicherte Autoren und ohne Kontakte rendert vollständig, mit benannten leeren Zuständen statt Nullen oder Platzhalterzahlen
  - Die Herkunftsleiste über den Kacheln nennt, wodurch die Gelegenheit erkannt wurde, aus welchen drei Werten die Dringlichkeit gerechnet ist und gegen welche Standardfassung das Stehen geprüft wurde
  - Die Reiterleiste auf der Seite führt „Situation“ als diese Seite und die übrigen als Verweise auf bestehende Mandatsseiten; ein Test löst jeden Verweis auf eine vorhandene Route auf, und ein Reiter ohne Ziel steht nicht in der Leiste

**Files:** `newspulse/src/newspulse/opportunity.py` (new), `newspulse/src/newspulse/web/routes/opportunity_view.py` (new), `newspulse/src/newspulse/web/templates/opportunity.html` (new), `newspulse/src/newspulse/web/app.py`, `newspulse/src/newspulse/web/templates/partials/newsjack_card.html`, `newspulse/src/newspulse/web/templates/client_detail.html`, `newspulse/src/newspulse/i18n.py`, `newspulse/src/newspulse/web/static/app.css`, `newspulse/tests/test_opportunity_view.py` (new)

### GEL-02: RAUTE Intelligence, die Leiste rechts

Sechs Kacheln neben dem Dossier, die beantworten, worauf das Mandat sich in dieser
Sache berufen kann: die Positionierung aus dem Profil, wie viele der Bylines im
Feld überhaupt erreichbar sind, was am Anlass an Texten hängt, wie es um deren
Prüfung steht, was die letzte Sichtbarkeitsmessung ergeben hat, und wie das
Reputationsband gerade steht. Sie sehen aus wie die Engine-Kacheln der Vorlage,
mit farbigem Symbolfeld, farbiger Ergebniszeile und Zeichen rechts.

Sie tragen nur eine zusätzliche Regel: jede Kachel steht auf einer gespeicherten
Zeile, nennt deren Stand und verlinkt auf die Seite, auf der sie entstanden ist.
Ein grünes Häkchen bedeutet, dass etwas gelaufen ist und ohne Einwand blieb, und
niemals, dass nichts gelaufen ist. Wo nichts gespeichert ist, sagt die Kachel das
und verlinkt dahin, wo es entstehen würde. Eine Kachel, die eine Null zeigt, weil
nie gemessen wurde, und eine, die eine Null zeigt, weil gemessen und nichts
gefunden wurde, dürfen sich nicht gleich lesen: derselbe Grund, aus dem der
Prüfzustand eines Textes drei Werte hat und nicht zwei.

Wie bei GEL-01 gilt: kein Modellaufruf, keine Netzanfrage, nur Lesen.

**Depends on:** GEL-01
**Decisions:** DEC-1

**Acceptance:**
  - Die Leiste zeigt sechs Kacheln in der Reihenfolge und unter den Namen der Vorlage: Positioning, Media &amp; Relationship, Communication Asset, Quality &amp; Verification, AI Visibility &amp; GEO, Communication Intelligence
  - Positioning nennt den Positionierungssatz aus dem Profil und das Datum, an dem er zuletzt bestätigt wurde
  - Media &amp; Relationship nennt die Zahl der Journalisten aus der Medienliste dieser Gelegenheit und den bestplatzierten Namen mit seiner Herkunft
  - Communication Asset nennt die Texte, die am Anlass hängen, und wie viele davon geprüft sind; Quality &amp; Verification nennt, wie viele einen Einwand tragen und wie viele ungeprüft sind, aus dem gespeicherten Prüfzustand
  - AI Visibility &amp; GEO nennt Band und Datum der jüngsten Sichtbarkeitsmessung des Mandats; Communication Intelligence nennt den Reputationsstand und die Zahl der Beiträge, auf denen er beruht
  - Das Zeichen rechts auf einer Kachel unterscheidet drei Fälle: gelaufen und ohne Einwand, gelaufen mit Einwand, und nichts gelaufen; ein grünes Häkchen erscheint nie für einen fehlenden Lauf, und ein Test prüft genau das
  - Eine Kachel ohne gespeicherte Grundlage sagt in einem Satz, dass dazu noch nichts gemessen wurde, und verlinkt auf die Seite, auf der es entsteht; ein Test prüft, dass sie sich von einer gemessenen Null unterscheidet
  - Beim Rendern der Leiste wird kein Modell gerufen und keine Netzanfrage gestellt; ein eingespeister Backend, der bei Aufruf wirft, bleibt ungerufen
  - Jede Kachel trägt einen Link auf die Seite, aus der ihr Wert stammt, und alle sechs Links lösen im Test auf eine bestehende Route auf

**Files:** `newspulse/src/newspulse/dossier_rail.py` (new), `newspulse/src/newspulse/web/templates/partials/opportunity_rail.html` (new), `newspulse/src/newspulse/web/templates/opportunity.html`, `newspulse/src/newspulse/web/routes/opportunity_view.py`, `newspulse/src/newspulse/i18n.py`, `newspulse/src/newspulse/web/static/app.css`, `newspulse/tests/test_dossier_rail.py` (new)

### GEL-03: Der Anstrich aus der Vorlage

Die Gestaltung der Vorlage, angewendet auf den Rahmen, den es schon gibt: der
violette Akzent statt des blauen, eine Kopfleiste über dem Inhalt mit Pfad, Suchfeld
und dem Ask-RAUTE-Knopf, Reiter mit Symbolen, und der Kachelstil mit weicherem
Radius und feinem Schatten.

Das ist ausdrücklich ein Anstrich und kein Umbau. Es entsteht keine neue Seite,
kein neuer Menüpunkt und keine neue Route. Die Kopfleiste bekommt ihre Wege von
dem, was schon existiert: das Suchfeld führt ins Archiv, der Ask-RAUTE-Knopf öffnet
den Assistenten, der bereits läuft. Ein Knopf in dieser Leiste, hinter dem nichts
liegt, gehört nicht hinein, auch wenn die Vorlage ihn zeigt.

Der Anstrich liegt in den Farb- und Maßwerten an einer Stelle, nicht in
zwanzig Regeln über die Datei verteilt, denn sonst ist die nächste Änderung an der
Gestaltung wieder eine Woche Arbeit. Und weil das Werkzeug jeden Morgen benutzt
wird, gehört zu dieser Geschichte, dass jede bestehende Seite danach noch lädt.

**Depends on:** GEL-01
**Decisions:** DEC-4

**Acceptance:**
  - Farb- und Maßwerte stehen als Variablen an einer Stelle in `app.css`; ein Wechsel des Akzents ist eine Zeile, und kein Modul definiert seinen eigenen Akzent daneben
  - Die Kopfleiste zeigt den Pfad (Arbeitsbereich, Mandat), ein Suchfeld und den Ask-RAUTE-Knopf; das Suchfeld führt auf die Archivsuche, der Knopf auf den bestehenden Assistenten
  - Kein Element der Kopfleiste führt ins Leere: ein Test ruft jeden Verweis der Leiste auf und erwartet keine 404
  - Die Mandatsreiter tragen Symbole und den neuen aktiven Zustand, behalten aber ihre bestehenden Namen, Reihenfolge und Ziele
  - Die Seitenleiste behält ihre Struktur und übernimmt nur Farbe, Abstände und den aktiven Zustand
  - Ein Durchlauf über alle bestehenden Seiten (Heute, Portfolio, Archiv, Kontakte und jede Mandatsseite) antwortet nach dem Anstrich weiter mit 200
  - Die Änderung ist reine Darstellung: kein Template gewinnt oder verliert einen Wert, und kein Test in `tests/` muss wegen geänderter Inhalte angefasst werden

**Files:** `newspulse/src/newspulse/web/static/app.css`, `newspulse/src/newspulse/web/templates/base.html`, `newspulse/src/newspulse/web/templates/_client_tabs.html`, `newspulse/src/newspulse/i18n.py`, `newspulse/tests/test_shell_paint.py` (new)

## Deferred

- **Engines als eigenes Objekt, mit Laufprotokoll je Gelegenheit**: die Leiste in GEL-02 trägt die Namen und das Aussehen der Vorlage und liest dieselben sechs Bereiche, aber sie liest gespeicherte Ergebnisse. Ein Objekt, das je Motor und je Gelegenheit einen eigenen Lauf mit Fortschritt festhält, ist ein eigener Bau mit eigener Tabelle, und ohne ihn wäre ein Fortschrittsbalken eine Behauptung.
- **Der Wirkungsdurchschnitt in der Communication Intelligence Engine („⌀ 8,7/10 bei Politik-Themen“)**: das Werkzeug misst die Wirkung eines einzelnen Textes nirgends, also gibt es keine Zeilen, über die sich mitteln ließe. Die Kachel bleibt an ihrem Platz und trägt, was gespeichert ist. Der Durchschnitt kommt, wenn die Wirkungsmessung kommt.
- **Die Reiter Performance und Historie auf der Seite**: die sechs übrigen führen auf gebaute Mandatsseiten. Für Performance je Gelegenheit gibt es keine Messung, und Historie ist die Spur unten, die schon auf der Seite steht.
- **Neue Menüpunkte aus der Vorlage (Command Center, New Business, Operations, Management, Portal, Growth, Intelligence)**: GEL-03 streicht den bestehenden Rahmen neu, es baut ihn nicht um. Jeder dieser Punkte ist ein eigener Arbeitsbereich mit eigenen Seiten und gehört nicht in den Anhang einer Detailseite.
- **Ein eigener gespeicherter Status neben „steht“ und „verworfen“**: die Statuswahl im Kopf zeigt den Zustand, der aus den vorhandenen Zeilen folgt, und „Aktivieren“ öffnet den Anlass, was heute schon die Handlung ist, die eine Gelegenheit aktiv macht. Eine zusätzliche Spalte, die dasselbe noch einmal behauptet, kann von der Wirklichkeit abweichen.
- **Ein Ereignisprotokoll als eigene Tabelle**: die Chronik wird aus vorhandenen Zeitstempeln gelesen. Eine zweite Wahrheit über dieselben Ereignisse müsste gepflegt werden und könnte auseinanderlaufen.
- **Redaktion der Storyline auf der Seite**: das Bearbeiten eines Textes gehört auf die Texte-Seite, wo es schon steht. Das Dossier zeigt und verlinkt.

## Summary

Heute ist eine Gelegenheit ein Kärtchen auf Heute: Schlagzeile, Restzeit, ein Satz
zum Stehen, zwei Knöpfe. Wer mehr wissen will, sucht es sich über fünf Seiten
zusammen, und zwar genau in den Stunden, in denen das Fenster zuläuft.

Danach hat jede Gelegenheit eine Seite. Sie zeigt, was gerade über das Thema läuft
und welche Medien es tragen, was das Mandat dazu belegen kann, welche Texte schon
hängen und welcher davon noch ungeprüft ist, wen man ansprechen könnte und ob
dieser Jemand überhaupt erreichbar ist, und was als nächstes zu tun wäre. Alles
davon steht heute schon in der Datenbank; es stand nur nie an einem Ort beieinander.

Die Seite kostet beim Ansehen nichts: sie ruft kein Modell und legt nichts an. Und
weil sie nach dem Ablauf des Fensters lesbar bleibt, ist sie hinterher der Beleg,
was zu dem Zeitpunkt bekannt war und wann was entschieden wurde.

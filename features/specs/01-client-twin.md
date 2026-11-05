# 01 Client Twin

> Wir müssen einen neuen Kunden anlegen können und das OS mit möglichst vielen
> Informationen füttern. Das haben wir ja jetzt schon zum Teil. Ich habe das mal
> weitergedacht und einen „Fragebogen" entwickelt, den ich gerne immer als
> Grundlage nehmen und hochladen wollen würde. Vielleicht ist der ein bisschen
> arg umfangreich und deshalb so auch nicht umsetzbar? Müssen wir mal testen.
> Man kann ja auch da mit Pflichtinfos und optionalen Infos arbeiten.
>
> Ich befülle den gerade für Carbon Farming und für Calibre. Ist halt echt
> umfangreich. Bin mal gespannt, wie lang ich dafür brauche inkl. Abstimmung mit
> Marc und Alex. Ich tracke da mal die Zeit, damit ich weiß, wie viel Onboarding
> Fee wir in Zukunft verlangen müssen. Das wäre aber z.B. was, das ein
> Werke/Prakti übernehmen könnte zukünftig.
>
> Wichtig wäre hier, dass Informationen nicht einfach nur als Text irgendwo
> gespeichert werden. Das System sollte möglichst unterscheiden können zwischen:
>
> - Bestätigter Fakt
> - Kundenaussage
> - External Observation
> - Unsere Hypothese
>
> Zusätzlich sollten (soweit vorhanden) Quelle, Stand/Aktualität, Confidence und
> Vertraulichkeit hinterlegt werden.
>
> Beispiel: "400 % THG-Minderung bei BeyondZero"
> Das darf für das System nicht dasselbe sein wie ein unabhängig bestätigter
> Fakt. Das ist zunächst ein Unternehmensclaim und muss entsprechend
> gekennzeichnet werden.
>
> Der Twin muss außerdem jederzeit manuell bearbeitbar sein. Wir müssen Dinge
> korrigieren, ergänzen, bestätigen oder verwerfen können.
>
> Und ich würde gerne einen einfachen Completeness Status haben. Also zum
> Beispiel: Carbon Farming Twin 84 % complete
>
> Dann sehen wir sofort, wie gut unser OS diesen Kunden schon kennt und wo noch
> Wissenslücken bestehen.

## Was heute schon steht

- 17 Profilfelder mit Quelle und Quelltitel je Wert (`ClientFact`)
- `filled_by` trennt Mensch von Maschine; eine Historienstufe (`superseded_*`)
- Handbearbeitung ist vor KI-Überschreiben geschützt (`profile_refresh.may_replace`)
- Vollständigkeit wird auf dem Desk berechnet (Profil 40 %, Kickoff 40 %, Guide 20 %)
- Kickoff-Fragebogen mit 20 Fragen, Abschnitten und Fortschritt

## Was fehlt

- Die vier Herkunftsklassen als eigenes Feld
- Confidence, Vertraulichkeit, Stand-Datum
- Mehrere Aussagen je Feld statt einem Wert je Feld
- Import des großen Fragebogens (Tabelle), mit Pflicht-/Optionalfeldern

## Offen

Der Fragebogen liegt in einem geschützten Google-Drive-Dokument. Ohne die
Feldliste lässt sich weder die Pflicht-/Optional-Trennung noch der Import bauen.

## Marke zuerst, Unternehmen dahinter (5. November 2026)

> im aktuellen kunden profil fragen wir unternehmen ab und dann auch die
> möglichkeit verschiedene marken unter dem kunden hinzuzufügen. also quasi
> welche marke wir beraten. idealerweise ist das Logo / und das gesamte Profil
> auf basis der Marke anlegen und dann die unternehmensform dahinter.
> […] bitte frage auch die Unternehmen dahinter ab (aber als Optional) erst
> die marke und dann das unternehmen

Festgelegt: **Je beratene Marke ein Mandant.** Name, Logo, Website, Profil,
Recherche und Monitoring richten sich nach der Marke. Das Unternehmen dahinter
(Rechtsträger mit Rechtsform, z. B. „Zenchef SAS“) ist das Feld `legal_name`
(Migration 0068): beim Anlegen nach Marke und Website gefragt, optional, in
Profil und Überblick unter der Marke genannt, in Einstellungen und auf der
Mandantenkarte änderbar. Die Recherche bekommt Marke und Unternehmen getrennt
und ermittelt das Unternehmen, wenn es leer ist. Zwei Marken desselben
Unternehmens sind zwei Mandanten mit demselben `legal_name`.

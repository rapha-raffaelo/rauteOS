# 10 Aufgaben, LinkedIn und Sales CRM

Schritt 6 aus [09-ui-umbau.md](09-ui-umbau.md). Der rauteOS-Prototyp zeigt drei
Bereiche, die es in RauteOS noch nicht gab. Das README des Prototyps (Abschnitt
6, „Datenobjekte“) nennt die Felder als Arbeitsgrundlage. Hier steht, was davon
gebaut wird, und was bewusst noch nicht.

## Grundsätze

- **Von Hand gepflegt, nichts automatisch.** Keine Aufgabe entsteht aus einer
  E-Mail, kein Deal aus einem Postfach angelegt. Ein Beitrag geht nur auf
  LinkedIn, wenn eine Person ihn postet oder einplant (siehe unten). Das sind die Integrationen aus Abschnitt 7 des READMEs,
  und jede braucht eigene Berechtigungs- und Freigaberegeln. Die Tabellen sind
  so angelegt, dass diese Integrationen später Zeilen schreiben können.
- **Ein Mandant ist optional, wo es um Agenturarbeit geht.** Eine Aufgabe kann
  einem Mandanten gehören oder der Agentur. Ein LinkedIn-Beitrag gehört immer
  einem Mandanten. Ein Deal gehört nie einem: Er ist ein möglicher Kunde.
- **Löschen ist endgültig, Erledigen nicht.** Eine erledigte Aufgabe bleibt mit
  Datum stehen; ein verlorener Deal bleibt mit seiner Stufe stehen.

## Aufgaben (`tasks`)

| Feld | Bedeutung |
|---|---|
| `client_id` | Mandant, oder leer für Agenturarbeit |
| `title` | Was zu tun ist, höchstens 200 Zeichen |
| `note` | Freitext |
| `priority` | `hoch`, `mittel`, `niedrig` |
| `status` | `offen`, `in_arbeit`, `erledigt` |
| `due_on` | Fälligkeit (Datum), optional |
| `owner` | Wer es macht, Freitext |
| `context_href` | Link auf den auslösenden Vorgang (Story, Text, Kontakt), optional |
| `created_at`, `done_at` | Angelegt, erledigt |

Desk: „Offene Aufgaben“ als Kennzahl (davon heute fällig), und „Heute
priorisiert“ zeigt zuerst überfällige und heute fällige Aufgaben, dann die
offenen Entscheidungen. Seite `/aufgaben` mit Anlegen, Status ändern,
Erledigen, Löschen und Filter nach Status und Mandant.

## LinkedIn (`linkedin_posts`)

| Feld | Bedeutung |
|---|---|
| `client_id` | Mandant (Pflicht) |
| `author` | Autor oder Sprecher, Freitext |
| `title` | Arbeitstitel |
| `body` | Text des Beitrags |
| `status` | `idee`, `entwurf`, `freigabe`, `geplant`, `veroeffentlicht` |
| `planned_on` | Geplanter Tag, optional |
| `published_url` | Link nach Veröffentlichung, optional |
| `created_at`, `updated_at` | |

| `asset_id` | Der LinkedIn-Text aus RauteOS, aus dem der Beitrag stammt, optional |
| `context_href` | Die Chance, die der Beitrag aufgreift, optional |
| `post_at` | Wann RauteOS den Beitrag postet, optional |
| `post_as` | Über wessen LinkedIn-Konto (RauteOS-Anmeldeadresse) |
| `linkedin_urn` | Was LinkedIn für den geposteten Beitrag antwortete |
| `post_error` | Warum der letzte Versuch nicht geklappt hat |

Seite `/linkedin`: Beiträge nach Status gruppiert, Anlegen, Bearbeiten,
Status wechseln.

### Posten von Hand (Standard)

Solange keine LinkedIn-App eingerichtet ist (die braucht eine
Unternehmensseite), steht an jeder Karte mit Text „In LinkedIn öffnen“. Der
Knopf kopiert den Text in die Zwischenablage und öffnet LinkedIn mit dem
Text im Eingabefeld. Ob LinkedIn das Feld füllt, ist nicht dokumentiert,
deshalb die Kopie. Die Person postet in ihrem eigenen Login und trägt den
Link ein. Dann steht der Beitrag auf „Veröffentlicht“. Angenommen werden nur
Links zu linkedin.com oder lnkd.in.

### Posten über LinkedIn (sobald eine App eingerichtet ist)

Jede Person verbindet auf `/linkedin` ihr eigenes LinkedIn-Profil
(„Sign In with LinkedIn using OpenID Connect“ und „Share on LinkedIn“,
Scopes `openid profile w_member_social`, ohne Prüfung durch LinkedIn).
Danach steht an jeder Karte mit Text „Jetzt auf LinkedIn posten“ (mit
Rückfrage) und „Einplanen“ mit Datum und Uhrzeit.

- Gepostet wird öffentlich als die Person, die gedrückt oder eingeplant hat.
- Ein Beitrag mit `linkedin_urn` geht nie ein zweites Mal raus.
- Der Scheduler prüft jede Minute. Er nimmt einen fälligen Beitrag aus dem
  Plan, bevor er postet. Ein Fehler steht danach an der Karte und wird nicht
  von selbst wiederholt.
- Ohne Refresh-Token gilt eine Verbindung 60 Tage. Sieben Tage vorher bittet
  die Seite um eine neue Verbindung. Ein Termin nach dem Ablauf wird
  abgelehnt.
- Die Tokens liegen in `linkedin_tokens.json` neben der Datenbank (0600),
  nie in einer Tabelle.
- Eine Karte, die von „Geplant“ weggeschoben wird, ist nicht mehr eingeplant.

Darüber „Vorschläge aus RauteOS“: die in einer Chance geschriebenen
LinkedIn-Posts (Format `linkedin`) und die offenen Chancen der aktiven
Mandanten. „Übernehmen“ legt eine Karte an, ein freigegebener Text startet in
„Freigabe“, ein Entwurf in „Entwurf“, eine Chance als „Idee“. Jeder Text und
jede Chance wird höchstens einmal übernommen; von selbst landet nichts auf dem
Board.

## Sales CRM (`deals`)

| Feld | Bedeutung |
|---|---|
| `company` | Unternehmen |
| `contact_name`, `contact_email` | Ansprechpartner |
| `stage` | `lead`, `gespraech`, `angebot`, `verhandlung`, `gewonnen`, `verloren` |
| `value_eur` | Monatliches Potenzial in Euro, optional |
| `owner` | Wer betreut, Freitext |
| `next_step`, `next_step_on` | Nächster Schritt und Datum |
| `note` | Freitext |
| `created_at`, `updated_at`, `closed_at` | `closed_at` bei gewonnen/verloren |

Seite `/sales`: Pipeline als Spalten je Stufe mit Summe des Potenzials,
Anlegen, Bearbeiten, Stufe wechseln. Ein gewonnener Deal legt **keinen**
Mandanten an: Das bleibt ein bewusster Schritt über „Neuer Mandant“.

## Noch nicht

Aufgaben aus E-Mails, Wiedervorlagen mit Benachrichtigung, Posten auf
Unternehmensseiten und LinkedIn-Metriken (beides braucht die Community
Management API mit Prüfung durch LinkedIn), E-Mail-Zuordnung zu Deals, Aktivitätsverlauf je Deal.

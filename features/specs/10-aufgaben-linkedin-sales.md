# 10 Aufgaben, LinkedIn und Sales CRM

Schritt 6 aus [09-ui-umbau.md](09-ui-umbau.md). Der rauteOS-Prototyp zeigt drei
Bereiche, die es in RauteOS noch nicht gab. Das README des Prototyps (Abschnitt
6, „Datenobjekte“) nennt die Felder als Arbeitsgrundlage. Hier steht, was davon
gebaut wird, und was bewusst noch nicht.

## Grundsätze

- **Von Hand gepflegt, nichts automatisch.** Keine Aufgabe entsteht aus einer
  E-Mail, kein Beitrag wird auf LinkedIn veröffentlicht, kein Deal aus einem
  Postfach angelegt. Das sind die Integrationen aus Abschnitt 7 des READMEs,
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

Seite `/linkedin`: Beiträge nach Status gruppiert, Anlegen, Bearbeiten,
Status wechseln. Kein Publishing über die API.

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

Aufgaben aus E-Mails, Wiedervorlagen mit Benachrichtigung, LinkedIn-Publishing
und -Metriken, E-Mail-Zuordnung zu Deals, Aktivitätsverlauf je Deal.

# RAUTE Communications Guide

Die neun Engine-Dokumente aus dem Drive-Ordner „PR & Communications“, im
Original. Sie beschreiben, was RAUTE OS je Bereich leisten soll. Die Teile,
die festlegen, **wie RAUTE schreibt**, sind als Bausteine in
`newspulse/src/newspulse/blocks/` hinterlegt. Jeder Prompt, der einen Text
für einen Leser schreibt, bindet sie ein, egal welches Modell ihn ausführt
(Claude, Gemini, Codex). Dasselbe gilt für Ask RAUTE.

In RauteOS stehen sie unter **Einstellungen → Format & Text**: der
Communications Guide als eigener Baustein ganz oben, darunter die Bereiche,
in die seine übrigen Regeln einsortiert sind. Jeder Baustein ist dort
bearbeitbar und hat eine Versionsgeschichte. Eine Änderung gilt ab dem
nächsten erzeugten Text.

## Was wo steht

| Baustein (Einstellungen) | Datei | Aus dem Guide |
| --- | --- | --- |
| RAUTE Communications Guide | `comms_guide.txt` | Communication Asset Engine: Vorgehen vor dem Schreiben, Platzhalter, Corporate Language, Sprecherton, Zielgruppen, Zitate als Entwürfe, journalistisches Red Team |
| Formate | `comms_formats.txt` | Communication Asset Engine: Formatlogik, Pressemitteilung, Statement, Q&A, Gastbeitrag, Briefing. Nur in den Prompts, die eines dieser Formate schreiben, und im Gegenlesen |
| Sprache & Hausstil | `house_style.txt` | Quality & Verification: KI-Sprache, Werblichkeit |
| Belege & Nachweise | `evidence.txt` | Quality & Verification: Claims, Superlative, Zahlen, Studien, Kausalität, heikle Claims |
| Fakten statt Erfindungen | `no_invention.txt` | Quality & Verification: Widersprüche nicht still auflösen, Fakten nicht still ändern |
| Krisenkommunikation | `crisis_discipline.txt` | Reputation & Crisis: Fakt, Vorwurf, Gerücht, Holding Statement, Antwortlogik, Konsistenz über Kanäle |
| Journalistischer Mehrwert | `journalistic_value.txt` | Market & Opportunity: Warum jetzt, warum dieser Absender |
| Blickwinkel für Pitches | `pitch_angle.txt` | Market & Opportunity: Spannungsfelder |
| Aufbau von Pitches | `pitch_shape.txt` | Communication Asset: Betreffzeile, Nachfassen |
| Positionierung | `position.txt` | Positioning: eine Kernbotschaft zuerst, Gegenpositionen |
| Quellenordnung | `quellenordnung.txt` | Quality & Verification: Primärquellen |
| Zitate & Fremdmaterial | `quoted_material.txt` | Quality & Verification: Zitat- und Urheberrecht |
| Grenzen & Ablehnung | `refusal.txt` | Communication Asset: Assets priorisieren |
| Fehlalarme vermeiden | `false_alarm.txt` | Quality & Verification: Fehler, Risiko, Verbesserung, Geschmacksfrage |

## Was bewusst nicht in den Bausteinen steht

Der größte Teil der Dokumente beschreibt Funktionen, Datenquellen,
Kennzahlen und das Zusammenspiel der Engines, etwa Monitoring, Share of Voice,
Journalisten-Matching oder GEO-Messung. Das sind Produktanforderungen und
keine Schreibregeln. Sie gehören in die Spezifikationen unter
`features/specs/` und würden in jedem Prompt nur Platz kosten.

Kundenspezifisches wie Positionierung, Kernbotschaften, No-Gos und Corporate
Language steht nicht hier, sondern im Kommunikations-Guide des jeweiligen
Mandanten. Der Communications Guide sagt nur, dass er verbindlich ist.

## Pflege

Ändert sich ein Engine-Dokument, wird der betroffene Baustein angepasst und
die Prompt-Goldens neu erzeugt:

    cd newspulse && NEWSPULSE_REGOLD=1 uv run pytest tests/test_brain.py

Der Test `test_every_prompt_that_writes_prose_follows_the_communications_guide`
sorgt dafür, dass ein neuer Schreib-Prompt den Guide nicht vergessen kann.
`test_only_the_format_prompts_carry_the_format_rules` hält die Formatregeln
aus allen anderen Prompts heraus: Ein Pitch braucht die Q&A-Regel nicht, und
jeder Aufruf bezahlt jedes Wort in Tokens.

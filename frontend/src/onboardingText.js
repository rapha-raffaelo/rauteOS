// The customer questionnaire in German and English. Keyed by the German
// sentence, like the server's translator, so the page reads in its own words.
const EN = {
  'Speichern nicht möglich. Bitte erneut versuchen. Ihre Eingabe bleibt hier.': 'Could not save. Please try again. Your input stays here.',
  'Dieser Link ist unvollständig. Bitte öffnen Sie den persönlichen Link von raute+kopf.': 'This link is incomplete. Please open the personal link from raute+kopf.',
  'Ein paar Worte genügen. Oder wählen Sie „Später beantworten“.': 'A few words are enough. Or choose “Answer later”.',
  'Ihr Start mit raute+kopf.': 'Your start with raute+kopf.',
  'Ihr Fragebogen wird geladen …': 'Loading your questionnaire …',
  'Erneut versuchen': 'Try again',
  'Demo · nur in diesem Tab gespeichert': 'Demo · saved in this tab only',
  'Neustart': 'Restart',
  'Ihre Perspektive.': 'Your perspective.',
  'Die Fakten stehen. Jetzt Ihre Perspektive.': 'The facts are in place. Now your perspective.',
  'Fragen · jede ist freiwillig · in mehreren Etappen möglich': 'questions · each one optional · can be done in several sittings',
  'Weiter, wo ich war': 'Continue where I left off',
  'Los geht’s': 'Let’s start',
  'Speichern & später weitermachen — jederzeit.': 'Save and continue later, at any time.',
  'Das wissen wir schon.': 'What we already know.',
  'Stimmt das so?': 'Is this correct?',
  'Bearbeitung abbrechen': 'Cancel editing',
  'Angaben bearbeiten': 'Edit details',
  'Wird gespeichert …': 'Saving …',
  'Speichern & weiter': 'Save and continue',
  'Stimmt, weiter': 'Correct, continue',
  'Gespeicherte Fragen': 'Saved questions',
  'Antwortvorschläge': 'Suggested answers',
  'Ihre Antwort': 'Your answer',
  'Ihre Antwort …': 'Your answer …',
  'Zurück zu den Unternehmensangaben': 'Back to the company details',
  'Vorherige Frage': 'Previous question',
  'Antworten ansehen': 'Review answers',
  'Weiter': 'Next',
  'Später beantworten': 'Answer later',
  'So klingt Ihr Unternehmen.': 'This is how your company sounds.',
  'Antworten gespeichert': 'answers saved',
  'Fragen noch offen.': 'questions still open.',
  'Unternehmensangaben': 'Company details',
  'Audio gespeichert': 'Audio saved',
  'Noch offen — später beantworten': 'Still open, answer later',
  'Bearbeiten ↗': 'Edit ↗',
  'Wird abgeschlossen …': 'Finishing …',
  'Abschließen': 'Finish',
  'DER ANFANG IST GEMACHT': 'A GOOD START',
  'Danke für': 'Thank you for',
  'Ihre Einblicke.': 'your insights.',
  'Demo abgeschlossen.': 'Demo finished.',
  'Antworten lokal gespeichert.': 'answers saved locally.',
  'Ihre': 'Your',
  'Antworten sind gespeichert.': 'answers are saved.',
  'Sie können Ihre Antworten jederzeit bearbeiten.': 'You can edit your answers at any time.',
  'Über diesen Link können Sie Ihre Antworten weiter bearbeiten.': 'You can keep editing your answers through this link.',
  'Sprache': 'Language',
  // Recording and transcription
  'Audio konnte nicht verarbeitet werden. Bitte erneut versuchen.': 'The audio could not be processed. Please try again.',
  'Maximal 25 MB pro Datei.': 'Maximum 25 MB per file.',
  'Die Aufnahme ist leer. Bitte erneut versuchen.': 'The recording is empty. Please try again.',
  'Aufnahme unterbrochen. Bitte erneut versuchen.': 'Recording interrupted. Please try again.',
  'Aufnahme': 'Recording',
  'Mikrofon nicht verfügbar. Bitte Zugriff erlauben oder eine Datei hochladen.': 'Microphone not available. Please allow access or upload a file.',
  'Diese Datei kann hier nicht abgespielt werden. Sie können sie trotzdem hochladen.': 'This file cannot be played here. You can still upload it.',
  'Speichern als': 'Save as',
  'Transkript': 'Transcript',
  'Audio': 'Audio',
  'Aufnahme fortsetzen': 'Resume recording',
  'Aufnahme starten': 'Start recording',
  'Audio abspielen': 'Play audio',
  'Aufnahme pausieren': 'Pause recording',
  'Wiedergabe pausieren': 'Pause playback',
  'Stopp': 'Stop',
  '10 Sekunden zurück': 'Back 10 seconds',
  '10 Sekunden vor': 'Forward 10 seconds',
  'Aufnahme löschen': 'Delete recording',
  'Audiodatei auswählen': 'Choose audio file',
  'Pause': 'Paused',
  'Audiodatei hochladen': 'Upload audio file',
  'Wiedergabeposition': 'Playback position',
  'Original speichern · KI-Transkript zusätzlich': 'Keep the original · AI transcript in addition',
  'Nur Text speichern · Audio danach löschen': 'Keep text only · audio deleted afterwards',
  'Demo: nur lokal': 'Demo: local only',
  'Verarbeitung durch Deepgram': 'Processed by Deepgram',
  'Wird übertragen …': 'Uploading …',
  'Audio übernehmen': 'Use audio',
  'Transkript erstellen': 'Create transcript',
  'KI-Transkription über einen persönlichen Kundenlink testen.': 'Try AI transcription through a personal customer link.',
  'Transkription wird eingerichtet. Audio kann bereits gespeichert werden.': 'Transcription is being set up. Audio can already be saved.',
  'Transkript bereit': 'Transcript ready',
  'Audio lokal übernommen': 'Audio kept locally',
  'KI erstellt das Transkript …': 'AI is creating the transcript …',
  'Audio gespeichert · Transkription wartet auf Einrichtung': 'Audio saved · transcription awaiting setup',
  'Erneut transkribieren': 'Transcribe again',
};

export const LANGUAGES = ['de', 'en'];
const STORAGE = 'raute-onboarding-language';

export function say(language, text) {
  return language === 'en' ? EN[text] ?? text : text;
}

// German unless the customer chose English here before. Not from the browser:
// plenty of German executives run an English browser.
export function initialLanguage() {
  try {
    const stored = localStorage.getItem(STORAGE);
    if (LANGUAGES.includes(stored)) return stored;
  } catch {}
  return 'de';
}

export function rememberLanguage(language) {
  try { localStorage.setItem(STORAGE, language); } catch {}
}

export const missingTranslations = texts => texts.filter(text => !(text in EN));

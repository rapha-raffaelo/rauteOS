import React, {useEffect, useId, useRef, useState} from 'react';

const presets = [
  ['Kundenmail', 'Schreibe eine kurze Kundenmail zu diesem Anlass. Erkläre die Relevanz und bitte um Rückmeldung zum vorgeschlagenen Vorgehen.'],
  ['LinkedIn-Post', 'Schreibe einen LinkedIn-Post zu diesem Anlass: ein klarer Einstieg, eine belegte Position und kurze Absätze.'],
  ['Statement', 'Schreibe ein kurzes Statement zu diesem Anlass. Verwende nur belegte Aussagen und erfinde keine Zitate oder Sprecher.'],
  ['Talking Points', 'Schreibe fünf prägnante Talking Points zu diesem Anlass für ein Hintergrundgespräch.'],
  ['Q&A', 'Schreibe fünf relevante Fragen und Antworten zu diesem Anlass. Kennzeichne fehlende Belege und offene Fragen.'],
];

export async function consumeDraft(response, onEvent) {
  if (!response.ok || !response.headers.get('content-type')?.includes('text/event-stream')) {
    const data = await response.json().catch(() => null);
    throw new Error(response.status === 401 ? 'Sitzung abgelaufen. Bitte erneut anmelden.'
      : typeof data?.detail === 'string' ? data.detail : 'Die Texterstellung konnte nicht gestartet werden.');
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '', saved = false;
  try {
    while (true) {
      const {value, done} = await reader.read();
      buffer += decoder.decode(value, {stream: !done}).replace(/\r\n/g, '\n');
      let boundary;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2);
        const type = frame.match(/^event: (.+)$/m)?.[1];
        const payload = frame.match(/^data: (.+)$/m)?.[1];
        if (!type || !payload) continue;
        const data = JSON.parse(payload);
        if (type === 'error') throw new Error(data);
        if (type === 'saved') saved = true;
        onEvent(type, data);
      }
      if (done) break;
    }
    if (!saved) throw new Error('Die Verbindung wurde unterbrochen. Der angezeigte Zwischenstand ist noch kein bestätigter Entwurf.');
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}

export function CustomMessageComposer({clientId, angleId, initialVersion = '', released = false}) {
  const id = useId();
  const [instruction, setInstruction] = useState('');
  const [preset, setPreset] = useState('');
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(null);
  const [version, setVersion] = useState(initialVersion);
  const controller = useRef(null);
  useEffect(() => () => controller.current?.abort(), []);
  const words = preview.trim() ? preview.trim().split(/\s+/u).length : 0;
  async function write(event) {
    event.preventDefault();
    if (controller.current || !instruction.trim()) return;
    const abort = new AbortController(); controller.current = abort;
    setBusy(true); setError(''); setSaved(null); setPreview(''); setStatus('Auftrag wird vorbereitet …');
    try {
      const response = await fetch(`/api/v1/clients/${clientId}/impulses/${angleId}/custom-draft`, {
        method: 'POST', credentials: 'same-origin', signal: abort.signal,
        headers: {'Content-Type': 'application/json', Accept: 'text/event-stream'},
        body: JSON.stringify({instruction, version}),
      });
      await consumeDraft(response, (type, data) => {
        if (type === 'status') setStatus(data);
        if (type === 'preview') setPreview(data);
        if (type === 'saved') {
          const result = JSON.parse(data);
          setSaved(result); setPreview(result.body); setVersion(result.version); setStatus(result.notice);
        }
      });
    } catch (err) { if (err.name !== 'AbortError') setError(err.message); }
    finally { controller.current = null; setBusy(false); }
  }
  return <section className="custom-composer" data-editing={busy || !!instruction || !!saved ? 'true' : 'false'} aria-labelledby={`${id}-heading`}>
    <div className="custom-composer__heading"><span className="custom-composer__eyebrow">WEITERER TEXT</span><h3 id={`${id}-heading`}>Was möchtest du daraus schreiben?</h3><p>Wähle eine Vorlage oder beschreibe deinen eigenen Auftrag.</p></div>
    <form onSubmit={write}>
      <div className="custom-composer__presets" role="group" aria-label="Textvorlagen">
        {presets.map(([label, text]) => <button key={label} type="button" aria-pressed={preset === label} disabled={busy || released}
          onClick={() => {setPreset(label); setInstruction(text);}}>{label}</button>)}
      </div>
      <label htmlFor={`${id}-instruction`}>Dein Auftrag</label>
      <textarea id={`${id}-instruction`} value={instruction} maxLength={5000} rows={4} disabled={busy || released}
        placeholder="Zum Beispiel: Eine kurze Nachricht an unseren Kunden. Erkläre den Anlass und schlage ein Hintergrundgespräch vor."
        onChange={event => {setInstruction(event.target.value); setPreset('');}} />
      {version && !released && <p className="custom-composer__hint">Ein neuer Auftrag ersetzt den bisherigen Entwurf der eigenen Nachricht. Die Pressemitteilung bleibt erhalten.</p>}
      {released && <p className="custom-composer__hint">Die eigene Nachricht ist bereits freigegeben und kann nicht ersetzt werden.</p>}
      <div className="custom-composer__footer"><span>Auf Basis dieses Anlasses und deines Profils.</span><button className="btn btn--go btn--big" type="submit" disabled={busy || released || !instruction.trim()}>{busy ? 'Nachricht wird geschrieben …' : 'Eigene Nachricht schreiben'}</button></div>
    </form>
    {(busy || saved || error) && <div className="custom-composer__result" aria-busy={busy}>
      {busy && <progress aria-label="Nachricht wird erstellt" />}
      {saved && !busy && <progress aria-label="Nachricht fertiggestellt" max="1" value="1" />}
      <div className="custom-composer__status"><span role="status">{error ? 'Erstellung unterbrochen' : status}</span><span>{words} Wörter{busy ? ' geschrieben' : ''}</span></div>
      {error && <p role="alert">{error}</p>}
      {preview && <div className="custom-composer__preview" aria-label={saved ? 'Gespeicherter Entwurf' : 'Live-Vorschau'}>{saved && <h4>{saved.title}</h4>}{preview}</div>}
      {saved && <a className="btn btn--ghost" href={saved.url}>Entwurf bearbeiten und Prüfhinweise ansehen →</a>}
    </div>}
  </section>;
}

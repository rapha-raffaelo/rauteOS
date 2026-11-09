import React, { useState } from 'react';

// A customer's recordings under the question they answer (newspulse.web.routes.
// customer_audio). The transcript is raw material: the consultant copies what
// matters into the answer beside it and saves that as the question's answer.
// Then the recording goes to the archive, or is deleted.

const when = value => value ? new Date(value).toLocaleString('de-DE', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'}) : '';

async function call(path, method, body) {
  const response = await fetch(path, {method, credentials: 'same-origin',
    headers: {Accept: 'application/json', ...(body ? {'Content-Type': 'application/json'} : {})},
    ...(body ? {body: JSON.stringify(body)} : {})});
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : 'Speichern fehlgeschlagen. Bitte erneut versuchen.');
  return data;
}

const Trash = () => <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" aria-hidden="true">
  <path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/></svg>;

function Recording({clientId, item, onChanged}) {
  const base = `/client/${clientId}/onboarding-audio/${item.id}`;
  const [answer, setAnswer] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function act(path, method, body, after) {
    setBusy(true); setError('');
    try { await call(base + path, method, body); after?.(); await onChanged(); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  const transcript = item.status === 'ready' ? item.transcript
    : item.status === 'failed' ? item.note || 'Transkription fehlgeschlagen.'
    : item.transcription_configured ? 'Wird transkribiert …' : 'Transkription ist noch nicht eingerichtet.';
  return <article className="qa-rec" id={`audio-${item.id}`}>
    <header className="qa-rec__head">
      <span>Audio vom Kunden · {when(item.created_at)}</span>
      <button type="button" className="qa-icon" disabled={busy} aria-label="Aufnahme verwerfen" title="Verwerfen"
        onClick={() => { if (window.confirm('Diese Aufnahme endgültig löschen?')) act('', 'DELETE'); }}><Trash /></button>
    </header>
    {item.retained && <audio controls preload="none" src={`${base}/content`} />}
    <div className="qa-rec__cols">
      <div><p className="qa-rec__label">Transkript</p>
        <p className={`qa-rec__transcript${item.status === 'ready' ? '' : ' qa-rec__transcript--wait'}`}>{transcript}</p>
        {item.status === 'failed' && <button type="button" className="btn btn--quiet" disabled={busy} onClick={() => act('/retry', 'POST')}>Erneut transkribieren</button>}</div>
      <form onSubmit={e => { e.preventDefault(); act('/answer', 'POST', {value: answer}, () => setAnswer('')); }}>
        <label className="qa-rec__label" htmlFor={`answer-${item.id}`}>Antwort aus dem Audio</label>
        <textarea id={`answer-${item.id}`} value={answer} maxLength={20000} disabled={busy}
          placeholder="Das Wichtige aus dem Transkript …" onChange={e => setAnswer(e.target.value)} />
        <div className="qa-rec__acts">
          <button type="submit" className="btn btn--go" disabled={busy || !answer.trim()}>Als Antwort speichern</button>
          {item.answer_fact_id && <button type="button" className="btn" disabled={busy} onClick={() => act('/archive', 'POST')}>Ins Archiv</button>}
        </div>
        {item.answer_fact_id && <p className="qa-rec__done" role="status">Als Antwort gespeichert.</p>}
      </form>
    </div>
    {error && <p role="alert" className="twin-error">{error}</p>}
  </article>;
}

export function QuestionAudio({clientId, items, onChanged}) {
  if (!items.length) return null;
  return <div className="qa-audio">{items.map(item => <Recording key={item.id} clientId={clientId} item={item} onChanged={onChanged} />)}</div>;
}

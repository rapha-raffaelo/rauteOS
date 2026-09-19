import React, {useEffect, useRef, useState} from 'react';

export function AutoPressRelease({clientId, angleId, onState}) {
  const [state, setState] = useState({status: 'running'});
  const [attempt, setAttempt] = useState(0);
  const onStateRef = useRef(onState); onStateRef.current = onState;
  useEffect(() => {
    const controller = new AbortController();
    let timer, stopped = false;
    const endpoint = `/api/v1/clients/${clientId}/impulses/${angleId}/press-release`;
    async function check(method = 'GET') {
      try {
        const response = await fetch(endpoint + (method === 'POST' && attempt ? '?retry=true' : ''), {
          method, credentials: 'same-origin', signal: controller.signal,
          headers: {Accept: 'application/json', ...(method === 'POST' ? {'Content-Type': 'application/json'} : {})},
          ...(method === 'POST' ? {body: '{}'} : {}),
        });
        const data = response.headers.get('content-type')?.includes('application/json') ? await response.json() : null;
        if (!response.ok || !data) throw new Error(response.status === 401 ? 'Bitte erneut anmelden.' : 'Der Status konnte nicht geladen werden. Bitte erneut versuchen.');
        if (stopped) return;
        setState(data); onStateRef.current?.(data);
        if (['needed', 'queued', 'running', 'waiting'].includes(data.status)) {
          timer = setTimeout(() => check(data.status === 'needed' || data.status === 'waiting' ? 'POST' : 'GET'), data.status === 'running' ? 1500 : 4000);
        }
      } catch (error) {
        if (stopped || error.name === 'AbortError') return;
        const data = {status: 'failed', reason: error.message};
        setState(data); onStateRef.current?.(data);
      }
    }
    setState({status: 'running'});
    check('POST');
    return () => {stopped = true; clearTimeout(timer); controller.abort();};
  }, [clientId, angleId, attempt]);
  if (state.status === 'ready') return <div className="auto-release__draft">
    <p className="auto-release__meta">{state.label} · Bitte vor Verwendung prüfen.</p>
    <h3>{state.title}</h3><div className="auto-release__body">{state.body}</div>
    <a className="btn btn--ghost" href={state.url}>Bearbeiten und Prüfhinweise ansehen →</a>
  </div>;
  if (state.status === 'blocked') return <div className="auto-release__notice"><p>{state.reason}</p><a className="btn" href={state.url}>Profil ergänzen →</a></div>;
  if (state.status === 'failed') return <div className="auto-release__notice"><p role="alert">{state.reason}</p><button className="btn" onClick={() => setAttempt(value => value + 1)}>Erneut versuchen</button></div>;
  const queued = ['queued', 'waiting', 'needed'].includes(state.status);
  const checking = ['checking', 'storing'].includes(state.stage);
  const writing = state.stage === 'writing';
  const completedSteps = checking ? 2 : writing ? 1 : 0;
  return <div className="auto-release__loading">
    <div role="status" aria-live="polite">
      <span className="auto-release__eyebrow">{queued ? 'IM HINTERGRUND EINGEPLANT' : checking ? 'TEXT GESCHRIEBEN · PRÜFUNG LÄUFT' : writing ? 'PRESSEMITTEILUNG WIRD GESCHRIEBEN' : 'QUELLEN WERDEN VORBEREITET'}</span>
      <p>{queued ? 'Der Entwurf wird automatisch vorbereitet. Du kannst die Seite verlassen; der Auftrag bleibt gespeichert.' : checking ? 'Der Text ist vollständig. Quellen und Formulierungen werden jetzt geprüft.' : writing ? `${state.words || 0} Wörter geschrieben · Der Text wächst während der Erstellung.` : 'Die Quellen und das Unternehmensprofil werden für den Entwurf zusammengestellt.'}</p>
      <progress aria-label="Abgeschlossene Arbeitsschritte" max={3} value={completedSteps} />
      <ol className="auto-release__steps" aria-label="Arbeitsschritte">
        {['Vorbereiten', 'Schreiben', 'Prüfen'].map((label, index) => <li key={label} data-complete={index < completedSteps} aria-current={!queued && index === completedSteps ? 'step' : undefined}><span aria-hidden="true">{index < completedSteps ? '✓' : index + 1}</span>{label}</li>)}
      </ol>
    </div>
    {state.preview && <section className="auto-release__live" aria-label="Live-Textvorschau">
      <header><strong>{checking ? 'Entwurf zur Prüfung' : 'Text entsteht gerade'}</strong><span>{state.words || 0} Wörter</span></header>
      <div className="auto-release__body">{state.preview}</div>
      <small>{checking ? 'Prüfung noch nicht abgeschlossen.' : 'Unvollständige Vorschau; noch kein fertiger Entwurf.'}</small>
    </section>}
  </div>;
}

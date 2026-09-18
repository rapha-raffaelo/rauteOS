import React, {useEffect, useRef, useState} from 'react';

export function AutoPressRelease({clientId, angleId, onState}) {
  const [state, setState] = useState({status: 'running'});
  const [attempt, setAttempt] = useState(0);
  const onStateRef = useRef(onState); onStateRef.current = onState;
  useEffect(() => {
    const controller = new AbortController();
    let timer, stopped = false, polls = 0;
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
        if (['needed', 'running', 'waiting'].includes(data.status)) {
          if (++polls > 300) throw new Error('Die Erstellung dauert länger. Bitte den Status erneut laden.');
          timer = setTimeout(() => check(data.status === 'needed' || data.status === 'waiting' ? 'POST' : 'GET'), 3000);
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
  return <div className="auto-release__loading" role="status">
    <span className="auto-release__eyebrow">{state.status === 'waiting' ? 'WARTET AUF FREIEN SCHREIBPLATZ' : 'ENTWURF WIRD VORBEREITET'}</span>
    <p>{state.status === 'waiting' ? 'Die Pressemitteilung wird automatisch vorbereitet, sobald der laufende Auftrag fertig ist.' : 'Die Pressemitteilung wird automatisch geschrieben und geprüft.'}</p>
    <progress aria-label="Pressemitteilung wird vorbereitet" />
    <span className="auto-release__skeleton" aria-hidden="true" /><span className="auto-release__skeleton" aria-hidden="true" /><span className="auto-release__skeleton" aria-hidden="true" />
  </div>;
}

import React, { useEffect, useRef, useState } from 'react';

export function OnboardingPage({ token = window.location.hash.slice(1) }) {
  const [data, setData] = useState(null), [error, setError] = useState('');
  const [screen, setScreen] = useState('welcome'), [index, setIndex] = useState(0);
  const [draft, setDraft] = useState(''), [busy, setBusy] = useState(false);
  const [prefillEdits, setPrefillEdits] = useState({}), [editingPrefill, setEditingPrefill] = useState(false);
  const [listening, setListening] = useState(false), [interim, setInterim] = useState('');
  const recognition = useRef(null), heading = useRef(null), touch = useRef(null), lock = useRef(false);
  const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
  const question = data?.questions[index];
  const dirty = (screen === 'question' && draft !== (data?.answers[question?.key]?.value || '')) || Object.keys(prefillEdits).length > 0;

  async function api(path = '', method = 'GET', body) {
    const response = await fetch('/api/onboarding' + path, {method, credentials: 'omit',
      headers: {'X-Onboarding-Token': token, 'Content-Type': 'application/json'},
      ...(body === undefined ? {} : {body: JSON.stringify(body)})});
    if (!response.ok) {
      const json = await response.json().catch(() => ({}));
      throw new Error(typeof json.detail === 'string' ? json.detail : 'Speichern nicht möglich. Bitte erneut versuchen. Ihre Eingabe bleibt hier.');
    }
    return response.json();
  }
  useEffect(() => {
    let active = true;
    if (!token) { setError('Dieser Link ist unvollständig. Bitte öffnen Sie den persönlichen Link von raute+kopf.'); return; }
    api().then(d => { if (active) {setData(d); if (d.completed) setScreen('done');} })
      .catch(e => {if (active) setError(e.message);});
    return () => { active = false; };
  }, [token]);
  useEffect(() => { heading.current?.focus(); }, [screen, index]);
  useEffect(() => {
    const warn = e => { if (dirty || busy || listening) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty, busy, listening]);
  useEffect(() => () => { if (recognition.current) { recognition.current.onresult = null; recognition.current.onend = null; recognition.current.abort(); } }, []);

  function openQuestion(i) {
    setIndex(i); setDraft(data.answers[data.questions[i].key]?.value || '');
    setError(''); setScreen('question');
  }
  function resume() {
    const next = data.questions.findIndex(q => !data.answers[q.key]);
    if (next === -1) setScreen('review');
    else openQuestion(next);
  }
  async function confirmPrefill() {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError('');
    try {
      await api('/prefill', 'POST', {corrections: prefillEdits});
      setData({...data, prefill_confirmed: true, prefill: data.prefill.map(p => ({...p, ...(prefillEdits[p.key] ? {customer_value: prefillEdits[p.key]} : {})}))});
      setPrefillEdits({}); setEditingPrefill(false); resume();
    } catch(e) {setError(e.message);}
    finally {lock.current = false; setBusy(false);}
  }
  async function saveAndMove(skip = false, target = index + 1) {
    if (lock.current || listening) return;
    if (!skip && !draft.trim()) {setError('Ein paar Worte genügen. Oder wählen Sie „Später beantworten“.'); return;}
    lock.current = true; setBusy(true); setError('');
    try {
      const answer = await api('/answers/' + question.key, 'PUT', {value: skip ? '' : draft, skipped: skip});
      const next = {...data, answers: {...data.answers, [question.key]: answer}};
      setData(next);
      if (target >= data.questions.length) setScreen('review');
      else {setIndex(target); setDraft(next.answers[next.questions[target].key]?.value || '');}
    } catch (e) { setError(e.message); }
    finally { lock.current = false; setBusy(false); }
  }
  function back() {
    if (dirty) {saveAndMove(false, index - 1); return;}
    openQuestion(index - 1);
  }
  function dictate() {
    if (listening) { recognition.current?.stop(); return; }
    if (!Speech) return;
    setError(''); setInterim('');
    const r = new Speech(); recognition.current = r;
    r.lang = 'de-DE'; r.continuous = true; r.interimResults = true;
    let base = draft.trim();
    r.onresult = e => {
      let final = '', pending = '';
      for (let i = 0; i < e.results.length; i++) {
        if (e.results[i].isFinal) final += e.results[i][0].transcript + ' ';
        else pending += e.results[i][0].transcript;
      }
      setDraft([base, final.trim()].filter(Boolean).join(' ').slice(0, 20000)); setInterim(pending);
    };
    r.onerror = e => {
      setError(e.error === 'not-allowed' ? 'Das Mikrofon ist nicht freigegeben. Sie können die Antwort auch tippen.' : 'Die Spracheingabe wurde unterbrochen. Bitte prüfen Sie den Text oder versuchen Sie es erneut.');
      setListening(false); setInterim('');
    };
    r.onend = () => {setListening(false); setInterim(''); recognition.current = null;};
    try { setListening(true); r.start(); } catch {setListening(false); setError('Das Mikrofon konnte nicht starten. Bitte tippen Sie Ihre Antwort.');}
  }
  async function complete() {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError('');
    try {await api('/complete', 'POST'); setScreen('done');}
    catch (e) {setError(e.message);}
    finally {lock.current = false; setBusy(false);}
  }
  function renderPrefill(p) {
    return <div key={p.key} className="onb-prefill-row"><strong>{p.label}</strong>
              {editingPrefill ? <textarea aria-label={p.label} maxLength={20000} value={prefillEdits[p.key] ?? p.customer_value ?? p.value} disabled={busy} onChange={e=>setPrefillEdits({...prefillEdits,[p.key]:e.target.value})}/> : <p>{p.customer_value || p.value}</p>}
              <a href={p.source_url} target="_blank" rel="noopener noreferrer">{p.source_title || 'Öffentliche Quelle'} ↗</a>
              <small> · recherchiert {new Date(p.researched_at).toLocaleDateString('de-DE')}{p.customer_value ? ' · von Ihnen korrigiert' : ''}</small>
            </div>;
  }
  const settled = data ? Object.keys(data.answers).length : 0;
  const answered = data ? Object.values(data.answers).filter(a => a.value).length : 0;
  return <div className="onboarding">
    <header className="onb-header"><div className="onb-logo"><img src="/static/brand/raute-kopf.jpg" alt="raute+kopf" width="2048" height="683" /></div></header>
    <main>
      {!data ? <section className="onb-card"><h1>Ihr Start mit raute+kopf.</h1><p role={error ? 'alert' : 'status'}>{error || 'Ihr Fragebogen wird geladen …'}</p>{token && error && <button onClick={() => window.location.reload()}>Erneut versuchen</button>}</section> : <>
        <div className="onb-context"><span>{data.customer}</span><span>ONBOARDING</span></div>
        {screen === 'welcome' && <section className="onb-card onb-welcome">

          <h1 ref={heading} tabIndex={-1}>Ihre Perspektive.</h1>
          <p>Die öffentlichen Fakten haben wir vorbereitet. Jetzt fehlt nur Ihre Perspektive: Wohin soll es gehen — und was sollen wir wissen?</p>
          <p className="onb-meta">{data.questions.length} Fragen · ca. 5 Minuten</p>
          <button className="onb-primary" onClick={() => data.prefill_confirmed ? resume() : setScreen('prefill')}>{settled ? 'Weiter, wo ich war' : 'Los geht’s'}</button>
          <p className="onb-note">Jede bestätigte Antwort wird gespeichert. Mit diesem Link können Sie jederzeit weitermachen.</p>
        </section>}
        {screen === 'prefill' && <section className="onb-card">

          <h1 ref={heading} tabIndex={-1}>Das wissen wir schon.</h1>
          <p>Aus öffentlichen Quellen für Sie vorbereitet. Ein kurzer Blick genügt — stimmt das so?</p>
          <div className="onb-prefill">
            {(editingPrefill ? data.prefill : data.prefill.slice(0, 3)).map(renderPrefill)}
            {!editingPrefill && data.prefill.length > 3 && <details>
              <summary>{data.prefill.length - 3} weitere recherchierte Angaben ansehen</summary>
              {data.prefill.slice(3).map(renderPrefill)}
            </details>}
          </div>
          <button className="onb-primary" disabled={busy} onClick={confirmPrefill}>{busy ? 'Wird gespeichert …' : editingPrefill ? 'Korrekturen speichern & weiter' : 'Stimmt, weiter'}</button>
          {!editingPrefill && <button className="onb-skip" disabled={busy} onClick={()=>setEditingPrefill(true)}>Eine Angabe korrigieren</button>}
          <p className="onb-note">Was öffentlich nicht belegt ist, recherchiert unser Team weiter. Sie müssen nichts nachtragen.</p>
        </section>}
        {screen === 'question' && <>
          <div className="onb-progress-label"><span>Frage {index + 1} von {data.questions.length}</span><span>{settled} gespeichert</span></div>
          <progress value={settled} max={data.questions.length} aria-label="Gespeicherte Fragen"/>
          <section className="onb-card onb-question" key={question.key}
            onTouchStart={e => {if (e.target.closest('textarea,button,input')) return; touch.current = {x:e.touches[0].clientX,y:e.touches[0].clientY};}}
            onTouchEnd={e => {const start = touch.current; touch.current = null; if (!start || busy || listening) return; const dx = e.changedTouches[0].clientX-start.x, dy = e.changedTouches[0].clientY-start.y; if (Math.abs(dx)>100 && Math.abs(dy)<45) {if(dx<0 && draft.trim()) saveAndMove(); else if(dx>0 && index>0) back();}}}>

            <h1 id="onb-question-title" ref={heading} tabIndex={-1}>{question.text}</h1><p id="onb-help">{question.help}</p>
            {question.choices.length > 0 && <div className="onb-choices" aria-label="Antwortvorschläge">{question.choices.map(c => <button key={c} disabled={busy || listening} aria-pressed={draft.split('; ').includes(c)} onClick={() => setDraft(previous => {if(question.single_choice) return previous === c ? '' : c; const parts=previous ? previous.split('; ') : []; return (parts.includes(c) ? parts.filter(p=>p!==c) : [...parts,c]).join('; ');})}>{c}</button>)}</div>}
            <label className="onb-input-label" htmlFor="onb-answer">Ihre Antwort</label>
            <textarea id="onb-answer" aria-describedby="onb-help" value={draft} maxLength={20000} disabled={busy || listening} onChange={e=>setDraft(e.target.value)} placeholder="Ein paar Worte reichen für den Anfang …"/>
            {interim && <p className="onb-interim" role="status">{interim}</p>}
            <button className={'onb-voice ' + (listening ? 'is-listening' : '')} disabled={!Speech || busy} onClick={dictate} aria-pressed={listening}>
              <svg width="19" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><rect x="8" y="2" width="8" height="13" rx="4"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/></svg>
              {listening ? 'Aufnahme stoppen' : 'Antwort einsprechen'}{listening && <span className="onb-recording"/>}
            </button>
            <p className="onb-note">{Speech ? 'Beim Sprechen kann Ihr Browser Audio an seinen Sprachdienst senden. Wir speichern den Text. Bitte vor dem Weitergehen prüfen.' : 'Spracheingabe ist in diesem Browser nicht verfügbar. Nutzen Sie die Diktierfunktion Ihrer Tastatur oder tippen Sie Ihre Antwort.'}</p>
            <div className="onb-actions"><button disabled={!index || busy || listening} onClick={back} aria-label="Vorherige Frage">←</button><button className="onb-primary" disabled={busy || listening || !draft.trim()} onClick={()=>saveAndMove()}>{busy ? 'Wird gespeichert …' : index === data.questions.length-1 ? 'Antworten ansehen' : 'Speichern & weiter'}</button></div>
            {!data.answers[question.key]?.value && <button className="onb-skip" disabled={busy || listening} onClick={()=>saveAndMove(true)}>Später beantworten</button>}
          </section>

        </>}
        {screen === 'review' && <section className="onb-card"><h1 ref={heading} tabIndex={-1}>So klingt Ihr Unternehmen.</h1><p>{answered} Antworten gespeichert · {data.questions.length-answered} Fragen noch offen.</p>
          <button className="onb-skip" disabled={busy} onClick={()=>setScreen('prefill')}>Vorbereitete Unternehmensangaben ansehen</button>
          <div className="onb-review">{data.questions.map((q,i)=><button disabled={busy} key={q.key} onClick={()=>openQuestion(i)}><strong>{q.text}</strong><span>{data.answers[q.key]?.value || 'Noch offen — später beantworten'}</span><small>Bearbeiten ↗</small></button>)}</div>
          <button className="onb-primary" disabled={busy} onClick={complete}>{busy ? 'Wird abgeschlossen …' : 'Für jetzt abschließen'}</button>
        </section>}
        {screen === 'done' && <section className="onb-card onb-welcome"><span className="onb-eyebrow">DER ANFANG IST GEMACHT</span><h1 ref={heading} tabIndex={-1}>Danke für<br/><em>Ihre Einblicke.</em></h1><p>Ihre {answered} Antworten sind bei Ihrem raute+kopf-Team angekommen. Sie bilden die Grundlage für unsere Zusammenarbeit.</p><p className="onb-note">Sie können diesen Link bis zu seinem Ablauf erneut öffnen und Ihre Antworten ergänzen.</p><button className="onb-primary" onClick={()=>setScreen('review')}>Antworten ansehen</button></section>}
        {error && <p className="onb-error" role="alert">{error}</p>}
      </>}
    </main>
  </div>;
}

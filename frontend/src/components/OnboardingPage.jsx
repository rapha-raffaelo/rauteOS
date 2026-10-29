import React, { useEffect, useRef, useState } from 'react';
import {OnboardingAudio} from './OnboardingAudio.jsx';
import {LANGUAGES, initialLanguage, rememberLanguage, say} from '../onboardingText.js';

export function OnboardingPage({ token = window.location.hash.slice(1).split('/')[0], demoApi = null }) {
  const [data, setData] = useState(null), [error, setError] = useState('');
  const [screen, setScreen] = useState('welcome'), [index, setIndex] = useState(0);
  const [draft, setDraft] = useState(''), [busy, setBusy] = useState(false);
  const [prefillEdits, setPrefillEdits] = useState({}), [editingPrefill, setEditingPrefill] = useState(false);
  const [listening, setListening] = useState(false), [audioDrafts, setAudioDrafts] = useState({});
  const [language, setLanguage] = useState(initialLanguage);
  const tr = text => say(language, text);
  const en = language === 'en';
  const heading = useRef(null), touch = useRef(null), lock = useRef(false);
  const drafts = useRef({}), prefillReturn = useRef(null);
  const question = data?.questions[index];
  const audioState = audioDrafts[question?.key] || {};
  const savedAnswer = data?.answers[question?.key];
  const audioMode = audioState.mode || savedAnswer?.mode || 'transcript';
  const audioRef = Object.hasOwn(audioState, 'uploaded') ? audioState.uploaded : savedAnswer?.audio_id ? {id:savedAnswer.audio_id,mode:savedAnswer.mode} : null;
  const canSave = audioMode === 'audio' ? !!audioRef : !!draft.trim() && (!audioRef?.status || audioRef.status === 'ready');
  const dirty = Object.entries(audioDrafts).some(([key, a]) => (a.blob || a.uploaded) && a.uploaded?.id !== data?.answers[key]?.audio_id) || (screen === 'question' && draft !== (data?.answers[question?.key]?.value || '')) || Object.keys(prefillEdits).length > 0 || Object.entries(drafts.current).some(([key, value]) => value !== (data?.answers[key]?.value || ''));

  async function api(path = '', method = 'GET', body) {
    if (demoApi) return demoApi(path, method, body);
    const response = await fetch('/api/onboarding' + path, {method, credentials: 'omit',
      headers: {'X-Onboarding-Token': token, 'Content-Type': 'application/json'},
      ...(body === undefined ? {} : {body: JSON.stringify(body)})});
    if (!response.ok) {
      const json = await response.json().catch(() => ({}));
      throw new Error(typeof json.detail === 'string' ? json.detail : tr('Speichern nicht möglich. Bitte erneut versuchen. Ihre Eingabe bleibt hier.'));
    }
    return response.json();
  }
  useEffect(() => {
    let active = true;
    if (!token && !demoApi) { setError(tr('Dieser Link ist unvollständig. Bitte öffnen Sie den persönlichen Link von raute+kopf.')); return; }
    api().then(d => { if (active) {setData(d); if (d.completed) setScreen('done');} })
      .catch(e => {if (active) setError(e.message);});
    return () => { active = false; };
  }, [token, demoApi]);
  useEffect(() => { heading.current?.focus(); }, [screen, index]);
  useEffect(() => {
    const warn = e => { if (dirty || busy || listening) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty, busy, listening]);

  function openQuestion(i) {
    setIndex(i); setDraft(drafts.current[data.questions[i].key] ?? data.answers[data.questions[i].key]?.value ?? '');
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
      setPrefillEdits({}); setEditingPrefill(false);
      if (prefillReturn.current !== null) {const target = prefillReturn.current; prefillReturn.current = null; openQuestion(target);} else resume();
    } catch(e) {setError(e.message);}
    finally {lock.current = false; setBusy(false);}
  }
  async function saveAndMove(skip = false, target = index + 1) {
    if (lock.current || listening) return;
    if (!skip && !canSave) {setError(tr('Ein paar Worte genügen. Oder wählen Sie „Später beantworten“.')); return;}
    lock.current = true; setBusy(true); setError('');
    try {
      const answer = await api('/answers/' + question.key, 'PUT', {value: skip || audioMode === 'audio' ? '' : draft, skipped: skip, ...(!skip && audioRef ? {audio_id:audioRef.id,mode:audioMode} : {})});
      const next = {...data, answers: {...data.answers, [question.key]: answer}};
      delete drafts.current[question.key];
      setData(next);
      if (target >= data.questions.length) setScreen('review');
      else {setIndex(target); setDraft(drafts.current[next.questions[target].key] ?? next.answers[next.questions[target].key]?.value ?? '');}
    } catch (e) { setError(e.message); }
    finally { lock.current = false; setBusy(false); }
  }
  function back() {
    if (busy || listening) return;
    drafts.current[question.key] = draft;
    setError('');
    if (index === 0) {prefillReturn.current = 0; setScreen('prefill');}
    else openQuestion(index - 1);
  }
  async function complete() {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError('');
    try {await api('/complete', 'POST'); setScreen('done');}
    catch (e) {setError(e.message);}
    finally {lock.current = false; setBusy(false);}
  }
  function renderPrefill(p) {
    const label = en ? p.label_en || p.label : p.label;
    return <div key={p.key} className="onb-prefill-row"><strong>{label}</strong>
              {editingPrefill ? <textarea aria-label={label} maxLength={20000} value={prefillEdits[p.key] ?? p.customer_value ?? p.value} disabled={busy} onChange={e=>setPrefillEdits({...prefillEdits,[p.key]:e.target.value})}/> : <p>{p.customer_value || p.value}</p>}
            </div>;
  }
  const settled = data ? Object.keys(data.answers).length : 0;
  const answered = data ? Object.values(data.answers).filter(a => a.value || a.audio_id).length : 0;
  return <div className="onboarding">
    <header className="onb-header"><div className="onb-logo"><img src="/static/brand/raute-kopf.jpg" alt="raute+kopf" width="2048" height="683" /></div>
      <div className="onb-language" role="group" aria-label={tr('Sprache')}>{LANGUAGES.map(code => <button key={code} type="button" lang={code} aria-pressed={language === code} onClick={() => {setLanguage(code); rememberLanguage(code);}}>{code.toUpperCase()}</button>)}</div></header>
    <main lang={language}>
      {demoApi && <aside className="onb-demo"><span>{tr('Demo · nur in diesem Tab gespeichert')}</span><button onClick={async () => {await demoApi.reset(); window.location.reload();}}>{tr('Neustart')}</button></aside>}
      {!data ? <section className="onb-card"><h1>{tr('Ihr Start mit raute+kopf.')}</h1><p role={error ? 'alert' : 'status'}>{error || tr('Ihr Fragebogen wird geladen …')}</p>{token && error && <button onClick={() => window.location.reload()}>{tr('Erneut versuchen')}</button>}</section> : <>
        <div className="onb-context"><span>{data.customer}</span><span>ONBOARDING</span></div>
        {screen === 'welcome' && <section className="onb-card onb-welcome">

          <h1 ref={heading} tabIndex={-1}>{tr('Ihre Perspektive.')}</h1>
          <p>{tr('Die Fakten stehen. Jetzt Ihre Perspektive.')}</p>
          <p className="onb-meta">{data.questions.length} {tr('Fragen · jede ist freiwillig · in mehreren Etappen möglich')}</p>
          <button className="onb-primary" onClick={() => data.prefill_confirmed ? resume() : setScreen('prefill')}>{settled ? tr('Weiter, wo ich war') : tr('Los geht’s')}</button>
          <p className="onb-note">{tr('Speichern & später weitermachen — jederzeit.')}</p>
        </section>}
        {screen === 'prefill' && <section className="onb-card">

          <h1 ref={heading} tabIndex={-1}>{tr('Das wissen wir schon.')}</h1>
          <p>{tr('Stimmt das so?')}</p>
          <button className="onb-edit" disabled={busy} onClick={() => {setEditingPrefill(!editingPrefill); setPrefillEdits({});}}>{editingPrefill ? tr('Bearbeitung abbrechen') : tr('Angaben bearbeiten')}</button>
          <div className="onb-prefill">
            {data.prefill.map(renderPrefill)}
          </div>
          <button className="onb-primary" disabled={busy} onClick={confirmPrefill}>{busy ? tr('Wird gespeichert …') : editingPrefill ? tr('Speichern & weiter') : tr('Stimmt, weiter')}</button>
        </section>}
        {screen === 'question' && <>
          <div className="onb-progress-label"><span>{index + 1} / {data.questions.length}</span></div>
          <progress value={settled} max={data.questions.length} aria-label={tr('Gespeicherte Fragen')}/>
          <section className="onb-card onb-question" key={question.key}
            onTouchStart={e => {if (e.target.closest('textarea,button,input')) return; touch.current = {x:e.touches[0].clientX,y:e.touches[0].clientY};}}
            onTouchEnd={e => {const start = touch.current; touch.current = null; if (!start || busy || listening) return; const dx = e.changedTouches[0].clientX-start.x, dy = e.changedTouches[0].clientY-start.y; if (Math.abs(dx)>100 && Math.abs(dy)<45) {if(dx<0 && canSave) saveAndMove(); else if(dx>0) back();}}}>

            <h1 id="onb-question-title" ref={heading} tabIndex={-1}>{en ? question.text_en || question.text : question.text}</h1>
            {question.help && <p className="onb-help">{en ? question.help_en || question.help : question.help}</p>}
            <OnboardingAudio language={language} questionKey={question.key} token={token} demoApi={demoApi} state={audioState} saved={savedAnswer}
              configured={data.transcription_configured} onActivity={setListening}
              onDelete={answer=>setData(previous=>{const answers={...previous.answers};if(answer)answers[question.key]=answer;else delete answers[question.key];return {...previous,answers,completed:false};})}
              onChange={value=>setAudioDrafts(previous=>({...previous,[question.key]:value}))}
              onText={value=>setDraft(previous=>[previous.trim(),value].filter(Boolean).join('\n'))}>
            {audioMode === 'transcript' && question.choices.length > 0 && <div className="onb-choices" aria-label={tr('Antwortvorschläge')}>{question.choices.map(c => <button key={c} disabled={busy || listening} aria-pressed={draft.split('; ').includes(c)} onClick={() => setDraft(previous => {if(question.single_choice) return previous === c ? '' : c; const parts=previous ? previous.split('; ') : []; return (parts.includes(c) ? parts.filter(p=>p!==c) : [...parts,c]).join('; ');})}>{c}</button>)}</div>}
            {audioMode === 'transcript' && <><label className="onb-input-label onb-sr-only" htmlFor="onb-answer">{tr('Ihre Antwort')}</label>
            <textarea id="onb-answer" value={draft} maxLength={20000} disabled={busy || listening} onChange={e=>setDraft(e.target.value)} placeholder={tr('Ihre Antwort …')}/></>}
            </OnboardingAudio>
            <div className="onb-actions"><button disabled={busy || listening} onClick={back} aria-label={tr(index === 0 ? 'Zurück zu den Unternehmensangaben' : 'Vorherige Frage')}>←</button><button className="onb-primary" disabled={busy || listening || !canSave} onClick={()=>saveAndMove()}>{busy ? tr('Wird gespeichert …') : index === data.questions.length-1 ? tr('Antworten ansehen') : tr('Weiter')}</button></div>
            {!data.answers[question.key]?.value && !data.answers[question.key]?.audio_id && <button className="onb-skip" disabled={busy || listening} onClick={()=>saveAndMove(true)}>{tr('Später beantworten')}</button>}
          </section>

        </>}
        {screen === 'review' && <section className="onb-card"><h1 ref={heading} tabIndex={-1}>{tr('So klingt Ihr Unternehmen.')}</h1><p>{answered} {tr('Antworten gespeichert')} · {data.questions.length-answered} {tr('Fragen noch offen.')}</p>
          <button className="onb-skip" disabled={busy} onClick={()=>setScreen('prefill')}>{tr('Unternehmensangaben')}</button>
          <div className="onb-review">{data.questions.map((q,i)=><button disabled={busy} key={q.key} onClick={()=>openQuestion(i)}><strong>{en ? q.text_en || q.text : q.text}</strong><span>{data.answers[q.key]?.mode === 'audio' ? tr('Audio gespeichert') : data.answers[q.key]?.value || tr('Noch offen — später beantworten')}</span><small>{tr('Bearbeiten ↗')}</small></button>)}</div>
          <button className="onb-primary" disabled={busy} onClick={complete}>{busy ? tr('Wird abgeschlossen …') : tr('Abschließen')}</button>
        </section>}
        {screen === 'done' && <section className="onb-card onb-welcome"><span className="onb-eyebrow">{tr('DER ANFANG IST GEMACHT')}</span><h1 ref={heading} tabIndex={-1}>{tr('Danke für')}<br/><em>{tr('Ihre Einblicke.')}</em></h1><p>{demoApi ? `${tr('Demo abgeschlossen.')} ${answered} ${tr('Antworten lokal gespeichert.')}` : `${tr('Ihre')} ${answered} ${tr('Antworten sind gespeichert.')}`}</p><p className="onb-note">{demoApi ? tr('Sie können Ihre Antworten jederzeit bearbeiten.') : tr('Über diesen Link können Sie Ihre Antworten weiter bearbeiten.')}</p><button className="onb-primary" onClick={()=>setScreen('review')}>{tr('Antworten ansehen')}</button></section>}
        {error && <p className="onb-error" role="alert">{error}</p>}
      </>}
    </main>
  </div>;
}

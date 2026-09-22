import React, { useEffect, useState, useRef } from 'react';
import { TwinAIImport } from './TwinAIImport.jsx';
import { twinRequest } from '../twin-api.js';

const labels = {evidence_type: 'Herkunft', source_type: 'Quellentyp', confidence: 'Sicherheit der Aussage',
  confidentiality: 'Vertraulichkeit', external_use: 'Externe Nutzung', fact_status: 'Status', input_owner: 'Verantwortlich'};
const defaults = {evidence_type: 'Client Statement', source_type: 'Other', confidence: 'Unknown',
  confidentiality: 'Client Confidential', external_use: 'Approval Required', fact_status: 'Needs Verification', input_owner: 'RAUTE'};

// Display labels only; imports and API payloads retain the workbook vocabulary.
const readable = value => ({'Client Statement':'Kundenaussage','Fact':'Fakt','Management Belief':'Einschätzung des Managements',
 'Customer Perception':'Kundenwahrnehmung','RAUTE Hypothesis':'Unsere Hypothese','External Observation':'Externe Beobachtung','Derived Insight':'Abgeleitete Erkenntnis',
 'High':'Hoch','Medium':'Mittel','Low':'Niedrig','Unknown':'Unbekannt','Public':'Öffentlich','Client Confidential':'Vertraulich',
 'RAUTE Internal':'Intern bei RAUTE','Highly Restricted':'Streng vertraulich','Allowed':'Extern verwendbar','Approval Required':'Freigabe nötig','Internal Only':'Nur intern',
 'Needs Verification':'Prüfung offen','Outdated':'Veraltet','Contradictory':'Widersprüchlich','Rejected':'Verworfen','Archived':'Archiviert',
 'Other':'Sonstige Quelle','Media':'Medien','External Research':'Externe Recherche','Study':'Studie','Public Database':'Öffentliche Datenbank',
 'Client Interview':'Kundengespräch','Management Interview':'Managementgespräch','Employee Interview':'Mitarbeitergespräch','Customer Interview':'Gespräch mit Endkunden',
 'Sales Data':'Vertriebsdaten','Internal Document':'Internes Dokument','RAUTE Analysis':'RAUTE-Analyse','AI Research':'KI-Recherche','OS / Research':'OS / Recherche'}[value] || value);

export function TwinPage({clientId, embedded = false, initialLimit = 20}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState('');
  const [section, setSection] = useState('');
  const [filter, setFilter] = useState('all');
  const [limit, setLimit] = useState(initialLimit);
  const [editing, setEditing] = useState(null);
  const importPanel = useRef(null), filePanel = useRef(null), chosenImport = useRef(null);
  const [aiImporting, setAIImporting] = useState(false);
  const [aiStatus, setAIStatus] = useState(null);
  const [importing, setImporting] = useState(false);
  useEffect(() => {if (aiImporting) importPanel.current?.scrollIntoView?.({behavior: 'smooth', block: 'start'});}, [aiImporting]);
  useEffect(()=>{if(importing)filePanel.current?.scrollIntoView?.({behavior:'smooth',block:'start'});},[importing]);
  const load = async () => setData(await twinRequest(clientId));
  useEffect(() => {
    const controller = new AbortController();
    twinRequest(clientId, '', {signal: controller.signal}).then(setData).catch(err => {
      if (!controller.signal.aborted) setError(err.message);
    });
    return () => controller.abort();
  }, [clientId]);
  async function mutate(path, payload, method = 'POST') {
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await twinRequest(clientId, path, {method, body: JSON.stringify(payload)});
      setEditing(null);
      await load();
      setNotice('Gespeichert.');
      return result;
    } catch (err) { setError(err.message); return null; }
    finally {setBusy(false);}
  }
  const refresh = async () => {try {await load(); setError('');} catch (err) {setError(err.message);}};
  const errors = error && <div role="alert" className="twin-error"><p>{error}</p>
    <button className="btn" onClick={refresh}>Neu laden</button> <a href={`/login?next=/client/${clientId}/twin`}>Anmelden</a></div>;
  if (!data) return <div className="twin-page">{errors || <p role="status">Profil wird geladen…</p>}</div>;
  const statements = (key) => data.statements.filter(row => row.key === key);
  const active = (row) => !['Rejected', 'Archived'].includes(row.fact_status);
  const visible = data.fields.filter(field => {
    const rows = statements(field.key);
    return (!section || field.section === section) &&
      (!query || `${field.key} ${field.label} ${rows.map(r => r.value).join(' ')}`.toLowerCase().includes(query.toLowerCase())) &&
      (filter === 'all' || filter === 'required' && field.requirement === 'Pflicht' ||
       filter === 'missing' && data.progress.missing.includes(field.key) ||
       filter === 'answered' && rows.some(active) || filter === 'review' && rows.some(r => active(r) && !r.verified_at));
  });
  return <div className="twin-page">
    <header>{embedded ? <h2>Wissen & Aussagen</h2> : <><p className="twin-eyebrow">PROFIL · {data.client.name}</p><h1>Was wir wissen. Und woher.</h1></>}
      <p>Jede Aussage mit ihrer Quelle, ihrem Stand und ihrer Freigabe.</p>
      <div className="twin-toolbar"><button className="btn btn--go" type="button" aria-controls={`twin-ai-${clientId}`} aria-expanded={aiImporting} onClick={()=>{chosenImport.current='ai';setAIImporting(!aiImporting);setImporting(false);}}>Mit KI importieren</button>{aiStatus&&<span role="status">{aiStatus.preview?`${aiStatus.preview.rows.length} KI-Vorschläge gespeichert`:aiStatus.job?.note}</span>}<button className="btn btn--quiet" aria-expanded={importing} aria-controls={`twin-file-${clientId}`} onClick={() => {chosenImport.current='file';setImporting(!importing);setAIImporting(false);}}>Fragebogen importieren</button></div>
    </header>
    <div hidden={!importing} ref={filePanel} id={`twin-file-${clientId}`}><ImportPanel clientId={clientId} onImported={async result=>{await load();setNotice(`${result.created} Aussagen importiert; ${result.skipped} bereits vorhanden.`);}}/></div>
    {<div hidden={!aiImporting} ref={importPanel} id={`twin-ai-${clientId}`}><TwinAIImport clientId={clientId} fields={data.fields} onStatus={setAIStatus} onRestore={v=>{if(chosenImport.current!=='file'&&(v.preview||v.job?.status==='running'||v.job?.status==='failed'))setAIImporting(true);}} onImported={async result=>{await load();setNotice(`${result.created} KI-Vorschläge übernommen; ${result.skipped} bereits beantwortet oder vorhanden.`);}}/></div>}
    <section className="twin-progress" aria-label="Vollständigkeit">
      <div className="twin-progress-main"><span className="twin-progress-label">Profilvollständigkeit</span><strong>{data.progress.percent} % vollständig</strong>
        <progress max="100" value={data.progress.percent} aria-label="Beantwortete Pflichtfelder" /></div>
      <dl className="twin-progress-facts"><div><dt>Pflichtfelder beantwortet</dt><dd>{data.progress.required_filled}<span> / {data.progress.required_total}</span></dd></div>
        <div><dt>Unabhängig bestätigt</dt><dd>{data.progress.verified}<span> {data.progress.verified===1?'Aussage':'Aussagen'}</span></dd></div></dl>
      <small>Vollständigkeit misst beantwortete Pflichtfelder. Sie ist keine Bestätigung ihrer Richtigkeit.</small>
    </section>
    {errors}{notice && <p role="status">{notice}</p>}

    <fieldset disabled={Boolean(editing)} className="twin-toolbar twin-filters">
      <label>Suche<input type="search" value={query} onChange={e => {setQuery(e.target.value); setLimit(initialLimit);}} placeholder="Feld oder Aussage suchen" /></label>
      <label>Bereich<select aria-label="Bereich" value={section} onChange={e => {setSection(e.target.value); setLimit(initialLimit);}}>
        <option value="">Alle Bereiche</option>{[...new Set(data.fields.map(f => f.section))].map(s => <option key={s}>{s}</option>)}</select></label>
      <label>Anzeige<select aria-label="Anzeige" value={filter} onChange={e => {setFilter(e.target.value); setLimit(initialLimit);}}>
        <option value="all">Alle Felder</option><option value="required">Pflichtfelder</option><option value="missing">Fehlende Pflichtfelder</option>
        <option value="answered">Mit Aussagen</option><option value="review">Bestätigung offen</option></select></label>
    </fieldset>
    <p className="twin-muted">{visible.length} Felder · mehrere Aussagen je Feld möglich</p>
    {visible.slice(0, limit).map(field => <section className={`twin-field twin-question ${statements(field.key).length?'twin-question--answered':'twin-question--empty'}`} key={field.key}>
      <div className="twin-field-head"><div><small className="twin-question-meta"><span>{field.key}</span> {field.group} · {field.requirement}</small><h2>{field.label}</h2></div>
        <button className="btn" disabled={busy || Boolean(editing)} onClick={() => setEditing({field})}>Aussage ergänzen</button></div>
      {editing?.field.key === field.key && <StatementEditor key={editing.row?.id ?? field.key} field={field} row={editing.row}
        options={data.options} busy={busy} onCancel={() => setEditing(null)} onSave={payload => mutate(
          editing.row ? `/statements/${editing.row.id}` : '/statements',
          {...payload, ...(editing.row ? {revision: editing.row.revision} : {})}, editing.row ? 'PUT' : 'POST')} />}
      {!statements(field.key).length && !editing && <p className="twin-muted">Noch offen</p>}
      {statements(field.key).map(row => <Statement key={row.id} row={row} clientId={clientId} busy={busy || Boolean(editing)}
        onEdit={() => setEditing({field, row})} onAction={(action, note = '') => mutate(`/statements/${row.id}/${action}`, {revision: row.revision, note})} />)}
    </section>)}
    {!visible.length && <p>Keine passenden Felder.</p>}
    {limit < visible.length && <button className="btn" onClick={() => setLimit(limit + 20)}>Weitere Felder anzeigen</button>}
  </div>;
}

function Statement({row, clientId, busy, onEdit, onAction}) {
  const [confirming, setConfirming] = useState(false);
  const [note, setNote] = useState('');
  const [history, setHistory] = useState(null);
  const [historyError, setHistoryError] = useState('');
  useEffect(() => {setHistory(null);}, [row.revision]);
  const inactive = ['Rejected', 'Archived'].includes(row.fact_status);
  const canConfirm = !row.verified_at && ['Media','External Research','Study','Public Database'].includes(row.source_type) && Boolean(row.source_url || row.source_title);
  return <article className={`twin-statement ${inactive ? 'twin-inactive' : ''}`}>
    <div className="twin-badges"><span>{readable(row.evidence_type) || 'Herkunft unbekannt'}</span><span>{readable(row.fact_status) || 'Prüfung offen'}</span>
      <span>{row.verified_at && !inactive ? 'Unabhängig bestätigt' : 'Nicht unabhängig bestätigt'}</span></div>
    <p className="twin-value">{row.value}</p>
    <dl className="twin-metadata">
      <div><dt>Quelle</dt><dd>{/^https?:\/\//i.test(row.source_url) ? <a href={row.source_url} target="_blank" rel="noreferrer">{row.source_title || row.source_url}</a> : row.source_title || 'Nicht hinterlegt'}</dd></div>
      <div><dt>Stand</dt><dd>{row.as_of?.slice(0, 10) || 'Unbekannt'}</dd></div>
      <div><dt>Sicherheit der Aussage</dt><dd>{readable(row.confidence) || 'Unbekannt'}</dd></div>
      <div><dt>Vertraulichkeit</dt><dd>{readable(row.confidentiality) || 'Unbekannt'}</dd></div>
      <div><dt>Externe Nutzung</dt><dd>{readable(row.external_use) || 'Freigabe erforderlich'}</dd></div>
    </dl>
    {row.note && <p>{row.note}</p>}{row.verified_at && <p className="twin-muted">Geprüft von {row.verified_by}: {row.verification_note}</p>}
    <div className="twin-toolbar"><button className="btn" disabled={busy} onClick={onEdit}>Bearbeiten</button>
      <details className="quiet-actions"><summary>Weitere Aktionen</summary><div className="quiet-actions-body">{!inactive && <>{canConfirm&&<button className="btn" disabled={busy} onClick={() => setConfirming(!confirming)}>Bestätigen</button>}
        <button className="btn" disabled={busy} onClick={() => onAction('reject')}>Verwerfen</button>
        <button className="btn" disabled={busy} onClick={() => onAction('archive')}>Archivieren</button></>}
      <button className="btn" onClick={async () => {
        if (history) {setHistory(null); return;}
        try {setHistory(await twinRequest(clientId, `/statements/${row.id}/history`)); setHistoryError('');}
        catch (err) {setHistoryError(err.message);}
      }}>Historie</button></div></details></div>
    {confirming && <form className="twin-confirm" onSubmit={async e => {e.preventDefault(); if (await onAction('confirm', note)) setConfirming(false);}}>
      <p>Als unabhängig belegten Fakt bestätigen. Eine Quelle vom Typ Media, External Research, Study oder Public Database muss hinterlegt sein. Die externe Freigabe bleibt separat.</p>
      <label>Prüfvermerk<textarea aria-label="Prüfvermerk" required value={note} maxLength={5000} onChange={e => setNote(e.target.value)} /></label>
      <button className="btn" disabled={busy}>Unabhängige Bestätigung speichern</button>
    </form>}
    {historyError && <p role="alert">{historyError}</p>}
    {history && <div className="twin-history"><h3>Frühere Fassungen</h3>{history.length ? history.map((item, i) => <div key={i}>
      <small>{item.changed_at} · {item.changed_by}</small><p>{item.snapshot.value}</p>
      <p>{item.snapshot.evidence_type || 'Unbekannt'} · {item.snapshot.fact_status || 'Needs Verification'} · {item.snapshot.source_title || item.snapshot.source_url || 'Ohne Quelle'}</p>
    </div>) : <p>Noch keine Änderungen.</p>}</div>}
  </article>;
}

function StatementEditor({field, row, options, busy, onCancel, onSave}) {
  const [values, setValues] = useState(() => ({key: field.key, value: row?.value || '', source_title: row?.source_title || '',
    source_url: row?.source_url || '', as_of: row?.as_of?.slice(0, 10) || '', note: row?.note || '',
    verification_note: row?.verification_note || '', ...Object.fromEntries(Object.keys(labels).map(key => [key, row?.[key] || (key === 'input_owner' ? field.input_owner : key === 'evidence_type' && field.key.startsWith('C') ? 'RAUTE Hypothesis' : key === 'evidence_type' && field.key.startsWith('D') ? 'External Observation' : defaults[key])]))}));
  const input = (key) => ({'aria-label': labels[key] || ({value:'Aussage',source_title:'Quelle / Dokument',source_url:'Quellen-URL',as_of:'Stand der Aussage',note:'Notizen'})[key], value: values[key], onChange: e => setValues({...values, [key]: e.target.value})});
  return <form className="twin-editor" aria-label="Aussage bearbeiten" onSubmit={e => {e.preventDefault(); onSave({...values, as_of: values.as_of || null});}}>
    <h3>{row ? 'Aussage bearbeiten' : 'Antwort ergänzen'}</h3>
    {row?.verified_at && <p>Ändern hebt die bisherige Bestätigung auf. Danach die Aussage erneut prüfen.</p>}
    <label>Aussage<textarea autoFocus required maxLength={20000} {...input('value')} /></label>
    <div className="twin-form-grid">
      <label>Quelle / Dokument<input maxLength={2000} {...input('source_title')} /></label>
      <label>Quellen-URL<input type="url" maxLength={2000} {...input('source_url')} /></label>
    </div>
    <p className="editor-permissions">{readable(values.evidence_type)} · {readable(values.confidentiality)} · {readable(values.external_use)}</p>
    <details className="editor-details"><summary>Herkunft, Freigabe & weitere Angaben</summary>
    <div className="twin-form-grid">
      <label>Stand der Aussage<input type="date" {...input('as_of')} /></label>
      {Object.entries(labels).map(([key, label]) => <label key={key}>{label}<select {...input(key)}>
        {options[key].map(value => <option key={value} value={value}>{readable(value)}</option>)}</select></label>)}
    </div>
    <label>Notizen<textarea maxLength={5000} {...input('note')} /></label>
    </details>
    <div className="twin-toolbar editor-actions"><button className="btn btn--go" disabled={busy}>{busy ? 'Speichert…' : 'Aussage speichern'}</button>
      <button className="btn" type="button" disabled={busy} onClick={onCancel}>Abbrechen</button></div>
  </form>;
}

export function ImportPanel({clientId, onImported}) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [mapping, setMapping] = useState({});
  const [selected, setSelected] = useState([]);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function review() {
    if (!file) return;
    setBusy(true); setError('');
    try {
      const form = new FormData(); form.append('file', file); form.append('mapping', JSON.stringify(mapping));
      const result = await twinRequest(clientId, '/import/preview', {method: 'POST', body: form});
      setPreview(result); setMapping(result.mapping); setSelected(result.rows.filter(r => r.state === 'ready').map(r => r.index)); setDirty(false);
    } catch (err) {setError(err.message); setDirty(true);}
    finally {setBusy(false);}
  }
  return <section className="twin-import"><h2>Fragebogen importieren</h2>
    <p>Vorlage herunterladen, Antworten ausfüllen und die gespeicherte Datei hier wieder hochladen.</p>
    <div className="twin-toolbar"><a className="btn" href={`/api/v1/clients/${clientId}/twin/questionnaire/xlsx`} download>Excel-Vorlage herunterladen</a><a className="btn btn--quiet" href={`/api/v1/clients/${clientId}/twin/questionnaire/pdf`} download>Ausfüllbares PDF herunterladen</a></div>
    <p className="twin-muted">Excel, CSV oder unsere digital ausgefüllte PDF-Vorlage, bis 5 MB. PDF mit Formulardaten speichern; Scans können nicht eingelesen werden. Vor der Übernahme prüfst du die Vorschau. Vorhandene Aussagen bleiben erhalten.</p>
    <label>Datei<input type="file" accept=".xlsx,.csv,.pdf" onChange={e => {setFile(e.target.files[0]); setPreview(null); setMapping({}); setDirty(true);}} /></label>
    <button className="btn" disabled={!file || busy} onClick={review}>{busy ? 'Prüft…' : 'Vorschau erstellen'}</button>
    {error && <p role="alert">{error}</p>}
    {preview && <>
      <details><summary>Spalten zuordnen</summary><div className="twin-form-grid">
        {Object.entries(preview.mapping).map(([key]) => <label key={key}>{({key:'Feld-ID', value:'Antwort', source_title:'Quelle / Dokument', source_url:'Quellen-URL', as_of:'Datum', note:'Notizen', ...labels})[key] || key}
          <select value={mapping[key] || ''} onChange={e => {setMapping({...mapping, [key]: e.target.value}); setDirty(true);}}>
            <option value="">Nicht zugeordnet</option>{preview.columns.map(column => <option key={column}>{column}</option>)}</select></label>)}
      </div><button className="btn" onClick={review} disabled={busy}>Zuordnung prüfen</button></details>
      <p>{selected.length} ausgewählt · {preview.rows.filter(r => r.state === 'error').length} Fehler · {preview.rows.filter(r => r.state === 'empty').length} unbeantwortet · {preview.rows.filter(r => r.state === 'duplicate').length} doppelt</p>
      <div className="twin-import-rows">{preview.rows.filter(row => row.state !== 'empty').map(row => <article key={row.index}>
        <label>{row.state === 'ready' && <input type="checkbox" checked={selected.includes(row.index)} onChange={e => setSelected(e.target.checked ? [...selected, row.index] : selected.filter(i => i !== row.index))} />}
          {row.sheet}, Zeile {row.line} · {row.data?.key || 'Nicht zugeordnet'}</label>
        <p className="twin-value">{row.data?.value}</p><p>{row.message}</p>
        {row.data && <details><summary>Herkunft und Metadaten prüfen</summary><dl className="twin-metadata">{Object.entries(row.data).filter(([key]) => !['key','value'].includes(key)).map(([key,value]) =>
          <div key={key}><dt>{labels[key] || key}</dt><dd>{value || 'Nicht hinterlegt'}</dd></div>)}</dl></details>}
      </article>)}</div>
      {dirty && <p>Zuordnung geändert. Vorschau vor dem Import erneut prüfen.</p>}
      <button className="btn" disabled={busy || dirty || !selected.length} onClick={async () => {
        setBusy(true); setError('');
        try {
          const result = await twinRequest(clientId, '/import/commit', {method:'POST', body:JSON.stringify({preview_id:preview.id, selected})});
          setPreview(null); setSelected([]); await onImported(result);
        } catch (err) {setError(err.message);}
        finally {setBusy(false);}
      }}>Ausgewählte Aussagen importieren</button>
    </>}
  </section>;
}

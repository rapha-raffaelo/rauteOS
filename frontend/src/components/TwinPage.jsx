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

// The company facts the glance row shows when research has them.
const GLANCE = [['A01.03', 'Gegründet', 'calendar'], ['A01.04', 'Hauptsitz', 'pin'], ['A01.07', 'Mitarbeitende', 'people'],
  ['A01.06', 'Märkte', 'globe'], ['A01.09', 'Eigentümer', 'building']];
const ICONS = {
  calendar: 'M7 3v3M17 3v3M4 9h16M5 6h14a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1z',
  pin: 'M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21zM12 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z',
  people: 'M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 6.5M18.5 14.5A6.5 6.5 0 0 1 21.5 20',
  globe: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z',
  building: 'M4 21V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v16M15 9h4a1 1 0 0 1 1 1v11M3 21h18M8 8h3M8 12h3M8 16h3',
};
const Icon = ({name}) => <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={ICONS[name]}/></svg>;

export function TwinPage({clientId, embedded = false}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null);
  const [hints, setHints] = useState([]);
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
  // The profile is the onboarding questionnaire, numbered as the customer sees
  // it: 21 researched topics, then 22 questions. The wider catalogue (A to D)
  // is not shown: research still fills it for the prompts and the glance row.
  const brief = data.fields.filter(f => f.key.startsWith('R'));
  const asked = data.fields.filter(f => f.key.startsWith('Q'));
  const has = field => statements(field.key).some(active);
  const number = key => key.slice(1).split('.')[key.startsWith('Q') ? 1 : 0];
  const editor = item => editing?.field.key === item.key && <StatementEditor key={editing.row?.id ?? item.key} field={item} row={editing.row}
      options={data.options} busy={busy} onCancel={() => setEditing(null)} onSave={payload => mutate(
        editing.row ? `/statements/${editing.row.id}` : '/statements',
        {...payload, ...(editing.row ? {revision: editing.row.revision} : {})}, editing.row ? 'PUT' : 'POST')} />;
  const answers = item => statements(item.key).map(row => <Statement key={row.id} row={row} busy={busy || Boolean(editing)}
      onEdit={() => setEditing({field: item, row})} />);
  const add = (item, label = 'Antwort ergänzen') => <button className="btn btn--quiet" disabled={busy || Boolean(editing)} onClick={() => setEditing({field: item})}>{label}</button>;
  // A topic of the brief as a card: number, title, the short text, its source.
  // The guiding question is the title's tooltip, not a paragraph on every card.
  const topic = item => <article className={`twin-topic${has(item) ? '' : ' twin-topic--empty'}${editing?.field.key === item.key ? ' twin-topic--editing' : ''}`} key={item.key} id={`feld-${item.key}`}>
    <header><span className="twin-number">{number(item.key)}</span><h3 title={item.hint || undefined}>{item.label}</h3>
      {!has(item) && add(item, 'Ergänzen')}</header>
    {editor(item)}{answers(item)}
    {!has(item) && editing?.field.key !== item.key && <p className="twin-empty">Noch keine belegte Angabe.</p>}
  </article>;
  // A customer question as one row; its guiding text opens on demand.
  const question = item => <li className={`twin-ask${has(item) ? ' twin-ask--done' : ''}`} key={item.key} id={`feld-${item.key}`}>
    <div className="twin-ask-row"><span className="twin-number">{number(item.key)}</span>
      <div className="twin-ask-text"><h3>{item.label}</h3>
        {item.hint && <button type="button" className="linkbtn twin-more" aria-expanded={hints.includes(item.key)} onClick={() => setHints(hints.includes(item.key) ? hints.filter(k => k !== item.key) : [...hints, item.key])}>{hints.includes(item.key) ? 'Leitfragen ausblenden' : 'Leitfragen'}</button>}
        {hints.includes(item.key) && <p className="twin-hint">{item.hint}</p>}</div>
      <span className={`twin-state${has(item) ? ' twin-state--ok' : ''}`}>{has(item) ? 'Beantwortet' : 'Offen'}</span>
      {!has(item) && add(item, 'Ergänzen')}</div>
    {editor(item)}{answers(item)}
  </li>;
  // Short facts for the glance row; each is a one-sentence research answer.
  const glance = GLANCE.map(([key, label, icon]) => [label, icon, statements(key).find(active)?.value]).filter(([, , value]) => value);
  const part = (label, done, total, note) => <div className="twin-part"><div><span>{label}</span><strong>{done}<small> / {total} {note}</small></strong></div>
    <div className="twin-bar"><span style={{width: `${total ? Math.round(100 * done / total) : 0}%`}}/></div></div>;
  return <div className="twin-page">
    <header>{embedded ? <h2>Wissen & Aussagen</h2> : <><p className="twin-eyebrow">PROFIL · {data.client.name}</p><h1>Was wir wissen. Und woher.</h1></>}
      <p>Jede Aussage mit ihrer Quelle, ihrem Stand und ihrer Freigabe.</p>
      <div className="twin-toolbar"><button className="btn btn--go" type="button" aria-controls={`twin-ai-${clientId}`} aria-expanded={aiImporting} onClick={()=>{chosenImport.current='ai';setAIImporting(!aiImporting);setImporting(false);}}>Mit KI importieren</button>{aiStatus&&<span role="status">{aiStatus.preview?`${aiStatus.preview.rows.length} KI-Vorschläge gespeichert`:aiStatus.job?.note}</span>}<button className="btn btn--quiet" aria-expanded={importing} aria-controls={`twin-file-${clientId}`} onClick={() => {chosenImport.current='file';setImporting(!importing);setAIImporting(false);}}>Fragebogen importieren</button></div>
    </header>
    <div hidden={!importing} ref={filePanel} id={`twin-file-${clientId}`}><ImportPanel clientId={clientId} onImported={async result=>{await load();setNotice(`${result.created} Aussagen importiert; ${result.skipped} bereits vorhanden.`);}}/></div>
    {<div hidden={!aiImporting} ref={importPanel} id={`twin-ai-${clientId}`}><TwinAIImport clientId={clientId} fields={data.fields} onStatus={setAIStatus} onRestore={v=>{if(chosenImport.current!=='file'&&(v.preview||v.job?.status==='running'||v.job?.status==='failed'))setAIImporting(true);}} onImported={async result=>{await load();setNotice(`${result.created} KI-Vorschläge übernommen; ${result.skipped} bereits beantwortet oder vorhanden.`);}}/></div>}
    <section className="twin-overview" aria-label="Vollständigkeit">
      <div className="twin-ring" style={{'--p': data.progress.percent}} role="progressbar" aria-label="Profilvollständigkeit"
        aria-valuenow={data.progress.percent} aria-valuemin={0} aria-valuemax={100}><strong>{data.progress.percent} %</strong><span>vollständig</span></div>
      <div className="twin-parts">
        {part('Unternehmenssteckbrief', brief.filter(has).length, brief.length, 'recherchiert')}
        {part('Kundenfragebogen', asked.filter(has).length, asked.length, 'beantwortet')}
        <p className="twin-muted">{data.progress.verified} {data.progress.verified === 1 ? 'Aussage' : 'Aussagen'} unabhängig bestätigt. Vollständigkeit misst die 21 Recherche-Themen und 22 Kundenfragen, nicht ihre Richtigkeit.</p>
      </div>
    </section>
    {errors}{notice && <p role="status">{notice}</p>}

    {glance.length > 0 && <section className="twin-glance" aria-label="Auf einen Blick">
      {glance.map(([label, icon, value]) => <div key={label}><span className="twin-glance-icon"><Icon name={icon}/></span><div><small>{label}</small><p title={value}>{value}</p></div></div>)}
    </section>}

    <section className="twin-brief" aria-labelledby={`twin-brief-${clientId}`}>
      <header className="twin-section-head"><div><p className="twin-eyebrow">AUS DER RECHERCHE</p><h2 id={`twin-brief-${clientId}`}>Unternehmenssteckbrief</h2></div>
        <p className="twin-muted">{brief.filter(has).length} von {brief.length} Themen recherchiert · Prüfung offen, bis jemand bestätigt</p></header>
      <div className="twin-topics">{brief.map(topic)}</div>
    </section>

    <section className="twin-questionnaire" aria-labelledby={`twin-asked-${clientId}`}>
      <header className="twin-section-head"><div><p className="twin-eyebrow">VOM KUNDEN · ÜBER DEN ONBOARDING-LINK</p><h2 id={`twin-asked-${clientId}`}>Kundenfragebogen</h2></div>
        <p className="twin-muted">{asked.filter(has).length} von {asked.length} Fragen beantwortet</p></header>
      <ol className="twin-asks">{asked.map(question)}</ol>
    </section>

  </div>;
}

/** A source as its site's name, the way a reader recognises it. */
export function SourceLink({url, title}) {
  let host = '';
  try {host = new URL(url).hostname.replace(/^www\./, '');} catch {return title || 'Nicht hinterlegt';}
  return <a className="twin-source" href={url} target="_blank" rel="noreferrer" title={title ? `${title} · ${url}` : url}>{host}</a>;
}

// One statement as it reads in the brief: the answer, clipped to three lines
// until asked for more, one line saying where it comes from and how far it is
// checked, and the one action used daily. Origin, confidentiality and release
// are set in the editor, not shown as a table under every answer.
function Statement({row, busy, onEdit}) {
  const [open, setOpen] = useState(false);
  const inactive = ['Rejected', 'Archived'].includes(row.fact_status);
  const more = [...new Set((row.note || '').match(/https?:\/\/[^\s,]+/g) || [])]
    .filter(url => host(url) && host(url) !== host(row.source_url));
  const long = (row.value || '').length > 280;
  return <article className={`twin-statement ${inactive ? 'twin-inactive' : ''}`}>
    <p className={`twin-value ${long && !open ? 'twin-value--clipped' : ''}`}>{row.value}</p>
    {long && <button type="button" className="linkbtn twin-more" onClick={() => setOpen(!open)}>{open ? 'Weniger anzeigen' : 'Mehr anzeigen'}</button>}
    <div className="twin-statement-foot">
      <span className="twin-provenance">
        {/^https?:\/\//i.test(row.source_url) ? <SourceLink url={row.source_url} title={row.source_title} /> : <span>{row.source_title || 'Ohne Quelle'}</span>}
        {more.length > 0 && <span className="twin-more-sources" title={more.join('\n')}>+{more.length} {more.length === 1 ? 'Quelle' : 'Quellen'}</span>}
        <span className={`twin-state ${row.verified_at && !inactive ? 'twin-state--ok' : ''}`}>{inactive ? readable(row.fact_status) : row.verified_at ? 'Bestätigt' : 'Prüfung offen'}</span>
      </span>
      <button className="btn btn--quiet" disabled={busy} onClick={onEdit}>Bearbeiten</button>
    </div>
  </article>;
}

const host = url => {try {return new URL(url).hostname.replace(/^www\./, '');} catch {return '';}};

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

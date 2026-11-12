import React, {useEffect, useState} from 'react';
const money = (n,currency) => new Intl.NumberFormat('de-DE',{style:'currency',currency}).format(Number(n));
const date = iso => new Date(iso).toLocaleString('de-DE',{timeZone:'Europe/Zurich'});
export default function GeminiSpending({initial}) {
  const [data,setData]=useState(initial || {state:'not_configured'});
  const [editing,setEditing]=useState(false), [busy,setBusy]=useState(false), [error,setError]=useState('');
  async function refresh() {
    setBusy(true);setError('');
    try {
      const response=await fetch('/settings/ai/gemini/spending',{signal:AbortSignal.timeout(45000)});
      if(!response.ok) throw new Error('Kosten konnten nicht geladen werden');
      setData(await response.json());
    } catch(e) {setError(e.message || 'Kosten konnten nicht geladen werden');}
    finally {setBusy(false);}
  }
  useEffect(()=>{
    if(!data.config?.table) return;
    refresh();
    const timer=setInterval(()=>{if(!document.hidden) refresh();},900000);
    return ()=>clearInterval(timer);
  },[data.config?.table]);
  async function save(e) {
    e.preventDefault();setBusy(true);setError('');
    try {
      const response=await fetch('/settings/ai/gemini/spending/config',{method:'POST',body:new URLSearchParams(new FormData(e.currentTarget))});
      const result=await response.json();
      if(!response.ok) throw new Error(result.message || 'Konfiguration konnte nicht gespeichert werden');
      setData(result);setEditing(false);
      await refresh();
    } catch(e) {setError(e.message);}
    finally {setBusy(false);}
  }
  const config=data.config || {};
  return <section className="gemini-cash" aria-label="Gemini-Kosten">
    <div className="ai-usage__row"><div><p className="ai-usage__title">Gemini-Ausgaben · {data.month || 'aktueller Monat'}</p>
      <strong className="gemini-cash__amount">{data.net != null ? money(data.net,data.currency) : data.state==='not_configured' ? 'Billing-Export verbinden' : data.state==='no_data' ? 'Noch keine Kostendaten im Export' : busy ? 'Kosten werden geladen…' : 'Kostendaten nicht verfügbar'}</strong>
    </div><button className="btn" type="button" disabled={busy} onClick={()=>setEditing(!editing)}>{editing?'Schließen':config.table?'Datenquelle bearbeiten':'BigQuery verbinden'}</button></div>
    {data.net != null && <dl className="ai-usage__counts"><div><dt>Kosten vor Gutschriften</dt><dd>{money(data.gross,data.currency)}</dd></div><div><dt>Gutschriften / Rabatte</dt><dd>{money(data.credits,data.currency)}</dd></div></dl>}
    <p className="settings-caption">Ausgaben nach exportierten Gutschriften, kein verbleibendes Guthaben. Google meldet Kosten zeitverzögert; Nachbuchungen können den Betrag ändern.</p>
    {config.project && <p className="settings-caption">Gesamtes Projekt: {config.project} · Services: {config.services.join(', ')} · Nutzungsmonat nach Europe/Zurich</p>}
    {data.checked_at && <p className="settings-caption">Abgerufen: {date(data.checked_at)}{data.exported_at ? ` · Neuester enthaltener Export: ${date(data.exported_at)}` : ''}</p>}
    {data.state==='no_data' && <p className="settings-caption">Keine passenden Buchungen gefunden. Das ist keine Bestätigung für 0 Kosten. Export und Service-Filter prüfen.</p>}
    {(error || data.error) && <p role="alert">{error || data.error}{data.net != null ? ' Angezeigt wird der letzte erfolgreiche Abruf.' : ''}</p>}
    {config.table && <button className="btn" type="button" disabled={busy} onClick={refresh}>{busy?'Wird geladen…':'Kosten aktualisieren'}</button>}
    {config.table && <p className="settings-caption">Abruf höchstens alle 15 Minuten, solange diese Ansicht geöffnet ist</p>}
    {editing && <form className="gemini-spending__form" onSubmit={save}>
      <p>Google Cloud Billing → Billing-Export → Standardkosten nach BigQuery aktivieren. Der Server benötigt BigQuery-Lesezugriff auf das Dataset und Berechtigung zum Ausführen von Abfragen.</p>
      <label className="platform-field"><span>Export-Tabelle</span><input name="table" defaultValue={config.table || ''} required placeholder="projekt.dataset.tabelle"/></label>
      <label className="platform-field"><span>Gemini-Projekt-ID</span><input name="project" defaultValue={config.project || ''} required/></label>
      <label className="platform-field"><span>Gemini-Service-IDs</span><input name="services" defaultValue={config.services?.join(', ') || ''} required/><small>service.id aus dem Export; mehrere mit Komma trennen</small></label>
      <label className="platform-field"><span>BigQuery-Region</span><input name="location" defaultValue={config.location || 'EU'} required/></label>
      <p>Zugangsdaten werden sicher auf dem Server eingerichtet und hier nicht eingegeben. <a href="https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery-setup" target="_blank" rel="noreferrer">Google-Anleitung ↗</a></p>
      <button className="btn" disabled={busy}>Datenquelle speichern</button>
    </form>}
  </section>;
}

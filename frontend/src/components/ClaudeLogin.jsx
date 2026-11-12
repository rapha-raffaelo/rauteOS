import React, {useEffect, useRef, useState} from 'react';
import './ClaudeLogin.css';
const base = '/settings/ai/claude';
async function request(path, body) {
  const response = await fetch(base + path, {method: body === undefined ? 'GET' : 'POST',
    headers: {Accept: 'application/json'}, body: body === undefined ? undefined : new URLSearchParams(body), signal: AbortSignal.timeout(15000)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || data.detail || 'Anmeldung konnte nicht geladen werden');
  return data;
}
export default function ClaudeLogin() {
  const dialog = useRef(null), popup = useRef(null), opened = useRef(null);
  const [required, setRequired] = useState(false), [session, setSession] = useState(null);
  const [error, setError] = useState(''), [code, setCode] = useState(''), [busy, setBusy] = useState(false);
  const active = session && ['starting','waiting','checking'].includes(session.state);
  function show() { if (!dialog.current?.open) dialog.current?.showModal(); }
  useEffect(() => {
    let disposed = false;
    async function check() {
      if (document.hidden) return;
      try {
        const data = await request('/status');
        if (disposed || data.state === 'unknown') return;
        setRequired(data.state === 'login_required');
        if (data.state === 'login_required' && !sessionStorage.getItem('claude-login-dismissed')) show();
        if (data.state === 'connected') sessionStorage.removeItem('claude-login-dismissed');
      } catch { /* A network outage is not an expired login. */ }
    }
    check(); const timer = setInterval(check, 60000);
    window.addEventListener('raute:claude-login', show);
    return () => {disposed = true; clearInterval(timer); window.removeEventListener('raute:claude-login', show);};
  }, []);
  useEffect(() => {
    if (!active) return;
    let disposed = false;
    const timer = setInterval(async () => {
      try { const next = await request('/login/' + session.id); if (!disposed) setSession(next); }
      catch (e) { if (!disposed) {setError(e.message); setSession(s => ({...s, state:'failed'}));} }
    }, 1500);
    return () => {disposed = true; clearInterval(timer);};
  }, [session?.id, active]);
  useEffect(() => {
    if (session?.url && opened.current !== session.url) {
      opened.current = session.url;
      try { if (popup.current && !popup.current.closed) popup.current.location.replace(session.url); } catch { /* Link remains available. */ }
    }
    if (session?.state === 'connected') {
      setRequired(false); sessionStorage.removeItem('claude-login-dismissed'); popup.current?.close();
    }
  }, [session]);
  async function start() {
    popup.current = window.open('about:blank', 'raute-claude-login', 'popup,width=640,height=760');
    if (popup.current) popup.current.opener = null;
    opened.current = null; setBusy(true); setError(''); setCode('');
    try { setSession(await request('/login', {})); }
    catch (e) {setError(e.message); popup.current?.close();}
    finally {setBusy(false);}
  }
  async function close() {
    if (active) {
      setBusy(true);
      try { await request('/login/' + session.id + '/cancel', {}); }
      catch (e) {setError(e.message); setBusy(false); return;}
      setBusy(false); setSession(null);
    }
    popup.current?.close(); setCode(''); sessionStorage.setItem('claude-login-dismissed','1'); dialog.current.close();
  }
  async function confirm(e) {
    e.preventDefault(); setBusy(true); setError(''); const value = code; setCode('');
    try {setSession(await request('/login/' + session.id + '/code', {code:value}));}
    catch (e) {setError(e.message);}
    finally {setBusy(false);}
  }
  return <>
    {required && <button className="claude-login-alert btn" onClick={show}>Claude anmelden</button>}
    <dialog className="claude-login-dialog" ref={dialog} onCancel={e => {e.preventDefault(); if (!busy) close();}} aria-labelledby="claude-login-title">
      <h2 id="claude-login-title">{session?.state === 'connected' ? 'Claude ist verbunden' : 'Claude anmelden'}</h2>
      <p>{required ? 'Die Claude-Anmeldung auf dem Server ist abgelaufen oder fehlt. Melde das Konto erneut an, damit Claude wieder für eure Analysen verfügbar ist.' : 'Verbinde euer Claude-Konto direkt mit dem Server. Bestätige die Anmeldung im Claude-Fenster.'}</p>
      <ol className="claude-login-steps"><li>Anmeldung starten</li><li>Bei Claude bestätigen</li><li>Verbindung wird automatisch geprüft</li></ol>
      {session && <p role="status">{session.message}</p>}
      {error && <p role="alert" className="claude-login-error">{error}</p>}
      {session?.url && active && <p><a href={session.url} target="_blank" rel="noopener noreferrer">Claude-Anmeldefenster öffnen ↗</a></p>}
      {session?.state === 'waiting' && <form onSubmit={confirm}><label>Bestätigungscode, falls Claude einen anzeigt<input value={code} onChange={e=>setCode(e.target.value)} autoComplete="off" type="password" maxLength={4096} /></label><button className="btn" disabled={busy || !code.trim()}>Code bestätigen</button></form>}
      <div className="claude-login-actions">
        {!active && session?.state !== 'connected' && <button className="btn btn-primary" disabled={busy} onClick={start}>{busy ? 'Wird gestartet…' : 'Mit Claude anmelden'}</button>}
        <button className="btn" disabled={busy} onClick={close}>{active ? 'Abbrechen' : session?.state === 'connected' ? 'Fertig' : 'Später'}</button>
      </div>
    </dialog>
  </>;
}

import React, {useState, useRef, useEffect} from 'react';
import {Panel, Notice, t} from './shared.jsx';

export function ModelPicker({provider, name, value = '', label = 'Modell'}) {
  const options = [...new Set([...(provider?.models || []), value].filter(Boolean))];
  const [custom, setCustom] = useState(false);
  return <label className="platform-field"><span>{label}</span>
    <select aria-label={label} name={custom ? undefined : name} defaultValue={value}
      onChange={e => setCustom(e.target.value === '__custom')}>
      <option value="">Standard des Anbieters</option>
      {options.map(m => <option key={m} value={m}>{m}</option>)}
      <option value="__custom">Andere Modell-ID…</option>
    </select>
    {custom && <input name={name} aria-label={`${label} – eigene Modell-ID`} required maxLength={100} placeholder="Modell-ID" />}
  </label>;
}

function Provider({provider: p}) {
  const [test, setTest] = useState(null);
  const abort = useRef(null);
  useEffect(() => () => abort.current?.abort(), []);
  async function check() {
    if (test?.busy) return;
    setTest({busy: true, message: 'Verbindung wird geprüft…'});
    const controller = new AbortController(); abort.current = controller;
    const timeout = setTimeout(() => controller.abort(), 70000);
    try {
      const response = await fetch('/settings/ai/test?inline=1', {method: 'POST',
        headers: {Accept: 'application/json'}, body: new URLSearchParams({provider: p.key}), signal: controller.signal});
      const result = await response.json();
      if (!response.ok && !result.message) throw new Error();
      setTest({...result, message: result.message || 'Verbindung konnte nicht geprüft werden'});
    } catch { setTest({ok: false, message: 'Keine Antwort erhalten – bitte erneut testen'}); }
    finally {clearTimeout(timeout);}
  }
  return <article className="settings-provider">
    <div className="settings-row">
      <div className="settings-provider__icon" aria-hidden="true">{p.label.slice(0,1)}</div>
      <div className="settings-row__body"><h3>{p.label}</h3><p>{p.how || 'Noch nicht eingerichtet'}</p></div>
      {p.key === 'claude' && <button type="button" className="btn" onClick={() => window.dispatchEvent(new Event('raute:claude-login'))}>Anmelden</button>}
      <span className={`settings-status ${test?.ok ? 'is-success' : ''}`}>{test?.ok ? 'Geprüft' : p.connected ? 'Eingerichtet' : 'Nicht verbunden'}</span>
      <button type="button" className="btn" disabled={!p.connected || test?.busy} onClick={check}>{test?.busy ? 'Wird getestet…' : 'Verbindung testen'}</button>
    </div>
    {test && <div role="status" className={`settings-test ${test.ok ? 'is-success' : test.busy ? '' : 'is-error'}`}>
      <strong>{test.busy ? '◌ ' : test.ok ? '✓ ' : '! '}{test.message}</strong>
      {test.ok && <span>{test.model} · {test.seconds} s</span>}
      {test.busy && <span>Die gespeicherte Verbindung wird aufgerufen, maximal 60 Sekunden</span>}
    </div>}
    <details className="settings-config" open={!p.connected || undefined}>
      <summary>{p.connected ? 'Verbindung und Standardmodell bearbeiten' : 'Verbindung einrichten'}</summary>
      {p.subscription_only && <p>{p.connected ? 'Über das ChatGPT-Abo angemeldet' : 'Auf dem Server anmelden und den angezeigten Code im Browser bestätigen'}
        {!p.connected && <code className="ai-login__cmd">{p.login_command}</code>}</p>}
      <form method="post" action="/settings/ai/key" onChange={() => setTest(null)}>
        <input type="hidden" name="provider" value={p.key}/>
        <div className="settings-inputs">
          {!p.subscription_only && <label className="platform-field"><span>API-Schlüssel {p.hint ? '(gespeichert)' : '(optional bei bestehender Verbindung)'}</span>
            <input name="api_key" type="password" autoComplete="off" maxLength={500} placeholder={p.hint ? `…${p.hint}` : ''}/></label>}
          <ModelPicker provider={p} name="model" value={p.model}/>
        </div>
        <p className="settings-caption">Änderungen zuerst speichern, anschließend die Verbindung testen</p>
        <button className="btn btn--go" type="submit">Speichern</button>
      </form>
      {p.hint && <form method="post" action="/settings/ai/forget"><input type="hidden" name="provider" value={p.key}/><button className="btn btn--quiet">Schlüssel entfernen</button></form>}
    </details>
  </article>;
}

function RoleStep({role, number, ai}) {
  const initial = role.order[number-1] || '';
  const [provider, setProvider] = useState(initial);
  const p = ai.providers.find(x => x.key === provider);
  return <div className="settings-inputs">
    <label className="platform-field"><span>{number === 1 ? 'Anbieter' : `Ersatz ${number-1}`}</span>
      <select name={`${role.key}_${number}`} value={provider} aria-label={`${role.label} Anbieter ${number}`} onChange={e => setProvider(e.target.value)}>
        <option value="">{number === 1 ? 'Deaktiviert' : 'Kein Ersatz'}</option>
        {ai.providers.map(p => <option key={p.key} value={p.key}>{p.label}{p.connected ? '' : ' (nicht verbunden)'}</option>)}
      </select>
    </label>
    {p && <ModelPicker key={provider} provider={p} name={`${role.key}_model_${number}`} value={role.models?.[provider] || ''} label={`${role.label} Modell ${number}`}/>}
  </div>;
}

export function AiSettings({data: ai, roles = false}) {
  if (!ai) return null;
  return <Panel title={roles ? 'Modelle & Rollen' : 'KI-Verbindungen'} id={roles ? 'modelle-rollen' : 'ki-modelle'}>
    <p>{roles ? 'Wähle für jeden Arbeitsschritt einen Anbieter und ein Modell. Ersatzmodelle übernehmen, wenn ein Anbieter nicht verfügbar ist.' : 'Verwalte die verbundenen Anbieter und prüfe, ob ihr gespeichertes Modell antwortet.'}</p>
    <Notice>{ai.error}</Notice>{ai.notice && <Notice>{ai.notice}</Notice>}
    {!roles && !ai.secret_ready && <Notice>Auf dem Server fehlt NEWSPULSE_SESSION_SECRET. Ohne ihn werden keine Schlüssel gespeichert.</Notice>}
    {roles ? <form method="post" action="/settings/ai/order">
      {ai.roles.map(r => <article className="settings-role" key={r.key}>
        <header><h3>{r.label}</h3><p>{r.description}</p></header>
        <RoleStep role={r} number={1} ai={ai}/>
        <details><summary>Ersatzmodelle <span className="settings-caption">{r.order.slice(1).length} hinterlegt</span></summary>
          <RoleStep role={r} number={2} ai={ai}/><RoleStep role={r} number={3} ai={ai}/>
        </details>
      </article>)}
      <button type="submit" className="btn btn--go">Modelle und Reihenfolge speichern</button>
    </form> : <div className="settings-provider-list">{ai.providers.map(p => <Provider key={p.key} provider={p}/>)}</div>}
  </Panel>;
}

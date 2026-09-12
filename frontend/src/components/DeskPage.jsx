import React, { useEffect, useState } from 'react';
import { fetchDesk } from '../api.js';

export function DeskPage({ translations = {}, language = 'de' }) {
  const [board, setBoard] = useState(null);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const t = (text) => translations[text] ?? text;
  useEffect(() => {
    const controller = new AbortController();
    setError(null);
    fetchDesk(controller.signal).then(setBoard).catch((err) => {
      if (!controller.signal.aborted) setError(err.message);
    });
    return () => controller.abort();
  }, [attempt]);

  if (error) return <div role="alert">
    <p>{t(error === 'auth' ? 'Sitzung abgelaufen.' : 'Der Desk konnte nicht geladen werden.')}</p>
    {error === 'auth' ? <a href="/login?next=/desk">{t('Anmelden')}</a> :
      <button className="btn" onClick={() => setAttempt(attempt + 1)}>{t('Erneut versuchen')}</button>}
    <p><a href="/desk?view=classic">{t('Klassischen Desk öffnen')}</a></p>
  </div>;
  if (!board) return <p role="status">{t('Desk wird geladen…')}</p>;

  const date = (value) => value ? new Intl.DateTimeFormat(language, {
    day: '2-digit', month: '2-digit', timeZone: board.timezone,
  }).format(new Date(value)) : '';
  const metrics = [
    ['Aktive Mandanten', board.clients_active],
    ['Actions diesen Monat', board.actions_month, t('abgeliefert und nachgetragen')],
    ['Offene Opportunities', board.opportunities, t('Fenster noch offen')],
    ['Entscheidungen offen', board.decisions_open],
    ['Profile mit Lücken', board.twins_with_gaps, `${t('Schnitt')} ${board.twin_average} %`],
  ];
  return <>
    <div className="desk__h"><div className="desk__hi">{t('Guten Morgen.')}</div>
      <h1 className="desk__t">{t('Der Desk')}</h1>
      <p className="desk__sub">{t('Was zugesagt ist, was geliefert wurde, und was heute eine Entscheidung braucht.')}</p>
    </div>
    <div className="kpis">{metrics.map(([label, value, note]) => <div className="kpi" key={label}>
      <div className="kpi__l">{t(label)}</div><div className="kpi__v">{value}</div>
      {note && <div className="kpi__n">{note}</div>}
    </div>)}</div>
    <div className="desk-workspace"><div><div className="board">
      <div className="board__h"><h2 className="board__t">{t('Mandantenüberblick')}</h2>
        <span className="board__d">{t('Alle aktiven Mandanten auf einen Blick.')}</span></div>
      {board.rows.length ? <>
        <div className="board__wrap"><table><thead><tr>
          {['Mandant', 'Profil', 'Actions (Monat)', 'Vertrag / geliefert', 'Opportunities', 'Status'].map((label) =>
            <th scope="col" key={label}>{t(label)}</th>)}
        </tr></thead><tbody>{board.rows.map((row) => <tr key={row.client.id}>
          <td><a className="board__nm" href={`/client/${row.client.id}/overview`}>{row.client.name}</a>
            {row.client.industry && <div className="board__sec">{row.client.industry.slice(0, 44)}</div>}</td>
          <td><div className="twin" title={row.twin.required_total != null ? `${row.twin.required_filled}/${row.twin.required_total} Pflichtfelder beantwortet` : `${t('Profil')} ${row.twin.profile_filled}/${row.twin.profile_total}`}>
            <span className="twin__n">{row.twin.percent} %</span>
            <span className="twin__bar" aria-hidden="true"><span className="twin__fill" style={{width: `${row.twin.percent}%`}} /></span>
          </div></td>
          <td className="num" title={`${row.actions_month.released} ${t('aus RauteOS')} · ${row.actions_month.logged} ${t('nachgetragen')}`}>{row.actions_month.total}</td>
          <td className="num">{row.promised_quarter === null ? <span className="deal deal--none">{t('nicht hinterlegt')}</span> :
            <span className={`deal deal--${row.on_track ? 'met' : 'behind'}`}>{row.promised_quarter} / {row.actions_quarter.total}</span>}</td>
          <td className="num">{row.opportunities || '—'}</td>
          <td><span className={`st st--${row.status}`}><span className="dot" />
            {t(row.status === 'krise' ? 'Krise offen' : row.status === 'aktiv' ? 'Etwas passiert gerade' : 'Aktuell nichts Relevantes')}</span></td>
        </tr>)}</tbody></table></div>
        <details className="log"><summary>{t('Action nachtragen — Gespräch, Briefing, Redaktionsbesuch')}</summary>
          <form className="log__f" method="post" action="/desk/action">
            <select name="client_id" aria-label={t('Mandant')}>{board.rows.map(({client}) =>
              <option key={client.id} value={client.id}>{client.name}</option>)}</select>
            <input type="text" name="title" required maxLength={200} aria-label={t('Was war es? z. B. Hintergrundgespräch Handelsblatt')} placeholder={t('Was war es? z. B. Hintergrundgespräch Handelsblatt')} />
            <input type="date" name="happened_on" aria-label={t('Wann')} />
            <input type="hidden" name="redirect_to" value="/desk" />
            <button type="submit" className="btn">{t('Eintragen')}</button>
          </form>
        </details>
      </> : <p className="pane__empty">{t('Noch kein Mandant angelegt.')} <a href="/mandant/neu">{t('Mandant hinzufügen')} →</a></p>}
    </div>
    <div className="panes">
      <Pane title={t('Braucht Entscheidung')} count={board.decisions_open}>
        {board.decisions.slice(0, 8).map((item, index) => <a className="row" href={item.href} key={`${item.href}-${index}`}>
          <div className="row__c">{item.client.name} <span className={`tag tag--${({kundenfreigabe: 'kunde', freigabe: 'agentur'})[item.kind] ?? item.kind}`}>
            {t(({kundenfreigabe: 'Kundenabstimmung', freigabe: 'Freigabe', impuls: 'Impuls', profil: 'Profil'})[item.kind])}</span></div>
          <div className="row__t">{item.title.slice(0, 70)}</div><div className="row__d">{item.detail}</div>
          {item.since && <div className="row__age">{t('seit')} {date(item.since)}</div>}
        </a>)}
        {!board.decisions.length && <p className="pane__empty">{t('Nichts wartet auf eine Entscheidung.')}</p>}
      </Pane>
      <Pane title={t('In Arbeit')} count={board.in_flight.length}>
        {board.in_flight.slice(0, 8).map((item, index) => <a className="row" href={item.href} key={`${item.href}-${index}`}>
          <div className="row__c">{item.client.name} <span className={`tag tag--${item.state}`}>{t(item.state === 'raus' ? 'Raus' : 'Entwurf')}</span></div>
          <div className="row__t">{item.title.slice(0, 70)}</div><div className="row__age">{date(item.since)}</div>
        </a>)}
        {!board.in_flight.length && <p className="pane__empty">{t('Nichts unterwegs.')}</p>}
      </Pane>
      <Pane title={t('Profile mit Wissenslücken')} count={board.twins_with_gaps}>
        {board.rows.filter((row) => row.twin.gaps.length).map((row) => <a className="row" href={`/client/${row.client.id}/twin`} key={row.client.id}>
          <div className="row__t">{row.client.name}</div><div className="row__d">{row.twin.gaps.map(t).join(' · ')}</div>
          <div className="row__age">{t('Profil')} {row.twin.percent} %</div>
        </a>)}
        {!board.twins_with_gaps && <p className="pane__empty">{t('Jedes Profil ist vollständig.')}</p>}
      </Pane>
    </div>
    </div></div>
  </>;
}

function Pane({ title, count, children }) {
  return <section className="pane"><div className="pane__h"><h2 className="pane__t">{title}</h2>
    <span className="pane__n">{count}</span></div><div className="pane__b">{children}</div></section>;
}

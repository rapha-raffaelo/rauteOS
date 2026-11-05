import React, { useEffect, useState } from 'react';
import { fetchDesk } from '../api.js';

// What the Desk calls each kind of decision, in a list and in the briefing.
const KIND = {kundenfreigabe: 'Kundenfreigabe', freigabe: 'Freigabe', impuls: 'Impuls', profil: 'Profil'};
const KIND_TAG = {kundenfreigabe: 'kunde', freigabe: 'agentur'};
const WAITS = {kundenfreigabe: 'wartet auf eine Kundenfreigabe', freigabe: 'wartet auf die Freigabe',
  impuls: 'hat einen neuen Impuls', profil: 'braucht eine Profil-Entscheidung'};

// A first name only when the address starts with one ("lucas@…"), never a
// guess from initials ("r.mankopf@…").
export function firstName(email) {
  const head = (email || '').split('@')[0].split(/[._-]/)[0];
  return head.length > 1 && /^[a-zäöüß]+$/i.test(head) ? head[0].toUpperCase() + head.slice(1) : '';
}

function shellUser() {
  try { return JSON.parse(document.getElementById('react-shell-data')?.textContent || '{}').user; }
  catch { return null; }
}

function greeting(hour) {
  return hour < 11 ? 'Guten Morgen' : hour < 18 ? 'Guten Tag' : 'Guten Abend';
}

// The briefing is assembled from the Desk's own figures: nothing in it that the
// page below does not show.
export function briefing(board, t) {
  const n = board.decisions_open;
  const lead = n ? `${n} ${t(n === 1 ? 'offene Entscheidung' : 'offene Entscheidungen')}` : t('Keine offene Entscheidung');
  const named = [];
  for (const item of board.decisions) {
    if (named.find((d) => d.client.id === item.client.id)) continue;
    named.push(item);
    if (named.length === 2) break;
  }
  const crises = board.rows.filter((r) => r.status === 'krise').map((r) => r.client.name);
  const sentences = named.map((d) => `${d.client.name} ${t(WAITS[d.kind] || 'wartet auf eine Entscheidung')}.`);
  if (crises.length) sentences.unshift(`${t('Krise offen bei')} ${crises.join(', ')}.`);
  if (board.opportunities) sentences.push(`${board.opportunities} ${t(board.opportunities === 1 ? 'Chance ist offen.' : 'Chancen sind offen.')}`);
  return {lead, rest: sentences.join(' ')};
}

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

  const zone = board.timezone;
  const date = (value) => value ? new Intl.DateTimeFormat(language, {
    day: '2-digit', month: '2-digit', timeZone: zone,
  }).format(new Date(value)) : '';
  const now = new Date();
  const hour = Number(new Intl.DateTimeFormat('en-GB', {hour: 'numeric', hourCycle: 'h23', timeZone: zone}).format(now));
  const today = new Intl.DateTimeFormat(language, {weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: zone}).format(now);
  const name = firstName(shellUser());
  const customer = board.decisions.filter((d) => d.kind === 'kundenfreigabe');
  const waiting = board.in_flight.filter((item) => item.state === 'raus');
  const chances = board.chances || [];
  const brief = briefing(board, t);
  const stats = [
    ['Entscheidungen offen', board.decisions_open,
      customer.length ? `${customer.length} ${t('davon beim Kunden')}` : t('Nichts blockiert'), customer.length > 0],
    ['In Arbeit', board.in_flight.length, `${waiting.length} ${t('warten auf Antwort')}`, false],
    ['Offene Chancen', board.opportunities, t('Fenster noch offen'), false],
    ['Actions diesen Monat', board.actions_month, t('abgeliefert und nachgetragen'), false],
  ];

  return <>
    <header className="desk__h">
      <div>
        <p className="desk__eyebrow">{t('Dein Arbeitsplatz')}</p>
        <h1 className="desk__t">{t(greeting(hour))}{name ? `, ${name}` : ''}.</h1>
        <p className="desk__sub">{today} · {t('Alle Kunden und Aufgaben im Blick.')}</p>
      </div>
      <div className="desk__acts">
        <a className="btn btn--ghost" href="/clients">{t('Alle Kunden')}</a>
        <a className="btn btn--go" href="/mandant/neu">+ {t('Neuer Mandant')}</a>
      </div>
    </header>

    <section className="brief" aria-label={t('Dein Briefing von RAUTE')}>
      <div>
        <p className="brief__l"><svg className="ico" aria-hidden="true"><use href="#ico-raute" /></svg>{t('Dein Briefing von RAUTE')}</p>
        <p className="brief__t"><strong>{brief.lead}</strong> {t('für heute.')} {brief.rest}</p>
      </div>
      <a className="brief__go" href="/ask">{t('Briefing vertiefen')} →</a>
    </section>

    <div className="stat-row">{stats.map(([label, value, hint, bad]) => <div className="stat" key={label}>
      <small>{t(label)}</small><strong>{value}</strong>
      <span className={`stat__hint${bad ? ' stat__hint--bad' : ''}`}>{hint}</span>
    </div>)}</div>

    <div className="desk-grid">
      <div className="desk-col">
        <Card title={t('Heute priorisiert')} link={board.decisions.length > 5 ? ['/desk#entscheidungen', t('Alle Entscheidungen')] : null}>
          {board.decisions.slice(0, 5).map((item, index) => <a className="task" href={item.href} key={`${item.href}-${index}`}>
            <span className="task__box" aria-hidden="true" />
            <span className="task__b"><span className="task__t">{item.title.slice(0, 80)}</span>
              <span className="task__m">{item.client.name} · {item.since ? `${t('seit')} ${date(item.since)}` : t(KIND[item.kind])}{item.detail ? ` · ${item.detail}` : ''}</span></span>
            <span className={`badge badge--${KIND_TAG[item.kind] ?? item.kind}`}>{t(KIND[item.kind])}</span>
          </a>)}
          {!board.decisions.length && <p className="pane__empty">{t('Nichts wartet auf eine Entscheidung.')}</p>}
        </Card>
        <Card title={t('Relevante Chancen')} link={['/today', t('Intelligence öffnen')]}>
          {chances.map((c) => <a className="chance" href={c.href} key={c.href}>
            <span className="chance__ico" aria-hidden="true"><svg className="ico"><use href="#ico-intel" /></svg></span>
            <span className="task__b"><span className="task__t">{c.title.slice(0, 90)}</span>
              <span className="task__m">{c.client.name} · {t(c.kind === 'detected' ? 'Erkannte Chance' : 'Entwickelte Chance')}{c.since ? ` · ${date(c.since)}` : ''}</span></span>
            <span className="chance__go" aria-hidden="true">›</span>
          </a>)}
          {!chances.length && <p className="pane__empty">{t('Gerade keine offene Chance.')}</p>}
        </Card>
      </div>
      <div className="desk-col">
        <Card title={t('Das braucht Deine Aufmerksamkeit')}>
          {board.in_flight.slice(0, 5).map((item, index) => <a className="info-row" href={item.href} key={`${item.href}-${index}`}>
            <span className="info-row__ico" aria-hidden="true"><svg className="ico"><use href={item.state === 'raus' ? '#ico-media' : '#ico-texte'} /></svg></span>
            <span className="task__b"><span className="task__t">{item.title.slice(0, 70)}</span>
              <span className="task__m">{item.client.name} · {t(item.state === 'raus' ? 'Raus, wartet auf Antwort' : 'Entwurf')}</span></span>
            <span className="info-row__age">{date(item.since)}</span>
          </a>)}
          {!board.in_flight.length && <p className="pane__empty">{t('Nichts unterwegs.')}</p>}
        </Card>
        <Tile icon="profil" title={t('Kundenfreigaben')} note={t('Warten auf Abstimmungen')}
          count={customer.length} unit={t('offen')} href={customer[0]?.href} />
        <Tile icon="clients" title={t('Profile mit Wissenslücken')} note={`${t('Schnitt')} ${board.twin_average} %`}
          count={board.twins_with_gaps} unit={t('Profile')} href="/clients" />
        <Tile icon="media" title={t('Warten auf Antwort')} note={t('Offene Rückmeldungen')}
          count={waiting.length} unit={t(waiting.length === 1 ? 'Vorgang' : 'Vorgänge')} href={waiting[0]?.href} />
      </div>
    </div>

    <div className="board" id="mandanten">
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
        <details className="log"><summary>{t('Action nachtragen: Gespräch, Briefing, Redaktionsbesuch')}</summary>
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
  </>;
}

function Card({ title, link, children }) {
  return <section className="dcard"><div className="dcard__h"><h2>{title}</h2>
    {link && <a className="inline-link" href={link[0]}>{link[1]} →</a>}</div>
    <div className="dcard__b">{children}</div></section>;
}

function Tile({ icon, title, note, count, unit, href }) {
  const body = <><span className="info-row__ico" aria-hidden="true"><svg className="ico"><use href={`#ico-${icon}`} /></svg></span>
    <span className="task__b"><span className="task__t">{title}</span><span className="task__m">{note}</span></span>
    <span className={`badge${count ? ' badge--kunde' : ''}`}>{count} {unit}</span></>;
  return href ? <a className="mini-tile" href={href}>{body}</a> : <div className="mini-tile">{body}</div>;
}

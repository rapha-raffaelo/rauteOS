import React, {useState} from 'react';
import {date, t} from './shared.jsx';
import './media-shortlist.css';

// The two coverage sets may overlap: never add their article counts together.
function combine(market = [], own = []) {
  const rows = new Map();
  for (const [kind, entries] of [['market', market], ['own', own]]) {
    for (const entry of entries) {
      const key = entry.name.trim().toLocaleLowerCase('de');
      if (!key) continue;
      const row = rows.get(key) || {name: entry.name, market: null, own: null};
      row[kind] = entry.articles;
      if (entry.last_seen && (!row.last_seen || new Date(entry.last_seen) > new Date(row.last_seen))) row.last_seen = entry.last_seen;
      rows.set(key, row);
    }
  }
  return [...rows.values()].sort((a, b) => a.name.localeCompare(b.name, 'de'));
}

export function MediaShortlist({data}) {
  const [kind, setKind] = useState('authors');
  const [query, setQuery] = useState('');
  const [scope, setScope] = useState('all');
  const [page, setPage] = useState(0);
  const rows = kind === 'authors' ? combine(data.market_authors, data.own_authors) : combine(data.market_outlets, data.own_outlets);
  const words = query.trim().toLocaleLowerCase('de').split(/\s+/).filter(Boolean);
  const matches = rows.filter(row => words.every(word => row.name.toLocaleLowerCase('de').includes(word)) && (scope === 'all' || row[scope] !== null));
  const pages = Math.max(1, Math.ceil(matches.length / 20));
  const current = Math.min(page, pages - 1);
  return <section className="media-shortlist" aria-label={t('Wen ansprechen')}>
    <header className="media-shortlist__heading"><div><h3>{t('Wen ansprechen')}</h3><p>{t('Aus der erfassten Berichterstattung')} · {data.days} {t('Tage')}</p></div><a className="btn" href="/contacts">{t('Kontaktbuch öffnen')} →</a></header>
    <p className="media-shortlist__hint">{t('Häufig genannte Autoren und Medien aus dem Archiv. Die Liste ist keine vollständige Kontaktliste; Artikelzahlen zeigen Berichterstattung, keine bestehende Beziehung.')}</p>
    <div className="media-shortlist__tabs" role="group" aria-label={t('Liste wählen')}>
      {[['authors', 'Journalistinnen und Journalisten'], ['outlets', 'Medien']].map(([value, label]) => <button type="button" key={value} aria-pressed={kind === value} onClick={() => {setKind(value); setQuery(''); setPage(0);}}>{t(label)}</button>)}
    </div>
    <div className="media-shortlist__filters">
      <label>{t(kind === 'authors' ? 'Journalisten suchen' : 'Medien suchen')}<input type="search" value={query} placeholder={t('Name eingeben …')} onChange={event => {setQuery(event.target.value); setPage(0);}}/></label>
      <label>{t('Berichterstattung')}<select value={scope} onChange={event => {setScope(event.target.value); setPage(0);}}><option value="all">{t('Alle')}</option><option value="own">{t('Über den Kunden')}</option><option value="market">{t('Im Themenfeld')}</option></select></label>
    </div>
    <p className="media-shortlist__count" role="status">{matches.length} {t('von')} {rows.length} {t('Einträgen')}</p>
    {matches.length ? <div className="media-shortlist__table"><table><caption className="media-shortlist__caption">{t('Berichterstattung nach Autor oder Medium')}</caption><thead><tr><th scope="col">{t(kind === 'authors' ? 'Name laut Quelle' : 'Medium')}</th><th scope="col">{t('Artikel über den Kunden')}</th><th scope="col">{t('Artikel im Themenfeld')}</th><th scope="col">{t('Zuletzt erschienen')}</th><th scope="col">{t('Kontaktbuch')}</th></tr></thead><tbody>{matches.slice(current * 20, current * 20 + 20).map(row => <tr key={row.name}><th scope="row">{row.name}</th><td>{row.own ?? '—'}</td><td>{row.market ?? '—'}</td><td>{date(row.last_seen)}</td><td><a href={`/contacts?q=${encodeURIComponent(row.name)}`} aria-label={`${row.name}: ${t('Im Kontaktbuch suchen')}`}>{t('Kontakt suchen')} →</a></td></tr>)}</tbody></table></div> : <div className="media-shortlist__empty"><p>{t(rows.length ? 'Keine passenden Einträge gefunden.' : kind === 'authors' ? 'In diesem Zeitraum wurden keine Autorennamen von den Quellen mitgeliefert.' : 'In diesem Zeitraum wurde keine Berichterstattung erfasst.')}</p>{(query || scope !== 'all') && <button type="button" className="btn" onClick={() => {setQuery(''); setScope('all'); setPage(0);}}>{t('Filter zurücksetzen')}</button>}</div>}
    {pages > 1 && <nav className="media-shortlist__pagination" aria-label={t('Listenseiten')}><button type="button" className="btn" disabled={current === 0} onClick={() => setPage(current - 1)}>{t('Zurück')}</button><span>{current + 1} / {pages}</span><button type="button" className="btn" disabled={current + 1 === pages} onClick={() => setPage(current + 1)}>{t('Weiter')}</button></nav>}
    <p className="media-shortlist__hint">{t('Die beiden Artikelspalten können sich überschneiden und werden deshalb nicht addiert. Ein Strich bedeutet: kein Eintrag in dieser Auswertung.')}</p>
  </section>;
}

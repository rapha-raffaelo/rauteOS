import React,{useState} from 'react';
import {ClientActions} from './ClientActions.jsx';
import {PageHeading,EmptyState} from './PageHeading.jsx';
function initials(name){return name.trim().split(/[\s.\-]+/).filter(Boolean).slice(0,2).map(word=>word[0]).join('').toUpperCase();}
export function ClientsPage({clients}){
 const [search,setSearch]=useState('');
 const visible=clients.filter(row=>row.client.name.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
 return <section className="clients-page"><PageHeading eyebrow="MANDANTEN" title="Clients" description="Deine Mandate. Ihr Wissen. Die nächsten Chancen."><a className="btn btn--go" href="/mandant/neu"><span aria-hidden="true">＋</span> Neuer Mandant</a></PageHeading>
 <div className="clients-toolbar"><label className="client-search"><span>Mandanten suchen</span><input type="search" placeholder="Name eingeben …" value={search} onChange={e=>setSearch(e.target.value)}/></label><p>{visible.length} von {clients.length} Mandanten</p></div>
 <div className="workbench-list client-grid">{visible.map(row=><article className="client-card" key={row.client.id}>
 <div className="client-card-top"><span className="client-monogram" aria-hidden="true">{initials(row.client.name)}</span><span className={`client-status client-status--${row.status}`}>{row.status==='krise'?'Krise':row.status==='aktiv'?'In Arbeit':'Im Überblick'}</span></div>
 <h2><a href={`/client/${row.client.id}/overview`}>{row.client.name}<span aria-hidden="true">↗</span></a></h2><p className="client-industry">{row.client.industry||'Branche noch offen'}</p>
 <div className="client-completeness"><div><span>Profilwissen</span><strong>{row.twin.percent} %</strong></div><progress aria-label={`Profilvollständigkeit ${row.client.name}`} value={row.twin.percent} max="100"/></div>
 <dl className="client-card-metrics"><div><dt>Opportunities</dt><dd>{row.opportunities}</dd></div><div><dt>Im Quartal geliefert</dt><dd>{row.actions_quarter.total}{row.promised_quarter!=null&&<small> / {row.promised_quarter}</small>}</dd></div></dl>
 <div className="client-card-footer"><ClientActions client={row.client}/><span>{row.promised_quarter==null?'Zusage offen':`${row.promised_quarter} zugesagt`}</span></div>
 </article>)}</div>
 {!visible.length&&<EmptyState title={clients.length?'Keine passenden Mandanten':'Dein erster Mandant'}>{clients.length?'Versuche einen anderen Suchbegriff.':'Lege einen Mandanten an, um Profilwissen und Opportunities aufzubauen.'}</EmptyState>}
 </section>;
}

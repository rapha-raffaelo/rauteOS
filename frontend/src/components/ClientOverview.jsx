import React from 'react';

const statusNames={draft:'Entwurf',active:'Aktiviert',closed:'Abgeschlossen'};
const eventNames={idea_developed:'Idee entwickelt',activated:'Opportunity aktiviert',choices_saved:'Auswahl gespeichert',text_created:'Text erstellt',text_checked:'Aussagen geprüft',text_edited:'Text bearbeitet'};
const formatNames={kundenmail:'Kundenmail',pitch:'Pitch',statement:'Statement',pressemitteilung:'Pressemitteilung',linkedin:'LinkedIn',qa:'Q&A'};
const date=value=>value?new Date(value).toLocaleDateString('de-DE',{day:'2-digit',month:'short'}):'';

export function ClientOverview({data,clientId}){
 const base=`/client/${clientId}`;
 const summary=data.summary;
 const twin=summary?.twin;
 const opportunities=data.opportunities;
 const texts=data.texts.slice(0,4);
 const metrics=[
  ['Client Twin',twin?`${twin.percent} %`:'–','Vollständigkeit des Profils'],
  ['Geliefert im Quartal',summary?.actions_quarter.total??'–','Freigegebene und erfasste Leistungen'],
  ['Vereinbart im Quartal',summary?.promised_quarter??'–',summary?.promised_quarter==null?'Noch keine Zusage hinterlegt':'Vereinbarte Leistungen'],
  ['Offene Opportunities',summary?.opportunities??'–','Erkannte und entwickelte Chancen'],
 ];
 return <section className="client-overview">
  <header className="co-header"><div><p className="co-eyebrow">MANDANTENÜBERSICHT</p><h1>{data.client.name}</h1><p className="co-subtitle">Chancen, Wissen und Ergebnisse für dieses Mandat.</p></div><a className="btn btn--go" href={`${base}/opportunities?develop=1`}>+ Opportunity entwickeln</a></header>
  <div className="co-metrics">{metrics.map(([label,value,note])=><div className="co-metric" key={label}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>)}</div>
  <div className="co-layout"><div className="co-main">
   <section className="co-panel"><header className="co-panel-head"><div><p className="co-eyebrow">CHANCEN ERKENNEN UND ENTWICKELN</p><h2>Opportunities <span className="co-count">{opportunities.length}</span></h2></div>{opportunities.length>6&&<a href={`${base}/opportunities`}>Alle öffnen →</a>}</header>
    <div className="co-opportunities">{opportunities.length?opportunities.slice(0,6).map(o=><a className="co-opportunity" key={`${o.context_kind}-${o.context_id}`} href={`${base}/opportunities?kind=${o.context_kind}&context=${o.context_id}`}><div className="co-card-meta"><span>{o.context_kind==='detected'?'Erkannte Chance':'Entwickelte Chance'}</span><span className={`co-status co-status--${o.status}`}>{statusNames[o.status]||o.status}</span></div><h3>{o.title}</h3><span className="co-card-action">Chance prüfen <span aria-hidden="true">↗</span></span></a>):<div className="co-empty"><span className="co-empty-icon" aria-hidden="true">↗</span><h3>Raum für die nächste gute Idee</h3><p>Entwickle eine Kommunikationschance aus dem Twin und aktueller Recherche.</p></div>}</div>

   </section>
   <section className="co-panel"><header className="co-panel-head"><div><p className="co-eyebrow">VON DER IDEE ZUM ENTWURF</p><h2>Aktuelle Texte</h2></div></header>
    {texts.length?<div className="co-texts">{texts.map(t=><a className="co-text" key={`${t.type}-${t.id}`} href={t.href}><span className="co-document" aria-hidden="true">≡</span><div><small>{formatNames[t.format]||t.format} · {date(t.generated_at)}</small><h3>{t.title||'Ohne Titel'}</h3></div><span className="co-status">{t.released_at?'Freigegeben':'Entwurf'}</span><span aria-hidden="true">↗</span></a>)}</div>:<div className="co-empty co-empty--text"><span className="co-empty-icon" aria-hidden="true">≡</span><div><h3>Noch keine Texte erstellt</h3><p>Öffne eine Opportunity und beginne mit einem Vorschlag für den Kunden. Deine Entwürfe erscheinen anschließend hier.</p></div></div>}
   </section>
  </div><aside className="co-aside">
   <section className="co-panel co-twin"><p className="co-eyebrow">WISSENSBASIS</p><div className="co-twin-heading"><h2>Client Twin</h2><strong>{twin?`${twin.percent} %`:'–'}</strong></div>{twin&&<div className="co-progress" role="progressbar" aria-label="Vollständigkeit des Client Twin" aria-valuenow={twin.percent} aria-valuemin={0} aria-valuemax={100}><span style={{width:`${twin.percent}%`}}/></div>}<p>Ein gepflegter Twin liefert den Kontext für fundierte Vorschläge.</p><div className="co-gap"><h3>{twin?.gaps.length?'Profil vervollständigen':'Profil prüfen'}</h3>{twin?.gaps.length?<ul>{twin.gaps.slice(0,4).map(g=><li key={g}>{g}</li>)}</ul>:<p>{twin?'Keine offenen Pflichtfelder. Einzelne Aussagen und Quellen bleiben im Twin prüfbar.':'Für dieses Mandat liegt noch keine Zusammenfassung vor.'}</p>}</div><a className="btn" href={`${base}/twin`}>Twin bearbeiten <span aria-hidden="true">→</span></a></section>
   <section className="co-panel co-activity"><header className="co-panel-head"><h2>Letzte Aktivität</h2><a href={`${base}/actions`}>Alle →</a></header>{data.activity?.length?<ol>{data.activity.slice(0,4).map(e=><li key={e.id}><span className="co-activity-dot" aria-hidden="true"/><div><a href={e.href}>{eventNames[e.kind]||e.kind}</a><small>{date(e.happened_at)}{e.actor&&` · ${e.actor}`}</small></div></li>)}</ol>:<p className="co-quiet">Noch keine Arbeitsschritte erfasst. Entwicklung und Textarbeit werden hier sichtbar.</p>}</section>
  </aside></div>
 </section>;
}

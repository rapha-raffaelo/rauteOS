import React from 'react';
import {ClientTitle} from './ClientLogo.jsx';

const statusNames={draft:'Entwurf',active:'Aktiviert',closed:'Abgeschlossen'};
const eventNames={idea_developed:'Idee entwickelt',activated:'Opportunity aktiviert',choices_saved:'Auswahl gespeichert',text_created:'Text erstellt',text_checked:'Aussagen geprüft',text_edited:'Text bearbeitet'};
const formatNames={kundenmail:'Kundenmail',pitch:'Pitch',statement:'Statement',pressemitteilung:'Pressemitteilung',linkedin:'LinkedIn',qa:'Q&A'};
// An opportunity can be months old, so its date names the year when it is not this one.
const longDate=value=>{const d=new Date(value);return d.toLocaleDateString('de-DE',{day:'numeric',month:'long',...(d.getFullYear()===new Date().getFullYear()?{}:{year:'numeric'})});};
const date=value=>value?new Date(value).toLocaleDateString('de-DE',{day:'2-digit',month:'short'}):'';

export function ClientOverview({data,clientId}){
 const base=`/client/${clientId}`;
 const summary=data.summary;
 const twin=summary?.twin;
 const opportunities=data.opportunities;
 const texts=data.texts.slice(0,4);
 const parts=twin?.parts||{};
 const part=(label,p,note)=>p&&<div className="co-part"><div><span>{label}</span><strong>{p.filled}<small> / {p.total} {note}</small></strong></div><div className="co-bar"><span style={{width:`${p.total?Math.round(100*p.filled/p.total):0}%`}}/></div></div>;
 const open=[parts.R&&parts.R.total-parts.R.filled&&`${parts.R.total-parts.R.filled} Recherche-Themen ohne Angabe`,
  parts.Q&&parts.Q.total-parts.Q.filled&&`${parts.Q.total-parts.Q.filled} Kundenfragen offen`].filter(Boolean);
 const company=data.company||{};
 const steps=data.next_steps||[];
 const running=opportunities.filter(o=>o.status!=='closed');
 const quarter=summary?.actions_quarter;
 const promised=summary?.promised_quarter;
 const bar=(label,value,of)=><div className="co-deliv" key={label}><span>{label}</span><span className="co-bar"><span style={{width:`${of?Math.min(100,Math.round(100*value/of)):0}%`}}/></span><strong>{value}{of!=null?`/${of}`:''}</strong></div>;
 const impact=[['Veröffentlichungen',data.released_texts?.length??0],['Berichte',data.released_reports?.length??0],['Offene Chancen',summary?.opportunities??0],['Profil',twin?`${twin.percent} %`:'–']];
 const stepNames={aufgabe:'Aufgabe',kundenfreigabe:'Kundenfreigabe',freigabe:'Freigabe',impuls:'Impuls',profil:'Profil'};
 return <section className="client-overview">
  <header className="co-header"><div><p className="co-eyebrow">CLIENT WORKSPACE</p><h1><ClientTitle client={data.client}/></h1><p className="co-subtitle">{company.legal_name&&<>Unternehmen dahinter: {company.legal_name}{company.tags?.length?' · ':''}</>}{company.tags?.length?company.tags.join(' · '):company.legal_name?'':'Chancen, Wissen und Ergebnisse für dieses Mandat.'}</p></div>
   <div className="co-actions"><a className="btn btn--ghost" href={`/ask?client_id=${clientId}`}>Zu {data.client.name} fragen</a><a className="btn btn--go" href={`${base}/opportunities?develop=1`}>+ Opportunity entwickeln</a></div></header>
  <div className="co-layout"><div className="co-main">
   <section className="co-panel co-company"><header className="co-panel-head"><h2>Das Unternehmen</h2><span className="badge">Client Intelligence</span></header>
    <div className="co-company-body">
     {company.description?<p className="co-desc">{company.description}</p>:<p className="co-quiet">Noch keine Unternehmensbeschreibung recherchiert. <a href={`${base}/twin`}>Im Profil ergänzen →</a></p>}
     <p className="co-eyebrow">ZENTRALES GESCHÄFTSZIEL</p>
     {company.goal?<p className="co-goal">{company.goal}</p>:<p className="co-quiet">Hat der Kunde noch nicht beantwortet (Kundenfrage 2). <a href={`${base}/twin`}>Zum Fragebogen →</a></p>}
     {!!company.tags?.length&&<div className="co-tags">{company.tags.map(t=><span className="badge" key={t}>{t}</span>)}</div>}
    </div></section>
   <section className="co-panel"><header className="co-panel-head"><h2>Laufende Stories <span className="co-count">{running.length}</span></h2><a href={`${base}/opportunities`}>Alle Stories →</a></header>
    <div className="co-opportunities">{running.length?running.slice(0,6).map(o=><a className="co-opportunity" key={`${o.context_kind}-${o.context_id}`} href={`${base}/opportunities?kind=${o.context_kind}&context=${o.context_id}`}><div className="co-card-meta"><span>{o.context_kind==='detected'?'Erkannte Chance':'Entwickelte Chance'}{o.created_at&&<> · <time dateTime={o.created_at}>{longDate(o.created_at)}</time></>}</span><span className={`co-status co-status--${o.status}`}>{statusNames[o.status]||o.status}</span></div><h3>{o.title}</h3></a>):<div className="co-empty"><span className="co-empty-icon" aria-hidden="true">↗</span><h3>Raum für die nächste gute Idee</h3><p>Entwickle eine Kommunikationschance aus dem Profil und aktueller Recherche.</p></div>}</div>
   </section>
   <section className="co-panel"><header className="co-panel-head"><h2>Aktuelle Texte</h2></header>
    {texts.length?<div className="co-texts">{texts.map(t=><a className="co-text" key={`${t.type}-${t.id}`} href={t.href}><span className="co-document" aria-hidden="true">≡</span><div><small>{t.format_name||formatNames[t.format]||t.format} · {date(t.generated_at)}</small><h3>{t.title||'Ohne Titel'}</h3></div><span className="co-status">{t.released_at?'Freigegeben':'Entwurf'}</span><span aria-hidden="true">↗</span></a>)}</div>:<div className="co-empty co-empty--text"><span className="co-empty-icon" aria-hidden="true">≡</span><div><h3>Noch keine Texte erstellt</h3><p>Öffne eine Opportunity und beginne mit einem Vorschlag für den Kunden. Deine Entwürfe erscheinen anschließend hier.</p></div></div>}
   </section>
  </div><aside className="co-aside">
   <section className="co-panel co-delivery"><header className="co-panel-head"><h2>Leistungen · Quartal</h2><a href={`${base}/actions`}>Nachweis →</a></header>
    <div className="co-delivery-body">{quarter?<>{bar('Actions gesamt',quarter.total,promised)}{bar('Aus RauteOS',quarter.released,promised)}{bar('Nachgetragen',quarter.logged,promised)}</>:<p className="co-quiet">Noch keine Leistungen erfasst.</p>}
     {promised==null&&<p className="co-quiet">Noch keine Zusage hinterlegt.</p>}</div></section>
   <section className="co-panel"><header className="co-panel-head"><h2>Wirkung im Überblick</h2><a href={`${base}/ki`}>Alle KPIs →</a></header>
    <div className="co-impact">{impact.map(([label,value])=><div className="co-tile" key={label}><small>{label}</small><strong>{value}</strong></div>)}</div></section>
   <section className="co-panel co-steps"><header className="co-panel-head"><h2>Nächste Schritte</h2></header>
    {steps.length?<div className="co-step-list">{steps.map((d,i)=><a className="co-step" href={d.href} key={`${d.href}-${i}`}><span className="co-step-box" aria-hidden="true"/><div><h3>{d.title}</h3><small>{d.detail||stepNames[d.kind]}</small></div><span className="badge">{stepNames[d.kind]||d.kind}</span></a>)}</div>:<p className="co-quiet">Gerade wartet nichts auf eine Entscheidung.</p>}</section>
   <section className="co-panel co-twin"><p className="co-eyebrow">WISSENSBASIS</p><h2>Profil</h2>
    {twin?<div className="co-twin-body"><div className="co-ring" style={{'--p':twin.percent}} role="progressbar" aria-label="Vollständigkeit des Profils" aria-valuenow={twin.percent} aria-valuemin={0} aria-valuemax={100}><strong>{twin.percent} %</strong><span>vollständig</span></div>
     <div className="co-parts">{part('Steckbrief',parts.R,'recherchiert')}{part('Fragebogen',parts.Q,'beantwortet')}</div></div>:<p>Für dieses Mandat liegt noch keine Zusammenfassung vor.</p>}
    {open.length>0&&<div className="co-gap"><h3>Profil vervollständigen</h3><ul>{open.map(g=><li key={g}>{g}</li>)}</ul></div>}
    <a className="btn" href={`${base}/twin`}>Profil bearbeiten <span aria-hidden="true">→</span></a></section>
   <section className="co-panel co-activity"><header className="co-panel-head"><h2>Letzte Aktivität</h2>{data.activity?.length>4&&<a href={`${base}/actions`}>Alle →</a>}</header>{data.activity?.length?<ol>{data.activity.slice(0,4).map(e=><li key={e.id}><span className="co-activity-dot" aria-hidden="true"/><div><a href={e.href}>{eventNames[e.kind]||e.kind}</a><small>{date(e.happened_at)}{e.actor&&` · ${e.actor}`}</small></div></li>)}</ol>:<p className="co-quiet">Noch keine Arbeitsschritte erfasst. Entwicklung und Textarbeit werden hier sichtbar.</p>}</section>
  </aside></div>
 </section>;
}

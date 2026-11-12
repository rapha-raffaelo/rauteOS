import React,{useEffect,useState} from 'react';
import {AssetOverview} from './AssetOverview.jsx';
import {SocialMonitoring} from './SocialMonitoring.jsx';
import {ClientOverview} from './ClientOverview.jsx';
import {AskRaute} from './AskRaute.jsx';
import {ClientsPage} from './ClientsPage.jsx';
import {PageHeading} from './PageHeading.jsx';
const activityLabels={idea_developed:'Idee entwickelt',activated:'Opportunity aktiviert',choices_saved:'Auswahl gespeichert',text_created:'Text erstellt',text_checked:'Aussagen geprüft',text_edited:'Text bearbeitet'};
const date=v=>v?new Date(v).toLocaleDateString('de-DE'):'–';
function Summary({row}){return <p>Profil: {row.twin.percent} % · Quartal: {row.actions_quarter.total} geliefert{row.promised_quarter!==null?` / ${row.promised_quarter} zugesagt`:' · Zusage offen'} · {row.opportunities} Opportunities</p>;}
function Texts({items}){return <div className="workbench-list">{items.length?items.map(t=><article key={`${t.type}-${t.id}`}><span>{t.client} · {t.format_name||t.format} · {t.released_at?'Freigegeben':'Entwurf'}</span><h2><a href={t.href}>{t.title||'Ohne Titel'}</a></h2><p>{date(t.generated_at)}</p></article>):<p>Noch keine Texte.</p>}</div>;}
export function WorkbenchPage({page,clientId}){
 const [data,setData]=useState(null),[error,setError]=useState('');
 useEffect(()=>{if(page==='assets'||page==='ask'||page==='monitoring_kpis')return;let live=true;fetch(`/api/v1/workbench/${clientId?`clients/${clientId}${page==='monitoring_social'?'/monitoring/social':''}`:page}`).then(r=>{if(!r.ok)throw Error('Ansicht konnte nicht geladen werden.');return r.json();}).then(v=>{if(live)setData(v);}).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[page,clientId]);
 if(page==='ask')return <AskRaute/>;
 if(page==='monitoring_kpis')return <section><PageHeading eyebrow="Monitoring" title="KPIs" description="Dieser Bereich ist noch offen. Kennzahlen werden später ergänzt."/></section>;
 if(page==='assets')return <AssetOverview/>;
 if(error)return <p role="alert">{error} <a href={window.location.href}>Erneut laden</a></p>;
 if(!data)return <p role="status">Ansicht wird geladen…</p>;
 if(page==='clients')return <ClientsPage clients={data.clients}/>;
 if(page==='monitoring_social')return <SocialMonitoring data={data} clientId={clientId}/>;
 if(page==='overview')return <ClientOverview data={data} clientId={clientId}/>;
 return <section><h1>{data.client.name} · {page==='actions'?'Actions':'Overview'}</h1>{data.summary&&<Summary row={data.summary}/>}
  <><p>Freigegebene Texte und Berichte sowie extern erfasste Leistungen. Entwürfe zählen nicht als Lieferung. Je Liste werden höchstens {data.limit} Einträge gezeigt; die Quartalszahl umfasst alle Leistungen.</p><h2>Aktivitätsverlauf</h2><p>Entwicklung, Aktivierung und Entwürfe sind Arbeitsschritte. Sie erhöhen die Lieferzahl erst durch eine Freigabe oder eine separat erfasste Leistung.</p>{data.activity?.length?<ol>{data.activity.map(event=><li key={event.id}><a href={event.href}>{activityLabels[event.kind]||event.kind}</a> · {date(event.happened_at)} · {event.actor}{event.title&&` · ${event.title}`}{event.selected_journalists>0&&` · ${event.selected_journalists} Journalisten ausgewählt`}</li>)}</ol>:<p>Noch keine Aktivität erfasst.</p>}<h2>Freigegebene Texte</h2><Texts items={data.released_texts}/><h2>Freigegebene Berichte</h2>{data.released_reports.map(r=><p key={r.id}>{date(r.happened_at)} · {r.title}</p>)}<h2>Extern erfasste Leistungen</h2>{data.logged_actions.map(r=><article key={r.id}><h3>{r.title}</h3><p>{date(r.happened_at)} · {r.note}</p></article>)}<a href="/desk">Leistung im Desk erfassen</a></>
 </section>;
}

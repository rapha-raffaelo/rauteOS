import React from 'react';
import {PageHeading} from './PageHeading.jsx';
import './communication.css';
export function SocialMonitoring({data,clientId}){
 return <section className="social-monitoring"><PageHeading eyebrow={data.client.name} title="Social Media" description="Veröffentlichte Beiträge dieses Mandats."/>
  <div className="co-panel"><header className="co-panel-head"><h2>LinkedIn · erfasste Veröffentlichungen</h2><a href={`/linkedin?client=${clientId}`}>Beiträge verwalten →</a></header>
   <p className="social-monitoring-note">Hier stehen als veröffentlicht erfasste LinkedIn-Beiträge. Reichweite, Interaktionen und Erwähnungen werden bisher nicht automatisch gemessen.</p>
   {data.posts.length?data.posts.map(post=><article className="co-news-item" key={post.id}><small>{post.author||'LinkedIn'} · zuletzt gepflegt am {new Date(post.recorded_at).toLocaleDateString('de-DE')}</small><h3>{/^https?:\/\//i.test(post.url)?<a href={post.url} target="_blank" rel="noreferrer">{post.title} ↗</a>:post.title}</h3>{!post.url&&<p>Veröffentlichungslink noch nicht hinterlegt.</p>}</article>):<p className="social-monitoring-note">Für diesen Kunden sind noch keine veröffentlichten Social-Media-Beiträge erfasst.</p>}
   {data.posts.length>=data.limit&&<p className="social-monitoring-note">Die neuesten {data.limit} Einträge werden angezeigt.</p>}
  </div>
 </section>;
}

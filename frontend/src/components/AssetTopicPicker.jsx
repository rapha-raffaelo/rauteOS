import React,{useId,useState} from 'react';
import './AssetTopicPicker.css';

const recipientFormats=new Set(['pitch','interviewangebot','interview_briefing']);

export function useAssetTopics({scope,format,contact='',topics,defaultTopicId}){
 const [drafts,setDrafts]=useState({});
 const key=JSON.stringify([scope,format,recipientFormats.has(format)?String(contact||''):'']);
 const available=new Set(topics.map(topic=>Number(topic.id)));
 const selected=(drafts[key]??(defaultTopicId?[Number(defaultTopicId)]:[])).filter(id=>available.has(id));
 function toggle(id){
  const next=selected.includes(id)?selected.filter(value=>value!==id):[...selected,id];
  setDrafts(previous=>({...previous,[key]:next}));
 }
 return [selected,toggle];
}

export function AssetTopicPicker({topics,selected,onToggle,disabled=false}){
 const hintId=useId();
 return <fieldset className="asset-topic-picker" disabled={disabled} aria-describedby={hintId}>
  <legend>Themen für dieses Asset</legend>
  <p id={hintId}>{selected.length?`${selected.length} ${selected.length===1?'Thema ausgewählt':'Themen ausgewählt'}. Du kannst weitere Themen hinzufügen.`:'Wähle mindestens ein Thema aus.'}</p>
  <div className="asset-topic-tiles">{topics.map(topic=><label key={topic.id} className={`asset-topic-tile${selected.includes(Number(topic.id))?' asset-topic-tile--selected':''}`}>
   <input type="checkbox" disabled={disabled} aria-label={topic.title} checked={selected.includes(Number(topic.id))} onChange={()=>onToggle(Number(topic.id))}/>
   <span><strong>{topic.title}</strong>{topic.summary&&<small>{topic.summary}</small>}</span>
  </label>)}</div>
  {!topics.length&&<p>Noch kein aktives Thema verfügbar. Aktiviere zuerst ein Thema unter Themen.</p>}
 </fieldset>;
}

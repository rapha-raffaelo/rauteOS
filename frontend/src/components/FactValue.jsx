import React from 'react';
const missing = /^(?:bitte ergänzen|noch zu ergänzen|nicht (?:öffentlich )?(?:veröffentlicht|verfügbar|bekannt|angegeben)|keine (?:öffentlichen |belegten )?angaben(?: vorhanden)?|unbekannt)[.!]?$/i;
export function factParts(text='') {
 return text.split(/\n|;\s*/).map(line=>{
  line=line.replace(/^\s*[•*\-]\s+/, '');
  const colon=line.indexOf(':');
  const label=colon>=0?line.slice(0,colon+1):'';
  const value=(colon>=0?line.slice(colon+1):line).trim();
  return {label,value,missing:missing.test(value)};
 });
}
export const hasMissingFact = text => !text?.trim() || factParts(text).some(p=>p.missing);
export function FactValue({text}) {
 const parts=factParts(text);
 if(/^\s*[•*\-]\s+/m.test(text||''))return <ul className="fact-bullets">{parts.map((p,i)=><li key={i}>{p.label&&`${p.label} `}{p.missing?<em>bitte ergänzen</em>:p.value}</li>)}</ul>;
 return parts.map((p,i)=><React.Fragment key={i}>{i>0&&<br/>}{p.label&&`${p.label} `}{p.missing?<em>bitte ergänzen</em>:p.value}</React.Fragment>);
}

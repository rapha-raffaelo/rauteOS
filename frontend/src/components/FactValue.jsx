import React from 'react';
const missing = /^(?:bitte ergänzen|noch zu ergänzen|nicht (?:öffentlich )?(?:veröffentlicht|verfügbar|bekannt|angegeben)|keine (?:öffentlichen |belegten )?angaben(?: vorhanden)?|unbekannt)[.!]?$/i;
// A sentence that reports a gap ("Zu Umsatz gibt es keine öffentlichen
// Angaben.") is an open field, not a fact; newspulse.fact_values.open_lines
// does the same when an answer is stored. This catches answers stored before.
const absent=/(?:^|[^\p{L}])(?:keine (?:öffentlich(?:en|e)? |belegten |belastbaren |weiteren )?(?:angaben|informationen|daten|zahlen)|nicht (?:öffentlich )?(?:bekannt|veröffentlicht|verfügbar|angegeben)|unbekannt)(?![\p{L}])/iu;
const topics=[['Mitarbeitende',/mitarbeit|beschäftigt|personal/i],['Umsatz',/umsatz|erlös/i]];
function openLines(line){
 const bare=line.replace(/^\s*[•*\-]\s+/, '');
 if(!absent.test(bare)||missing.test(bare.split(':').slice(-1)[0].trim()))return [line];
 const kept=[],gaps=[];
 for(const sentence of bare.trim().split(/(?<=[.!?])\s+(?=[A-ZÄÖÜ])/)){
  if(!absent.test(sentence)){kept.push(sentence);continue;}
  const named=topics.filter(([,p])=>p.test(sentence)).map(([label])=>`${label}: bitte ergänzen`);
  gaps.push(...(named.length?named:['bitte ergänzen']));
 }
 return [...(kept.length?[kept.join(' ')]:[]),...new Set(gaps)];
}
export function factParts(text='') {
 return text.split(/\n|;\s*/).flatMap(openLines).map(line=>{
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

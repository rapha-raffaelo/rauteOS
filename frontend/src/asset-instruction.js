import {useEffect,useState} from 'react';

const recipientFormats=new Set(['pitch','interviewangebot','interview_briefing']);
const draftKey=(scope,format,contact)=>JSON.stringify([scope,format,recipientFormats.has(format)?String(contact||''):'']);

// An unfinished extra prompt belongs to one prospective asset, not the whole
// workspace. The accepted request stores its instruction in the server's run.
export function useAssetInstruction({scope,format,contact='',initialInstruction='',initialContact=''}){
 const [drafts,setDrafts]=useState({});
 const key=draftKey(scope,format,contact);
 const seedContact=String(initialContact||'');
 const seeded=format==='pitch'&&(!seedContact||String(contact||'')===seedContact);
 // Explicit master-pitch/follow-up changes target the pitch they came from.
 // Unchanged props on polling must not refill a submitted or edited prompt.
 useEffect(()=>{
  if(initialInstruction)setDrafts(previous=>({...previous,[draftKey(scope,'pitch',seedContact)]:initialInstruction}));
 },[scope,initialInstruction,seedContact]);
 const value=drafts[key]??(seeded?initialInstruction:'');
 const setValue=value=>setDrafts(previous=>({...previous,[key]:value}));
 return [value,setValue,()=>setValue('')];
}

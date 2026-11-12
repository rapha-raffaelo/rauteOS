import {journalistRequest as request} from '../../journalists-api.js';

// What the Gmail page has already seen, so a folder, a client tab or a mail
// opened before shows at once and is brought up to date behind it. Lists live
// for this tab in sessionStorage (gone when the tab closes); whole mails only
// in memory. Nothing here leaves the browser.
const LISTS='gm.lists.v1',MAX_LISTS=24;
const lists=new Map(),threads=new Map(),pending=new Map();
let loaded=false;

function storage(){try{return window.sessionStorage;}catch{return null;}}
function hydrate(){if(loaded)return;loaded=true;
 try{const raw=storage()?.getItem(LISTS);if(raw)for(const [k,v] of JSON.parse(raw))lists.set(k,v);}catch{/* a full or blocked storage is no error */}}
function persist(){try{storage()?.setItem(LISTS,JSON.stringify([...lists].slice(-MAX_LISTS)));}catch{/* see above */}}

export function cachedList(key){hydrate();return lists.get(key)||null;}
export function rememberList(key,value){hydrate();lists.delete(key);lists.set(key,value);while(lists.size>MAX_LISTS)lists.delete(lists.keys().next().value);persist();}
export function forgetLists(){lists.clear();persist();}

export function cachedStatus(){try{return JSON.parse(storage()?.getItem('gm.status.v1')||'null');}catch{return null;}}
export function rememberStatus(value){try{storage()?.setItem('gm.status.v1',JSON.stringify(value));}catch{/* see above */}}

// One mail, read once per change: the list's historyId says whether the copy
// held is still the mail Gmail has.
export function cachedThread(id,history){const held=threads.get(id);return held&&(!history||held.history===history)?held.messages:null;}
export function loadThread(id,history=''){
 const held=cachedThread(id,history);if(held)return Promise.resolve(held);
 const key=`${id}@${history}`;if(pending.has(key))return pending.get(key);
 const job=request(`mailbox/threads/${encodeURIComponent(id)}${history?`?h=${encodeURIComponent(history)}`:''}`)
  .then(v=>{threads.set(id,{history,messages:v.messages});if(threads.size>60)threads.delete(threads.keys().next().value);return v.messages;})
  .finally(()=>pending.delete(key));
 pending.set(key,job);return job;
}
export function prefetchThread(id,history){loadThread(id,history).catch(()=>{});}
export function forgetThreads(ids){ids.forEach(id=>threads.delete(id));}

// The test page shares the real questionnaire UI but never calls customer APIs.
export function createDemoApi(initial) {
  const key = 'raute-onboarding-demo-v2';
  let state = structuredClone(initial);
  try { const saved = JSON.parse(sessionStorage.getItem(key)); if (saved) state = {...state, ...saved}; } catch {}
  async function audioStore(action, id, value) {
    return new Promise((resolve,reject)=>{
      const open=indexedDB.open('raute-onboarding-demo-audio',1);
      open.onupgradeneeded=()=>open.result.createObjectStore('audio');
      open.onerror=()=>reject(new Error('Lokaler Audiospeicher ist nicht verfügbar.'));
      open.onsuccess=()=>{const db=open.result,tx=db.transaction('audio',action==='get'?'readonly':'readwrite'),store=tx.objectStore('audio');
        const request=action==='put'?store.put(value,id):action==='delete'?store.delete(id):store.get(id);
        tx.oncomplete=()=>{db.close();resolve(request.result);};tx.onerror=()=>{db.close();reject(new Error('Audio konnte lokal nicht gespeichert werden.'));};};
    });
  }
  const api = async (path = '', method = 'GET', body = {}) => {
    let answer;
    if(path.startsWith('/audio/')) {
      const url=new URL(path,'https://demo.local');
      const parts=url.pathname.split('/');
      if(method==='DELETE') {
        await audioStore('delete',parts[2]);
        let answer=null;
        for(const [id,a] of Object.entries(state.answers))if(a.audio_id===parts[2]){
          if(a.value){answer={value:a.value,skipped:false};state.answers[id]=answer;}else delete state.answers[id];
        }
        state.completed=false;sessionStorage.setItem(key,JSON.stringify(state));
        return {answer};
      }
      if(method==='POST') {
        if(url.searchParams.get('mode')!=='audio')throw new Error('KI-Transkription ist nur über einen persönlichen Kundenlink verfügbar.');
        const id=crypto.randomUUID().replaceAll('-','');
        const metadata={id,question_key:parts[2],mode:'audio',filename:url.searchParams.get('filename')||'Aufnahme',status:'local',transcript:'',retained:true,transcription_configured:false,size:body.size};
        await audioStore('put',id,{metadata,blob:body});
        const ids=JSON.parse(sessionStorage.getItem(key+'-audio')||'[]');sessionStorage.setItem(key+'-audio',JSON.stringify([...ids,id]));
        return metadata;
      }
      const stored=await audioStore('get',parts[2]);
      if(!stored)throw new Error('Demo-Audio nicht mehr verfügbar. Bitte erneut aufnehmen.');
      return parts[3]==='content'?stored.blob:stored.metadata;
    }
    if (path.startsWith('/answers/')) {
      const id = path.slice('/answers/'.length);
      if (!state.questions.some(q => q.key === id)) throw new Error('Unbekannte Frage');
      answer = {value: body.value || '', skipped: !!body.skipped, ...(body.audio_id?{audio_id:body.audio_id,mode:body.mode}:{})};
      state.answers = {...state.answers, [id]: answer};
    } else if (path === '/prefill') {
      state.prefill_confirmed = true;
      state.prefill = state.prefill.map(p => ({...p, ...(body.corrections?.[p.key] ? {customer_value: body.corrections[p.key]} : {})}));
    } else if (path === '/complete') state.completed = true;
    if (method !== 'GET') {
      try { sessionStorage.setItem(key, JSON.stringify(state)); } catch {}
    }
    return structuredClone(answer || state);
  };
  api.reset = async () => { state = structuredClone(initial); try {const ids=JSON.parse(sessionStorage.getItem(key+'-audio')||'[]');await Promise.all(ids.map(id=>audioStore('delete',id)));sessionStorage.removeItem(key+'-audio');sessionStorage.removeItem(key);} catch {} };
  return api;
}

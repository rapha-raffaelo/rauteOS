import React, {useEffect, useRef, useState} from 'react';

const MAX_BYTES = 25 * 1024 * 1024;
const icons = {
  record: <circle cx="12" cy="12" r="6" fill="currentColor"/>,
  play: <path d="m8 5 11 7-11 7z" fill="currentColor"/>,
  pause: <><path d="M8 5v14M16 5v14" stroke="currentColor" strokeWidth="4"/></>,
  stop: <rect x="6" y="6" width="12" height="12" rx="1" fill="currentColor"/>,
  upload: <><path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5" fill="none" stroke="currentColor" strokeWidth="1.7"/></>,
};
function IconButton({icon, label, ...props}) {
  return <button type="button" className="onb-audio-icon" aria-label={label} title={label} {...props}><svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">{icons[icon]}</svg></button>;
}

export function OnboardingAudio({questionKey, token, demoApi, state = {}, saved, configured, onChange, onText, onActivity, children}) {
  const [recording, setRecording] = useState('idle'), [playing, setPlaying] = useState(false);
  const [seconds, setSeconds] = useState(0), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [url, setUrl] = useState('');
  const recorder = useRef(null), stream = useRef(null), player = useRef(null), fileInput = useRef(null);
  const alive = useRef(true), chunks = useRef([]), current = useRef(state), change = useRef(onChange), text = useRef(onText);
  current.current = state; change.current = onChange; text.current = onText;
  const mode = state.mode || saved?.mode || 'transcript';
  const uploaded = state.uploaded;
  const pending = uploaded && ['queued', 'processing'].includes(uploaded.status);
  const supportsRecording = !!(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);
  async function api(path, method='GET', body) {
    if (demoApi) return demoApi(path, method, body);
    const response = await fetch('/api/onboarding' + path, {method, credentials:'omit',
      headers:{'X-Onboarding-Token':token, ...(body instanceof Blob ? {'Content-Type':body.type || 'application/octet-stream'} : {})}, body});
    if (!response.ok) {const d=await response.json().catch(()=>({}));throw new Error(d.detail || 'Audio konnte nicht verarbeitet werden. Bitte erneut versuchen.');}
    return path.endsWith('/content') ? response.blob() : response.json();
  }
  useEffect(()=>{alive.current=true;return()=>{alive.current=false; if(recorder.current?.state!=='inactive') recorder.current?.stop();stream.current?.getTracks().forEach(t=>t.stop());};},[]);
  useEffect(()=>{onActivity(recording!=='idle'||busy);return()=>onActivity(false);},[recording,busy]);
  useEffect(()=>{if(!state.blob){setUrl('');return;}const u=URL.createObjectURL(state.blob);setUrl(u);return()=>URL.revokeObjectURL(u);},[state.blob]);
  useEffect(()=>{if(recording!=='recording')return;const timer=setInterval(()=>setSeconds(v=>{if(v>=299){recorder.current?.stop();return 300;}return v+1;}),1000);return()=>clearInterval(timer);},[recording]);
  // Load previously submitted audio, including after returning to this question.
  useEffect(()=>{
    let active=true;
    if(saved?.audio_id && !Object.hasOwn(state,'uploaded')){
      api('/audio/'+saved.audio_id).then(async m=>{
        let blob; if(m.retained)blob=await api('/audio/'+m.id+'/content');
        if(active && !Object.hasOwn(current.current,'uploaded'))change.current({...current.current,mode:m.mode,uploaded:m,blob,delivered:true,name:m.filename});
      }).catch(e=>{if(active)setError(e.message);});
    }
    return()=>{active=false;};
  },[saved?.audio_id]);
  useEffect(()=>{
    if(!pending)return;let active=true,timer;
    async function poll(){
      try{const m=await api('/audio/'+uploaded.id);if(!active)return;
        const latest=current.current;
        change.current({...latest,uploaded:m,delivered:latest.delivered||m.status==='ready'});
        if(m.status==='ready' && m.mode==='transcript' && !latest.delivered)text.current(m.transcript,m);
        if(['queued','processing'].includes(m.status))timer=setTimeout(poll,2000);
      }catch(e){if(active){setError(e.message);timer=setTimeout(poll,5000);}}
    }
    timer=setTimeout(poll,1000);return()=>{active=false;clearTimeout(timer);};
  },[uploaded?.id,!!pending]);
  function selectBlob(blob,name){
    if(blob.size>MAX_BYTES){setError('Maximal 25 MB pro Datei.');return;}
    if(!blob.size){setError('Die Aufnahme ist leer. Bitte erneut versuchen.');return;}
    player.current?.pause();setPlaying(false);setError('');
    change.current({mode,blob,name,uploaded:null,delivered:false});
  }
  async function record(){
    if(busy||recording!=='idle')return;
    setBusy(true);setError('');
    try{
      const s=await navigator.mediaDevices.getUserMedia({audio:true});
      if(!alive.current){s.getTracks().forEach(t=>t.stop());return;}
      stream.current=s;player.current?.pause();setPlaying(false);
      const mime=['audio/webm;codecs=opus','audio/mp4','audio/ogg;codecs=opus'].find(t=>MediaRecorder.isTypeSupported(t));
      const r=new MediaRecorder(s,mime?{mimeType:mime}:undefined);recorder.current=r;chunks.current=[];
      r.ondataavailable=e=>{if(e.data.size)chunks.current.push(e.data);};
      r.onerror=()=>{if(alive.current){setError('Aufnahme unterbrochen. Bitte erneut versuchen.');setRecording('idle');}s.getTracks().forEach(t=>t.stop());};
      r.onstop=()=>{s.getTracks().forEach(t=>t.stop());if(!alive.current)return;selectBlob(new Blob(chunks.current,{type:r.mimeType||mime||'audio/webm'}),'Aufnahme');setRecording('idle');};
      r.start(1000);setSeconds(0);setRecording('recording');
    }catch{setError('Mikrofon nicht verfügbar. Bitte Zugriff erlauben oder eine Datei hochladen.');}
    finally{if(alive.current)setBusy(false);}
  }
  function pause(){
    if(recording==='recording'){recorder.current.pause();setRecording('paused');}
    else{player.current?.pause();setPlaying(false);}
  }
  async function play(){
    if(recording==='paused'){recorder.current.resume();setRecording('recording');return;}
    try{await player.current.play();setPlaying(true);}catch{setError('Diese Datei kann hier nicht abgespielt werden. Sie können sie trotzdem hochladen.');}
  }
  function stop(){
    if(recording!=='idle'){recorder.current?.stop();}
    else{player.current?.pause();if(player.current)player.current.currentTime=0;setPlaying(false);}
  }
  async function upload(){
    if(!state.blob||busy)return;setBusy(true);setError('');
    try{const m=await api('/audio/'+questionKey+'?mode='+mode+'&filename='+encodeURIComponent(state.name||'Audio'),'POST',state.blob);
      if(!alive.current)return;change.current({...current.current,uploaded:m,delivered:false});
      if(m.status==='ready'&&mode==='transcript'){text.current(m.transcript,m);change.current({...current.current,uploaded:m,delivered:true});}
    }catch(e){if(alive.current)setError(e.message);}finally{if(alive.current)setBusy(false);}
  }
  async function retry(){setError('');try{const m=await api('/audio/'+uploaded.id+'/retry','POST');change.current({...current.current,uploaded:m});}catch(e){setError(e.message);}}
  return <div className="onb-audio">
    <div className="onb-audio-mode" role="group" aria-label="Speichern als">{['transcript','audio'].map(m=><button key={m} type="button" aria-pressed={mode===m} disabled={busy||recording!=='idle'||!!pending} onClick={()=>{setError('');change.current({...state,mode:m,uploaded:null,delivered:false});}}>{m==='transcript'?'Transkript':'Audio'}</button>)}</div>
    {children}
    <div className="onb-audio-toolbar">
      <IconButton icon="record" label="Aufnahme starten" disabled={!supportsRecording||busy||recording!=='idle'||!!pending} onClick={record}/>
      <IconButton icon="play" label={recording==='paused'?'Aufnahme fortsetzen':'Audio abspielen'} disabled={busy||(recording!=='paused'&&(!url||recording!=='idle'||playing))} onClick={play}/>
      <IconButton icon="pause" label={recording==='recording'?'Aufnahme pausieren':'Wiedergabe pausieren'} disabled={busy||(recording!=='recording'&&!playing)} onClick={pause}/>
      <IconButton icon="stop" label="Stopp" disabled={busy||(recording==='idle'&&!url)} onClick={stop}/>
      <IconButton icon="upload" label="Audiodatei auswählen" disabled={busy||recording!=='idle'||!!pending} onClick={()=>fileInput.current.click()}/>
      {recording!=='idle'&&<span role="status" className="onb-audio-timer">{Math.floor(seconds/60)}:{String(seconds%60).padStart(2,'0')}{recording==='paused'?' · Pause':''}</span>}
    </div>
    <input ref={fileInput} className="onb-sr-only" type="file" accept="audio/*,.m4a,.mp3,.wav,.ogg,.webm,.flac" aria-label="Audiodatei hochladen" onChange={e=>{if(e.target.files[0])selectBlob(e.target.files[0],e.target.files[0].name);e.target.value='';}}/>
    <audio ref={player} src={url||undefined} onEnded={()=>setPlaying(false)}/>
    <p className="onb-note">{mode==='audio'?'Original speichern · KI-Transkript zusätzlich': 'Nur Text speichern · Audio danach löschen'}{demoApi?' · Demo: nur lokal':' · Verarbeitung durch Deepgram'}</p>
    {state.blob&&<p className="onb-audio-file">{state.name||'Aufnahme'} · {state.blob.size < 1024*1024 ? Math.max(1,Math.round(state.blob.size/1024))+' KB' : (state.blob.size/1024/1024).toFixed(1)+' MB'}</p>}
    {state.blob&&!uploaded&&<button type="button" className="onb-audio-submit" disabled={busy||recording!=='idle'||(mode==='transcript'&&(!configured||!!demoApi))} onClick={upload}>{busy?'Wird übertragen …':mode==='audio'?'Audio übernehmen':'Transkript erstellen'}</button>}
    {mode==='transcript'&&state.blob&&(!configured||demoApi)&&<p className="onb-note">{demoApi?'KI-Transkription über einen persönlichen Kundenlink testen.':'Transkription wird eingerichtet. Audio kann bereits gespeichert werden.'}</p>}
    {uploaded&&<p role="status" className="onb-note">{uploaded.status==='ready'?'Transkript bereit':uploaded.status==='local'?'Audio lokal übernommen':uploaded.status==='failed'||uploaded.status==='expired'?uploaded.note:uploaded.transcription_configured?'KI erstellt das Transkript …':'Audio gespeichert · Transkription wartet auf Einrichtung'}</p>}
    {uploaded?.status==='failed'&&<button type="button" onClick={retry}>Erneut transkribieren</button>}
    {error&&<p role="alert" className="onb-error">{error}</p>}
  </div>;
}

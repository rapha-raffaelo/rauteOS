import {useCallback,useRef,useState} from 'react';

function olderRun(incoming,current){
 if(!current?.id)return false;
 if(!incoming?.id||incoming.id<current.id)return true;
 return incoming.id===current.id&&current.status!=='running'&&incoming.status==='running';
}

// Requests can finish out of order. Keep the accepted run authoritative even
// before React paints it, so a late poll cannot replace it with an older run.
export function useAssetRunData(scope){
 const current=useRef({scope,data:null});
 const [state,setState]=useState(current.current);
 if(current.current.scope!==scope)current.current={scope,data:null};
 const setData=useCallback(value=>{
  if(current.current.scope!==scope)return false;
  const data=typeof value==='function'?value(current.current.data):value;
  current.current={scope,data};setState(current.current);return true;
 },[scope]);
 const acceptRead=useCallback(value=>{
  if(current.current.scope!==scope||olderRun(value?.latest,current.current.data?.latest))return false;
  return setData(value);
 },[scope,setData]);
 return [state.scope===scope?state.data:null,setData,acceptRead];
}

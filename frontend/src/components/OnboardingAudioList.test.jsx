import React from 'react';
import {render,screen,fireEvent,cleanup,within} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {OnboardingAudioList} from './OnboardingAudioList.jsx';
afterEach(()=>{cleanup();vi.restoreAllMocks();});
const item={id:'abc',question_key:'Q01.02',question:'Welche Ziele haben Sie?',filename:'Interview.wav',retained:true,status:'ready',transcript:'Unser Ziel.',review:''};
it('edits a transcript and archives only after submitting the answer',async()=>{
  global.fetch=vi.fn(async(path,options)=>({ok:true,json:async()=>options?.method==='POST'?{...item,review:'archiviert',answer:JSON.parse(options.body).value}:[item]}));
  render(<OnboardingAudioList clientId={16}/>);
  expect(await screen.findByRole('heading',{name:item.question})).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Als Antwort übernehmen'}));
  const field=screen.getByRole('textbox');
  expect(field.value).toBe('Unser Ziel.');
  fireEvent.change(field,{target:{value:'Geprüfte Antwort.'}});
  expect(fetch.mock.calls.filter(([,o])=>o?.method==='POST')).toHaveLength(0);
  fireEvent.click(screen.getByRole('button',{name:'Antwort absenden'}));
  expect(await screen.findByText('Kundenarchiv (1)')).toBeTruthy();
  expect(screen.getByText('Geprüfte Antwort.')).toBeTruthy();
  expect(screen.queryByRole('textbox')).toBeNull();
  expect(screen.getByText('Keine offenen Audioaufnahmen.')).toBeTruthy();
});
it('opens a blank field and preserves edits when submission fails',async()=>{
  global.fetch=vi.fn(async(path,options)=>({ok:options?.method!=='POST',json:async()=>options?.method==='POST'?{detail:'Speichern fehlgeschlagen'}:[item]}));
  render(<OnboardingAudioList clientId={16}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Leeres Antwortfeld öffnen'}));
  expect(screen.getByRole('textbox').value).toBe('');
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'Eingefügte Antwort'}});
  fireEvent.click(screen.getByRole('button',{name:'Antwort absenden'}));
  expect(await screen.findByRole('alert')).toBeTruthy();
  expect(screen.getByRole('textbox').value).toBe('Eingefügte Antwort');
  expect(screen.getByText('Kundenarchiv (0)')).toBeTruthy();
});
it('deletes an audio from the customer list',async()=>{
  global.fetch=vi.fn(async(path,options)=>({ok:true,json:async()=>options?.method==='DELETE'?{ok:true}:[item]}));
  render(<OnboardingAudioList clientId={16}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Audioaufnahme löschen'}));
  expect(await screen.findByText('Keine offenen Audioaufnahmen.')).toBeTruthy();
  expect(fetch.mock.calls.some(([p,o])=>p==='/client/16/onboarding-audio/abc'&&o.method==='DELETE')).toBe(true);
});
it('does not restore an archived recording from an older pending poll',async()=>{
 let finishPoll, gets=0;
 const realTimeout=globalThis.setTimeout;
 // Trigger the periodic refresh quickly without affecting Testing Library waits.
 vi.spyOn(globalThis,'setTimeout').mockImplementation((fn,ms,...args)=>realTimeout(fn,ms===5000?20:ms,...args));
 global.fetch=vi.fn(async(path,options)=>{
  if(options?.method==='POST')return {ok:true,json:async()=>({...item,review:'archiviert',answer:'Unser Ziel.'})};
  gets++;
  if(gets===1)return {ok:true,json:async()=>[item]};
  return new Promise(resolve=>{finishPoll=()=>resolve({ok:true,json:async()=>[item]});});
 });
 render(<OnboardingAudioList clientId={16}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Als Antwort übernehmen'}));
 await new Promise(resolve=>realTimeout(resolve,50));
 expect(finishPoll).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'Antwort absenden'}));
 await screen.findByText('Kundenarchiv (1)');
 finishPoll();
 await new Promise(resolve=>realTimeout(resolve,10));
 expect(screen.getByText('Kundenarchiv (1)')).toBeTruthy();
 expect(screen.getByText('Keine offenen Audioaufnahmen.')).toBeTruthy();
});
it('places recordings under their question and refreshes answers after archiving',async()=>{
 const onAnswered=vi.fn();
 global.fetch=vi.fn(async(path,options)=>({ok:true,json:async()=>options?.method==='POST'?{...item,review:'archiviert',answer:'Unser Ziel.'}:[item]}));
 render(<OnboardingAudioList clientId={16} onAnswered={onAnswered}>{({forQuestion,archive})=><><section aria-label="Frage 1">{forQuestion('Q01.01')}</section><section aria-label="Frage 2">{forQuestion('Q01.02')}</section>{archive}</>}</OnboardingAudioList>);
 const second=screen.getByRole('region',{name:'Frage 2'});
 expect(await within(second).findByText('Interview.wav')).toBeTruthy();
 expect(within(screen.getByRole('region',{name:'Frage 1'})).queryByText('Interview.wav')).toBeNull();
 fireEvent.click(within(second).getByRole('button',{name:'Als Antwort übernehmen'}));
 fireEvent.click(within(second).getByRole('button',{name:'Antwort absenden'}));
 await screen.findByText('Kundenarchiv (1)');
 expect(within(second).queryByText('Interview.wav')).toBeNull();
 expect(onAnswered).toHaveBeenCalledTimes(1);
});

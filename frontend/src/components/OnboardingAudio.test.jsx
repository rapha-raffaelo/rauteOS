import React, {useState} from 'react';
import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react';
import {afterEach,beforeEach,it,expect,vi} from 'vitest';
import {OnboardingAudio} from './OnboardingAudio.jsx';
let track, recorder;
function Harness({initial={}}){const [state,setState]=useState(initial);return <OnboardingAudio questionKey="B01.01" token="test" state={state} configured onChange={setState} onText={()=>{}} onActivity={()=>{}}/>;}
beforeEach(()=>{
  track={stop:vi.fn()};
  vi.stubGlobal('MediaRecorder',class {
    static isTypeSupported(){return true;}
    constructor(){recorder=this;this.state='inactive';this.mimeType='audio/webm';}
    start(){this.state='recording';}pause(){this.state='paused';}resume(){this.state='recording';}
    stop(){this.state='inactive';this.ondataavailable({data:new Blob(['recorded audio'],{type:'audio/webm'})});this.onstop();}
  });
  Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:{getUserMedia:vi.fn(async()=>({getTracks:()=>[track]}))}});
  URL.createObjectURL=vi.fn(()=> 'blob:recording');URL.revokeObjectURL=vi.fn();
  vi.spyOn(HTMLMediaElement.prototype,'pause').mockImplementation(()=>{});
  vi.spyOn(HTMLMediaElement.prototype,'play').mockResolvedValue();
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});
it('records, pauses, resumes and releases the microphone on stop',async()=>{
  render(<Harness/>);
  fireEvent.click(screen.getByRole('button',{name:'Aufnahme starten'}));
  fireEvent.click(await screen.findByRole('button',{name:'Aufnahme pausieren'}));
  expect(recorder.state).toBe('paused');
  fireEvent.click(screen.getByRole('button',{name:'Aufnahme fortsetzen'}));expect(recorder.state).toBe('recording');
  fireEvent.click(screen.getByRole('button',{name:'Stopp'}));
  expect(track.stop).toHaveBeenCalled();
  expect(await screen.findByRole('button',{name:'Transkript erstellen'})).toBeTruthy();
  expect(screen.getByRole('button',{name:'Audio abspielen'}).disabled).toBe(false);
});
it('retains a failed upload for retry and sends the scoped token',async()=>{
  global.fetch=vi.fn().mockResolvedValue({ok:false,json:async()=>({detail:'Upload fehlgeschlagen'})});
  render(<Harness initial={{mode:'audio',blob:new Blob(['audio']),name:'test.wav'}}/>);
  fireEvent.click(screen.getByRole('button',{name:'Audio übernehmen'}));
  expect((await screen.findByRole('alert')).textContent).toContain('Upload fehlgeschlagen');
  expect(screen.getByText(/test.wav/)).toBeTruthy();
  await waitFor(()=>expect(screen.getByRole('button',{name:'Audio übernehmen'}).disabled).toBe(false));
  expect(fetch.mock.calls[0][1].headers['X-Onboarding-Token']).toBe('test');
  expect(fetch.mock.calls[0][1].body).toBeInstanceOf(Blob);
});

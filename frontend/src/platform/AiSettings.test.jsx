import React from 'react';
import {render, screen, fireEvent, cleanup, waitFor} from '@testing-library/react';
import {afterEach, it, expect, vi} from 'vitest';
import {AiSettings} from './AiSettings.jsx';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const data={secret_ready:true,providers:[{key:'claude',label:'Claude',connected:true,model:'sonnet',models:['sonnet','opus'],how:'Claude-Abo'},{key:'gemini',label:'Gemini',connected:false,models:['gemini-test']}],roles:[{key:'designer',label:'Designer',description:'Schreibt Texte',order:['claude'],models:{claude:'opus'}}]};
it('saves role model and provider together and supports a custom model',()=>{
 render(<AiSettings data={data} roles/>);
 const form=screen.getByRole('button',{name:'Modelle und Reihenfolge speichern'}).closest('form');
 expect(new FormData(form).get('designer_model_1')).toBe('opus');
 fireEvent.change(screen.getByLabelText('Designer Modell 1'),{target:{value:'__custom'}});
 fireEvent.change(screen.getByLabelText('Designer Modell 1 – eigene Modell-ID'),{target:{value:'my-model'}});
 expect(new FormData(form).get('designer_model_1')).toBe('my-model');
 fireEvent.change(screen.getByLabelText('Designer Anbieter 1'),{target:{value:'gemini'}});
 expect(new FormData(form).get('designer_model_1')).toBe('');
});
it('shows testing and success inline, then handles failure on retry',async()=>{
 let resolve;
 const fetch=vi.fn(()=>new Promise(r=>resolve=r));vi.stubGlobal('fetch',fetch);
 render(<AiSettings data={data}/>);
 fireEvent.click(screen.getAllByRole('button',{name:'Verbindung testen'})[0]);
 expect(screen.getByRole('button',{name:'Wird getestet…'}).disabled).toBe(true);
 resolve({ok:true,json:async()=>({ok:true,message:'Claude antwortet',model:'sonnet',seconds:1.2})});
 await screen.findByText(/Claude antwortet/);
 expect(screen.getByText('sonnet · 1.2 s')).toBeTruthy();
 fetch.mockResolvedValueOnce({ok:false,json:async()=>({ok:false,message:'Anmeldung prüfen'})});
 fireEvent.click(screen.getAllByRole('button',{name:'Verbindung testen'})[0]);
 await screen.findByText(/Anmeldung prüfen/);
 expect(screen.queryByText('Geprüft')).toBeNull();
});
it('says Verbunden or Getrennt and shows what is left of each subscription or budget',()=>{
 const usage={secret_ready:true,roles:[],providers:[
  {key:'claude',label:'Claude',connected:true,models:[],usage:{kind:'windows',seen_at:'2026-11-12T08:00:00Z',
   windows:[{name:'5 Stunden',used_percent:20,resets_at:1794487200},{name:'7 Tage',used_percent:95,resets_at:1794571200}]}},
  {key:'openai',label:'OpenAI',connected:false,models:[],usage:{kind:'windows'}},
  {key:'gemini',label:'Gemini',connected:true,models:[],usage:{kind:'budget',month:'2026-11',calls:12,input_tokens:9000,output_tokens:1000,searches:4,billing_url:'https://aistudio.google.com/usage'}}]};
 render(<AiSettings data={usage}/>);
 expect(screen.getAllByText('Verbunden')).toHaveLength(2);
 expect(screen.getByText('Getrennt')).toBeTruthy();
 expect(screen.getByText('80 % frei')).toBeTruthy();
 expect(screen.getByText('5 % frei')).toBeTruthy();
 expect(screen.getByText('Verbrauch durch RauteOS im November')).toBeTruthy();
 expect(screen.getByText('10.000')).toBeTruthy();
 expect(screen.getByRole('link',{name:'Google AI Studio'}).getAttribute('href')).toBe('https://aistudio.google.com/usage');
});

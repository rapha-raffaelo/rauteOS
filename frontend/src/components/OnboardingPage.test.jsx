import React from 'react';
import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {OnboardingPage} from './OnboardingPage.jsx';
const questions=[{key:'A01.01',text:'Wie heißen Sie?',help:'Offizieller Name',section:'Unternehmen',choices:[]},{key:'B03.01',text:'Wohin geht es?',help:'Ihre Ziele',section:'Zukunft',choices:['Premium','Challenger']}];
const data={customer:'Testfirma',questions,answers:{},completed:false,prefill:[],prefill_confirmed:true};
const ok=d=>Promise.resolve({ok:true,json:async()=>d});
afterEach(()=>{cleanup();vi.restoreAllMocks();delete window.SpeechRecognition;localStorage.clear();});
it('retains failed answers and advances only after the database confirms saving',async()=>{
  global.fetch=vi.fn().mockImplementationOnce(()=>ok(data)).mockResolvedValueOnce({ok:false,json:async()=>({detail:'Offline. Bitte erneut versuchen.'})}).mockImplementationOnce(()=>ok({value:'Firma',skipped:false}));
  render(<OnboardingPage token="test"/>);
  fireEvent.click(await screen.findByText('Los geht’s'));
  fireEvent.change(screen.getByLabelText('Ihre Antwort'),{target:{value:'Firma'}});
  fireEvent.click(screen.getByText('Weiter'));
  expect((await screen.findByRole('alert')).textContent).toContain('Offline');
  expect(screen.getByLabelText('Ihre Antwort').value).toBe('Firma');
  fireEvent.click(screen.getByText('Weiter'));
  expect(await screen.findByText('Wohin geht es?')).toBeTruthy();
  expect(fetch.mock.calls[1][1].headers['X-Onboarding-Token']).toBe('test');
});
it('resumes saved answers, accepts tap choices and allows reviewing skipped answers',async()=>{
  global.fetch=vi.fn().mockImplementationOnce(()=>ok({...data,answers:{'A01.01':{value:'Firma',skipped:false}}})).mockImplementationOnce(()=>ok({value:'Premium',skipped:false}));
  render(<OnboardingPage token="test"/>);
  fireEvent.click(await screen.findByText('Weiter, wo ich war'));
  fireEvent.click(screen.getByText('Premium'));
  expect(screen.getByLabelText('Ihre Antwort').value).toBe('Premium');
  fireEvent.click(screen.getByText('Antworten ansehen'));
  expect(await screen.findByText('So klingt Ihr Unternehmen.')).toBeTruthy();
  expect(screen.getByText('Firma')).toBeTruthy();
});
it('shows sourced public prefills once and moves straight to the CEO questions after confirmation',async()=>{
  const prefill=[...Array.from({length:4},(_,i)=>({key:'extra'+i,label:'Angabe '+i,value:'Inhalt '+i})),{key:'A02.01',label:'Geschäftsfeld',value:'Public business',source_url:'https://example.org',source_title:'Website',researched_at:'2026-10-13T10:00:00Z'}];
  global.fetch=vi.fn().mockImplementationOnce(()=>ok({...data,prefill,prefill_confirmed:false})).mockImplementationOnce(()=>ok({ok:true}));
  render(<OnboardingPage token="test"/>);
  fireEvent.click(await screen.findByText('Los geht’s'));
  expect(screen.getByText('Public business')).toBeTruthy();
  expect(screen.queryByText('Website ↗')).toBeNull();
  expect(screen.getByText('Inhalt 3')).toBeTruthy();
  expect(document.querySelector('details')).toBeNull();
  fireEvent.click(screen.getByText('Angaben bearbeiten'));
  fireEvent.change(screen.getByLabelText('Geschäftsfeld'),{target:{value:'Corrected business'}});
  fireEvent.click(screen.getByText('Speichern & weiter'));
  expect(await screen.findByText('Wie heißen Sie?')).toBeTruthy();
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({corrections:{'A02.01':'Corrected business'}});
});

it.each(['', 'Mein noch ungespeicherter Entwurf'])('returns from question one to prefills and preserves draft %j', async value => {
  const {createDemoApi} = await import('../onboardingDemo.js');
  sessionStorage.clear();
  const demoApi = createDemoApi(data);
  render(<OnboardingPage demoApi={demoApi} />);
  fireEvent.click(await screen.findByText('Los geht’s'));
  fireEvent.change(screen.getByLabelText('Ihre Antwort'), {target: {value}});
  const back = screen.getByRole('button', {name: 'Zurück zu den Unternehmensangaben'});
  expect(back.disabled).toBe(false);
  fireEvent.click(back);
  expect(await screen.findByText('Das wissen wir schon.')).toBeTruthy();
  expect(screen.getByRole('button', {name: 'Angaben bearbeiten'})).toBeTruthy();
  fireEvent.click(screen.getByText('Stimmt, weiter'));
  expect(await screen.findByText('Wie heißen Sie?')).toBeTruthy();
  expect(screen.getByLabelText('Ihre Antwort').value).toBe(value);
});

it('retains a cleared answer when going back without requiring an answer or skipping the question', async () => {
  const {createDemoApi} = await import('../onboardingDemo.js');
  sessionStorage.clear();
  const demoApi = createDemoApi({...data, answers: {'A01.01': {value: 'Saved', skipped: false}}});
  render(<OnboardingPage demoApi={demoApi} />);
  fireEvent.click(await screen.findByText('Weiter, wo ich war'));
  fireEvent.change(screen.getByLabelText('Ihre Antwort'), {target: {value: 'Unfinished second answer'}});
  fireEvent.click(screen.getByRole('button', {name: 'Vorherige Frage'}));
  expect(screen.getByLabelText('Ihre Antwort').value).toBe('Saved');
  fireEvent.change(screen.getByLabelText('Ihre Antwort'), {target: {value: ''}});
  fireEvent.click(screen.getByRole('button', {name: 'Zurück zu den Unternehmensangaben'}));
  fireEvent.click(screen.getByText('Stimmt, weiter'));
  expect(await screen.findByText('Wie heißen Sie?')).toBeTruthy();
  expect(screen.getByLabelText('Ihre Antwort').value).toBe('');
  fireEvent.change(screen.getByLabelText('Ihre Antwort'), {target: {value: 'Updated'}});
  fireEvent.click(screen.getByText('Weiter'));
  await screen.findByText('Wohin geht es?');
  expect(screen.getByLabelText('Ihre Antwort').value).toBe('Unfinished second answer');
});

it('reads the protected token from links ending in a customer name',async()=>{
  window.location.hash='personal-token/example-ag';
  global.fetch=vi.fn().mockImplementation(()=>ok(data));
  render(<OnboardingPage/>);
  await screen.findByText('Los geht’s');
  expect(fetch.mock.calls[0][1].headers['X-Onboarding-Token']).toBe('personal-token');
  window.location.hash='';
});
it('shows each question with its explanation and lets the customer finish with open questions',async()=>{
  global.fetch=vi.fn().mockImplementationOnce(()=>ok(data)).mockImplementationOnce(()=>ok({value:'',skipped:true})).mockImplementationOnce(()=>ok({value:'',skipped:true})).mockImplementationOnce(()=>ok({ok:true}));
  render(<OnboardingPage token="test"/>);
  expect(await screen.findByText(/Dieser Fragebogen umfasst zu Beginn 22 Fragen/)).toBeTruthy();
  fireEvent.click(screen.getByText('Los geht’s'));
  expect(screen.getByText('Offizieller Name')).toBeTruthy();
  fireEvent.click(screen.getByText('Später beantworten'));
  expect(await screen.findByText('Ihre Ziele')).toBeTruthy();
  fireEvent.click(screen.getByText('Später beantworten'));
  expect(await screen.findByText(/0 Antworten gespeichert · 2 Fragen noch offen/)).toBeTruthy();
  fireEvent.click(screen.getByText('Abschließen'));
  expect(await screen.findByText(/Ihre 0 Antworten sind gespeichert/)).toBeTruthy();
});
it('switches questions, explanations, topic titles and labels to English and back',async()=>{
  const bilingual={...data,prefill_confirmed:false,
    questions:questions.map(q=>({...q,text_en:'EN '+q.text,help_en:'EN '+q.help})),
    prefill:[{key:'R01.01',label:'Unternehmensidentität',label_en:'Company identity',value:'Testfirma GmbH'}]};
  global.fetch=vi.fn().mockImplementationOnce(()=>ok(bilingual)).mockImplementationOnce(()=>ok({ok:true}));
  render(<OnboardingPage token="test"/>);
  fireEvent.click(await screen.findByRole('button',{name:'EN'}));
  expect(screen.getByText('Let’s start')).toBeTruthy();
  fireEvent.click(screen.getByText('Let’s start'));
  expect(screen.getByText('Company identity')).toBeTruthy();
  fireEvent.click(screen.getByText('Correct, continue'));
  expect(await screen.findByText('EN Wie heißen Sie?')).toBeTruthy();
  expect(screen.getByText('EN Offizieller Name')).toBeTruthy();
  expect(screen.getByLabelText('Your answer')).toBeTruthy();
  expect(screen.getByRole('button',{name:'Start recording'})).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'DE'}));
  expect(screen.getByText('Wie heißen Sie?')).toBeTruthy();
  expect(screen.getByText('Später beantworten')).toBeTruthy();
});
it('corrects one topic in place and shows research bold text without asterisks',async()=>{
  const prefill=[{key:'R05.01',label:'Unternehmensbeschreibung',value:'Ein **Reservierungsmanagement** für Restaurants.'},
    {key:'R06.01',label:'Produkte',value:'Reserve, Pay und Promote.'}];
  global.fetch=vi.fn().mockImplementationOnce(()=>ok({...data,prefill,prefill_confirmed:false})).mockImplementationOnce(()=>ok({ok:true}));
  render(<OnboardingPage token="test"/>);
  fireEvent.click(await screen.findByText('Los geht’s'));
  expect(screen.getByText('Reservierungsmanagement').tagName).toBe('STRONG');
  expect(screen.queryByText(/\*\*/)).toBeNull();
  fireEvent.click(screen.getAllByRole('button',{name:'Korrigieren'})[1]);
  expect(screen.queryByLabelText('Unternehmensbeschreibung')).toBeNull();
  fireEvent.change(screen.getByLabelText('Produkte'),{target:{value:'Reserve und Pay.'}});
  fireEvent.click(screen.getByText('Speichern & weiter'));
  expect(await screen.findByText('Wie heißen Sie?')).toBeTruthy();
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({corrections:{'R06.01':'Reserve und Pay.'}});
});

describe('prefill gist', () => {
  it('shows the first sentences and never ends one on a date or an abbreviation', async () => {
    const { gist } = await import('./OnboardingPage.jsx');
    const text = 'Der offizielle Firmenname ist Zenchef SAS, die Software heißt ZenchefOS. Das Unternehmen wurde am 4. November 2010 unter dem Namen 1001Menus gegründet. Der Hauptsitz liegt in der 63 Avenue de Villiers, 75017 Paris. Zenchef ist in der Gastronomie-Software tätig.';
    const short = gist(text);
    expect(short).toBe('Der offizielle Firmenname ist Zenchef SAS, die Software heißt ZenchefOS. Das Unternehmen wurde am 4. November 2010 unter dem Namen 1001Menus gegründet.');
    expect(short.length).toBeLessThanOrEqual(180);
    expect(gist('Kurz und gut.')).toBe('Kurz und gut.');
  });
});
it('shows customer identity prominently and saves customer answers without an extra confirmation',async()=>{
 global.fetch=vi.fn().mockImplementationOnce(()=>ok({...data,logo_url:'/static/logos/client.png'})).mockImplementationOnce(()=>ok({value:'Firma',skipped:false}));
 render(<OnboardingPage token="test"/>);
 expect(await screen.findByText('Testfirma')).toBeTruthy();
 expect(document.querySelector('.onb-customer-identity img').getAttribute('src')).toBe('/static/logos/client.png');
 fireEvent.click(screen.getByText('Los geht’s'));
 expect(screen.queryByRole('button',{name:'Antwort bestätigen'})).toBeNull();
 fireEvent.change(screen.getByLabelText('Ihre Antwort'),{target:{value:'Firma'}});
 fireEvent.click(screen.getByText('Weiter'));
 expect(await screen.findByText('Wohin geht es?')).toBeTruthy();
});
it('saves a corrected topic with an icon and shows no confirmation ticks',async()=>{
 const prefill=[{key:'R03.01',label:'Unternehmensgröße',value:'20 Mitarbeitende',source_url:'https://example.org'}];
 global.fetch=vi.fn().mockImplementationOnce(()=>ok({...data,prefill,prefill_confirmed:false})).mockImplementationOnce(()=>ok({ok:true}));
 render(<OnboardingPage token="test"/>);
 fireEvent.click(await screen.findByText('Los geht’s'));
 expect(screen.queryByRole('button',{name:/Bestätigen:/})).toBeNull();
 expect(screen.queryByRole('button',{name:'Speichern: Unternehmensgröße'})).toBeNull();
 fireEvent.click(screen.getByText('Korrigieren'));
 fireEvent.change(screen.getByRole('textbox',{name:'Unternehmensgröße'}),{target:{value:'25 Mitarbeitende'}});
 fireEvent.click(screen.getByRole('button',{name:'Speichern: Unternehmensgröße'}));
 await waitFor(()=>expect(screen.queryByRole('textbox',{name:'Unternehmensgröße'})).toBeNull());
 expect(screen.getByText('25 Mitarbeitende')).toBeTruthy();
 expect(JSON.parse(global.fetch.mock.calls[1][1].body)).toEqual({corrections:{'R03.01':'25 Mitarbeitende'},confirmed_keys:['R03.01']});
});

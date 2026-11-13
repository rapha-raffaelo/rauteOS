import React from 'react';
import {render,screen,fireEvent,cleanup,waitFor,within} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {MailboxPage} from './MailboxPage.jsx';
import {SignatureEditor} from './mail/SignatureEditor.jsx';
import {forgetLists} from './mail/cache.js';
afterEach(()=>{cleanup();vi.unstubAllGlobals();sessionStorage.clear();forgetLists();});
const json=body=>({ok:true,headers:{get:()=>'application/json'},json:async()=>body});
const STATUS={connected:true,email:'raphael@raute-kopf.com',may_send:true,may_manage:true,drive:true,signature:'<b>Raphael</b>',clients:[{id:1,name:'Remexian'}]};
const THREAD={id:'t1',subject:'Statement',sender:'Lena',snippet:'Danke',date:'2026-11-12T09:00:00Z',count:2,unread:true,starred:false,labels:['INBOX'],
 attachments:[{name:'Briefing.pdf',mime:'application/pdf',size:2048,part_id:'2',message_id:'m1'}]};
const MESSAGE={id:'m1',sender:'Lena',sender_email:'lena@remexian.com',to:'raphael@raute-kopf.com',cc:'',date:'2026-11-12T09:00:00Z',subject:'Statement',
 body:'Passt so.',html:'<p>Passt <b>so</b>.</p>',message_id_header:'<id@x>',references:'<id@x>',unread:true,snippet:'Passt so.',
 attachments:[{name:'Briefing.pdf',mime:'application/pdf',size:2048,part_id:'2',message_id:'m1'}]};

function mailbox(extra={}){
 const calls=[];
 vi.stubGlobal('fetch',vi.fn(async(url,options={})=>{calls.push({url,method:options.method||'GET',body:options.body});
  for(const [key,value] of Object.entries(extra))if(url.includes(key))return json(typeof value==='function'?value(options):value);
  if(url.endsWith('/api/v1/mailbox'))return json(STATUS);
  if(url.includes('/mailbox/threads?'))return json({threads:[THREAD],next_page_token:'',total:1496,unread_inbox:12});
  if(url.includes('/mailbox/threads/modify'))return json({changed:1});
  if(url.includes('/mailbox/threads/t1'))return json({messages:[MESSAGE]});
  if(url.includes('/mailbox/assets'))return json({folder:'7. Assets › Remexian',files:[{id:'f1',name:'Statement.pdf',mime:'application/pdf',size:2048}]});
  if(url.endsWith('/mailbox/send'))return json({message_id:'m9',thread_id:'t1'});
  if(url.endsWith('/mailbox/draft'))return json({draft_id:'d1'});
  return json({});}));
 return calls;
}
const sent=(calls,path)=>JSON.parse(calls.filter(c=>c.url.endsWith(path)).pop().body);

it('lays the inbox out as Gmail: client tabs, rows with chips and counts',async()=>{
 const calls=mailbox();
 render(<MailboxPage/>);
 const row=await screen.findByRole('button',{name:'Lena: Statement'});
 expect(within(row).getByText('Briefing.pdf')).toBeTruthy();
 expect(screen.getByText('1–1 von 1.496')).toBeTruthy();
 expect(screen.getByRole('button',{name:/Posteingang/}).textContent).toContain('12');
 fireEvent.click(screen.getByRole('tab',{name:'Remexian'}));
 await waitFor(()=>expect(calls.some(c=>c.url.includes('client=1'))).toBe(true));
 expect(screen.getByRole('tab',{name:'Remexian'}).getAttribute('aria-selected')).toBe('true');
});

it('archives from the row and undoes it from the notice',async()=>{
 const calls=mailbox();
 render(<MailboxPage/>);
 await screen.findByRole('button',{name:'Lena: Statement'});
 fireEvent.click(screen.getByRole('button',{name:'Archivieren'}));
 expect(await screen.findByText('Konversation archiviert.')).toBeTruthy();
 expect(screen.queryByRole('button',{name:'Lena: Statement'})).toBeNull();
 expect(sent(calls,'/threads/modify')).toEqual({ids:['t1'],action:'archive'});
 fireEvent.click(screen.getByRole('button',{name:'Rückgängig'}));
 await waitFor(()=>expect(sent(calls,'/threads/modify')).toEqual({ids:['t1'],action:'inbox'}));
});

it('opens a mail as Gmail does and replies with signature, quote and a Drive asset',async()=>{
 const calls=mailbox();
 render(<MailboxPage/>);
 fireEvent.click(await screen.findByRole('button',{name:'Lena: Statement'}));
 const frame=await screen.findByTitle('Inhalt der E-Mail');
 expect(frame.getAttribute('sandbox')).not.toContain('allow-scripts');
 expect(frame.getAttribute('srcdoc')).toContain('<p>Passt <b>so</b>.</p>');
 expect(screen.getByText('1 von 1.496')).toBeTruthy();
 await waitFor(()=>expect(calls.some(c=>c.url.endsWith('/threads/modify')&&JSON.parse(c.body).action==='read')).toBe(true));
 expect(screen.getByRole('link',{name:/Briefing.pdf/}).getAttribute('href')).toBe('/api/v1/mailbox/messages/m1/parts/2?download=1');
 fireEvent.click(screen.getAllByRole('button',{name:/^Antworten$/}).pop());
 const dialog=await screen.findByRole('dialog',{name:'Antworten'});
 const text=within(dialog).getByRole('textbox',{name:'Nachrichtentext'});
 expect(text.innerHTML).toContain('<b>Raphael</b>');
 expect(text.innerHTML).toContain('schrieb Lena');
 expect(within(dialog).getByRole('toolbar',{name:'Formatierung'})).toBeTruthy();
 fireEvent.click(within(dialog).getByRole('button',{name:'Kunden-Assets aus Drive'}));
 fireEvent.change(within(dialog).getByRole('combobox',{name:'Kunde'}),{target:{value:'1'}});
 fireEvent.click(await within(dialog).findByRole('checkbox',{name:/Statement.pdf/}));
 fireEvent.click(within(dialog).getByRole('button',{name:'Senden · 1 Anhang'}));
 await screen.findByText('Nachricht gesendet.');
 const body=sent(calls,'/mailbox/send');
 expect(body).toMatchObject({to:'lena@remexian.com',subject:'Re: Statement',thread_id:'t1',reply_to:'<id@x>',references:'<id@x>',drive_files:['f1']});
 expect(body.html).toContain('<b>Raphael</b>');
});

it('forwards with the original attachments and keeps a closed window as draft',async()=>{
 const calls=mailbox();
 render(<MailboxPage/>);
 fireEvent.click(await screen.findByRole('button',{name:'Lena: Statement'}));
 await screen.findByTitle('Inhalt der E-Mail');
 fireEvent.click(screen.getAllByRole('button',{name:/^Weiterleiten$/}).pop());
 const dialog=await screen.findByRole('dialog',{name:'Neue Nachricht'});
 expect(within(dialog).getByRole('list',{name:'Anhänge'}).textContent).toContain('Briefing.pdf');
 fireEvent.click(within(dialog).getByRole('button',{name:'Bcc'}));
 fireEvent.change(within(dialog).getByLabelText('Bcc'),{target:{value:'chef@raute-kopf.com'}});
 fireEvent.click(within(dialog).getByRole('button',{name:'Speichern und schließen'}));
 await screen.findByText('Entwurf gespeichert.');
 expect(sent(calls,'/mailbox/draft')).toMatchObject({subject:'Fwd: Statement',bcc:'chef@raute-kopf.com',forwarded:[{message_id:'m1',part_id:'2'}]});
});

it('hides the row actions and says why when the grant cannot manage',async()=>{
 vi.stubGlobal('fetch',vi.fn(async url=>json(url.endsWith('/api/v1/mailbox')?{...STATUS,may_manage:false}
  :{threads:[THREAD],next_page_token:'',total:1})));
 render(<MailboxPage/>);
 await screen.findByRole('button',{name:'Lena: Statement'});
 expect(screen.queryByRole('button',{name:'Archivieren'})).toBeNull();
 expect(screen.getByText(/brauchen einmal eine neue Verbindung/)).toBeTruthy();
});

it('asks to connect a mailbox when none is connected',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>json({connected:false,clients:[]})));
 render(<MailboxPage/>);
 expect((await screen.findByRole('link',{name:/Postfach in den Einstellungen verbinden/})).getAttribute('href')).toBe('/settings#gmail');
});

it('keeps a formatted signature from Settings',async()=>{
 const calls=[];
 vi.stubGlobal('fetch',vi.fn(async(url,options={})=>{calls.push({url,method:options.method||'GET',body:options.body});
  return json({html:options.method==='PUT'?JSON.parse(options.body).html:'<i>Alt</i>'});}));
 render(<SignatureEditor/>);
 const text=await screen.findByRole('textbox',{name:'Signatur'});
 expect(text.innerHTML).toBe('<i>Alt</i>');
 text.innerHTML='<b>Raphael Mankopf</b><br>raute+kopf';
 fireEvent.click(screen.getByRole('button',{name:'Signatur speichern'}));
 await screen.findByText('Gespeichert.');
 expect(JSON.parse(calls.find(c=>c.method==='PUT').body).html).toBe('<b>Raphael Mankopf</b><br>raute+kopf');
});

it('does not show a previous mailbox before the current session loads',async()=>{
 mailbox();
 const first=render(<MailboxPage/>);
 await screen.findByRole('button',{name:'Lena: Statement'});
 first.unmount();
 let answer;
 vi.stubGlobal('fetch',vi.fn(url=>url.endsWith('/api/v1/mailbox')?Promise.resolve(json(STATUS)):new Promise(r=>{answer=r;})));
 render(<MailboxPage/>);
 await waitFor(()=>expect(answer).toBeTruthy());
 expect(screen.queryByRole('button',{name:'Lena: Statement'})).toBeNull();
 answer(json({threads:[{...THREAD,id:'t2',subject:'Neu'}],next_page_token:'',total:2}));
 expect(await screen.findByRole('button',{name:'Lena: Neu'})).toBeTruthy();
});

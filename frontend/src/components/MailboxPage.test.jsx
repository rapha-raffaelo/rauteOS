import React from 'react';
import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {MailboxPage} from './MailboxPage.jsx';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const json=body=>({ok:true,headers:{get:()=>'application/json'},json:async()=>body});

it('filters by client, reads a thread and replies with a Drive asset',async()=>{
 const calls=[];
 vi.stubGlobal('fetch',vi.fn(async(url,options={})=>{calls.push({url,method:options.method||'GET',body:options.body});
  if(url.endsWith('/api/v1/mailbox'))return json({connected:true,email:'raphael@raute-kopf.com',may_send:true,drive:true,clients:[{id:1,name:'Remexian'}]});
  if(url.includes('/mailbox/threads?'))return json({threads:[{id:'t1',subject:'Statement',sender:'Lena',snippet:'Danke',date:'2026-11-12T09:00:00Z',count:2,unread:true}],next_page_token:''});
  if(url.includes('/mailbox/threads/t1'))return json({messages:[{id:'m1',sender:'Lena',sender_email:'lena@remexian.com',to:'raphael@raute-kopf.com',cc:'',
   date:'2026-11-12T09:00:00Z',subject:'Statement',body:'Passt so.',message_id_header:'<id@x>',attachments:[]}]});
  if(url.includes('/mailbox/assets'))return json({folder:'7. Assets › Remexian',files:[{id:'f1',name:'Statement.pdf',mime:'application/pdf',size:2048}]});
  if(url.endsWith('/mailbox/send'))return json({message_id:'m9',thread_id:'t1'});
  return json({});}));
 render(<MailboxPage/>);
 fireEvent.click(await screen.findByRole('button',{name:'Remexian'}));
 await waitFor(()=>expect(calls.some(c=>c.url.includes('client=1'))).toBe(true));
 fireEvent.click(await screen.findByRole('button',{name:/Statement/}));
 expect(await screen.findByText('Passt so.')).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'Antworten'}));
 fireEvent.click(await screen.findByRole('checkbox',{name:/Statement.pdf/}));
 fireEvent.click(screen.getByRole('button',{name:'Senden · 1 Anhang'}));
 await screen.findByText('E-Mail gesendet.');
 expect(JSON.parse(calls.find(c=>c.url.endsWith('/mailbox/send')).body)).toMatchObject({to:'lena@remexian.com',subject:'Re: Statement',
  thread_id:'t1',reply_to:'<id@x>',drive_files:['f1']});
});

it('asks to connect a mailbox when none is connected',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>json({connected:false,clients:[]})));
 render(<MailboxPage/>);
 expect((await screen.findByRole('link',{name:/Postfach in den Einstellungen verbinden/})).getAttribute('href')).toBe('/settings#gmail');
});

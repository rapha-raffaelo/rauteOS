import React,{useState} from 'react';
import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {Subtasks} from './Subtasks.jsx';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
function Harness(){const [rows,setRows]=useState([]);return <form onSubmit={e=>{e.preventDefault();throw Error('Parent submitted');}}><Subtasks task={{id:1,subtasks:rows}} onChange={setRows}/></form>;}
it('adds with Enter without submitting the parent and updates completion',async()=>{
 const fetch=vi.fn().mockResolvedValueOnce({ok:true,json:async()=>({subtasks:[{id:7,title:'Instagram',completed:false}]})}).mockResolvedValueOnce({ok:true,json:async()=>({subtasks:[{id:7,title:'Instagram',completed:true}]})});vi.stubGlobal('fetch',fetch);
 render(<Harness/>);
 fireEvent.change(screen.getByLabelText('Neue Unteraufgabe'),{target:{value:'Instagram'}});
 fireEvent.keyDown(screen.getByLabelText('Neue Unteraufgabe'),{key:'Enter'});
 await screen.findByLabelText('Instagram erledigt');
 expect(screen.getByLabelText('Neue Unteraufgabe').value).toBe('');
 fireEvent.click(screen.getByLabelText('Instagram erledigt'));
 await waitFor(()=>expect(screen.getByLabelText('Instagram erledigt').checked).toBe(true));
 expect(screen.getByText('☑ 1/1 Unteraufgaben')).toBeTruthy();
 expect(fetch.mock.calls[1][1].body.get('completed')).toBe('1');
});
it('keeps entered text when saving fails',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockRejectedValue(Error('Offline')));render(<Harness/>);
 fireEvent.change(screen.getByLabelText('Neue Unteraufgabe'),{target:{value:'Facebook'}});
 fireEvent.click(screen.getByText('+ Hinzufügen'));
 await screen.findByRole('alert');expect(screen.getByLabelText('Neue Unteraufgabe').value).toBe('Facebook');
});

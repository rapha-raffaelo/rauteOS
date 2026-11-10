import React from 'react';
import {render,screen,within,cleanup,fireEvent} from '@testing-library/react';
import {afterEach,expect,it} from 'vitest';
import {TasksPage} from './TaskManager.jsx';
afterEach(()=>{cleanup();window.history.replaceState(null,'','/aufgaben');});
const today=new Date().toLocaleDateString('en-CA');
const base={team:[{key:'raphael',name:'Raphael'},{key:'lucas',name:'Lucas'}],me:'lucas',
  clients:[{id:1,name:'Qonto'}],priorities:[['hoch','Hoch'],['mittel','Mittel'],['niedrig','Niedrig']],decisions:[],
  tasks:[
    {id:1,title:'Pitch Qonto',status:'offen',priority:'hoch',due_on:today,assignees:['lucas'],client:{id:1,name:'Qonto'},note:'',context_href:''},
    {id:2,title:'Medienliste',status:'offen',priority:'mittel',due_on:null,assignees:['raphael'],client:null,note:'',context_href:''},
    {id:3,title:'Alt',status:'erledigt',priority:'mittel',due_on:null,assignees:[],client:null,note:'',context_href:''}]};

it('defaults to four columns and creates a task in the selected status',()=>{
  render(<TasksPage data={base}/>);
  for(const name of ['Offen','In Bearbeitung','Review','Erledigt']) expect(screen.getByRole('region',{name})).toBeTruthy();
  fireEvent.click(within(screen.getByRole('region',{name:'Review'})).getByRole('button',{name:/Aufgabe hinzufügen/}));
  const form=screen.getByLabelText('Aufgabe hinzufügen').closest('form');
  expect(new FormData(form).get('status')).toBe('review');
  fireEvent.click(within(form).getByLabelText('@Lucas'));
  expect(new FormData(form).getAll('assignees')).toEqual(['lucas']);
});
it('supports both internal and client tasks from the same creation form',()=>{
  render(<TasksPage data={base}/>);
  fireEvent.click(screen.getByRole('button',{name:'+ Neue Aufgabe'}));
  const form=screen.getByLabelText('Aufgabe hinzufügen').closest('form');
  expect(new FormData(form).get('client_id')).toBe('');
  fireEvent.change(within(form).getByLabelText('Bereich'),{target:{value:'kunde'}});
  fireEvent.change(within(form).getByLabelText('Kunde auswählen'),{target:{value:'1'}});
  expect(new FormData(form).get('client_id')).toBe('1');
  fireEvent.change(within(form).getByLabelText('Bereich'),{target:{value:'intern'}});
  expect(new FormData(form).get('client_id')).toBe('');
});
it('filters by customer and preserves its default in inline creation',()=>{
  window.history.replaceState(null,'','/aufgaben?liste=kunde%3A1');
  render(<TasksPage data={base}/>);
  expect(screen.getByText('Pitch Qonto')).toBeTruthy();
  expect(screen.queryByText('Medienliste')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'+ Neue Aufgabe'}));
  expect(new FormData(screen.getByLabelText('Aufgabe hinzufügen').closest('form')).get('client_id')).toBe('1');
  expect(screen.queryByText('Mir zugewiesen')).toBeNull();
});
it('provides an accessible status form and search across the board',()=>{
  render(<TasksPage data={base}/>);
  const move=screen.getByLabelText('Status: Pitch Qonto').closest('form');
  fireEvent.change(screen.getByLabelText('Status: Pitch Qonto'),{target:{value:'review'}});
  expect(new FormData(move).get('status')).toBe('review');
  expect(new FormData(move).get('redirect_to')).toBe('/aufgaben');
  fireEvent.change(screen.getByLabelText('Aufgaben suchen'),{target:{value:'Medienliste'}});
  expect(screen.queryByText('Pitch Qonto')).toBeNull();
  expect(screen.getByText('Medienliste')).toBeTruthy();
});
it('retains list mode and edits assignments and review status in the drawer',()=>{
  window.history.replaceState(null,'','/aufgaben?ansicht=liste&aufgabe=2');
  render(<TasksPage data={base}/>);
  expect(screen.queryByRole('region',{name:'Review'})).toBeNull();
  const detail=screen.getByRole('complementary',{name:'Aufgabe bearbeiten'});
  expect(within(detail).getByLabelText('@Raphael').checked).toBe(true);
  expect(within(detail).getByLabelText('@Lucas').checked).toBe(false);
  fireEvent.change(within(detail).getByLabelText('Status'),{target:{value:'review'}});
  expect(new FormData(within(detail).getByRole('button',{name:'Speichern'}).closest('form')).get('status')).toBe('review');
});

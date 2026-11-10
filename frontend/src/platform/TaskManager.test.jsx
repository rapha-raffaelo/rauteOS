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
it('shows a list of open tasks with client, people and a quick add that lands in the list',()=>{
  window.history.replaceState(null,'','/aufgaben?liste=kunde%3A1');
  render(<TasksPage data={base}/>);
  expect(screen.getByRole('heading',{name:'Qonto'})).toBeTruthy();
  expect(screen.getByText('Pitch Qonto')).toBeTruthy();
  expect(screen.queryByText('Medienliste')).toBeNull();
  const add=screen.getByLabelText('Aufgabe hinzufügen').closest('form');
  expect(new FormData(add).get('client_id')).toBe('1');
  expect(new FormData(add).get('redirect_to')).toBe('/aufgaben?liste=kunde%3A1');
});
it('counts each list and opens the details with tags for every team member',()=>{
  window.history.replaceState(null,'','/aufgaben?aufgabe=2');
  render(<TasksPage data={base}/>);
  const lists=screen.getByRole('navigation',{name:'Listen'});
  expect(within(lists).queryByRole('link',{name:/Mir zugewiesen/})).toBeNull();
  expect(within(lists).getByRole('link',{name:/Intern/}).textContent).toContain('1');
  const details=screen.getByRole('complementary',{name:'Aufgabe bearbeiten'});
  expect(within(details).getByLabelText('@Raphael').checked).toBe(true);
  expect(within(details).getByLabelText('@Lucas').checked).toBe(false);
  expect(within(details).getByText('Einem Kunden zugeordnet, erscheint die Aufgabe auch auf seinem Dashboard.')).toBeTruthy();
});

it('keeps board navigation and posts only status when moving a task',()=>{
  window.history.replaceState(null,'','/aufgaben?ansicht=board');
  render(<TasksPage data={base}/>);
  expect(screen.getByRole('region',{name:'Erledigt'})).toBeTruthy();
  const move=screen.getByLabelText('Status: Pitch Qonto').closest('form');
  fireEvent.change(screen.getByLabelText('Status: Pitch Qonto'),{target:{value:'in_arbeit'}});
  expect(new FormData(move).get('status')).toBe('in_arbeit');
  expect(new FormData(move).get('redirect_to')).toBe('/aufgaben?ansicht=board');
  expect(screen.getByText('Alt')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Aufgaben suchen'),{target:{value:'Medienliste'}});
  expect(screen.queryByText('Pitch Qonto')).toBeNull();
  expect(screen.getByText('Medienliste')).toBeTruthy();
});
it('assigns new tasks to me by default and supports both team members',()=>{
  window.history.replaceState(null,'','/aufgaben?liste=mir');
  render(<TasksPage data={base}/>);
  const form=screen.getByLabelText('Aufgabe hinzufügen').closest('form');
  expect(new FormData(form).getAll('assignees')).toEqual(['lucas']);
  fireEvent.click(within(form).getByLabelText('@Raphael'));
  expect(new FormData(form).getAll('assignees')).toEqual(['raphael','lucas']);
});

it('combines client and internal tasks and offers client assignment at creation',()=>{
  render(<TasksPage data={base}/>);
  expect(screen.getByText('Pitch Qonto')).toBeTruthy();
  expect(screen.getByText('Medienliste')).toBeTruthy();
  const form=screen.getByLabelText('Aufgabe hinzufügen').closest('form');
  fireEvent.change(within(form).getByLabelText('Bereich'),{target:{value:'kunde'}});
  fireEvent.change(within(form).getByLabelText('Kunde auswählen'),{target:{value:'1'}});
  expect(new FormData(form).get('client_id')).toBe('1');
  expect(within(form).getByRole('button',{name:'Aufgabe erstellen'})).toBeTruthy();
  fireEvent.change(within(form).getByLabelText('Bereich'),{target:{value:'intern'}});
  expect(new FormData(form).get('client_id')).toBe('');
  expect(within(form).queryByLabelText('Kunde auswählen')).toBeNull();
  const lists=screen.getByRole('navigation',{name:'Listen'});
  expect(within(lists).queryByText('Mir zugewiesen')).toBeNull();
  expect(within(lists).getByText('Raphael')).toBeTruthy();
  expect(within(lists).getByText('Lucas')).toBeTruthy();
});

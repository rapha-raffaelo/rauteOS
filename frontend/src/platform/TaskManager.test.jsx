import React from 'react';
import {render,screen,within,cleanup} from '@testing-library/react';
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
  expect(within(lists).getByRole('link',{name:/Mir zugewiesen/}).textContent).toContain('1');
  expect(within(lists).getByRole('link',{name:/Intern/}).textContent).toContain('1');
  const details=screen.getByRole('complementary',{name:'Aufgabe bearbeiten'});
  expect(within(details).getByLabelText('@Raphael').checked).toBe(true);
  expect(within(details).getByLabelText('@Lucas').checked).toBe(false);
  expect(within(details).getByText('Einem Kunden zugeordnet, erscheint die Aufgabe auch auf seinem Dashboard.')).toBeTruthy();
});

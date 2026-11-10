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

it('combines person, area and customer filters and keeps them in task links',()=>{
  render(<TasksPage data={base}/>);
  fireEvent.change(screen.getByLabelText('Person filtern'),{target:{value:'lucas'}});
  fireEvent.change(screen.getByLabelText('Bereich filtern'),{target:{value:'kunde'}});
  fireEvent.change(screen.getByLabelText('Kunde filtern'),{target:{value:'1'}});
  expect(screen.getByText('Pitch Qonto')).toBeTruthy();
  expect(screen.queryByText('Medienliste')).toBeNull();
  const link=screen.getByRole('link',{name:'Pitch Qonto'});
  expect(link.getAttribute('href')).toContain('person=lucas');
  expect(link.getAttribute('href')).toContain('kunde=1');
  expect(window.location.search).toContain('bereich=kunde');
  fireEvent.change(screen.getByLabelText('Bereich filtern'),{target:{value:'intern'}});
  expect(screen.getByLabelText('Kunde filtern').disabled).toBe(true);
  expect(window.location.search).not.toContain('kunde=1');
  fireEvent.click(screen.getByRole('button',{name:'Filter zurücksetzen'}));
  expect(screen.getByText('Medienliste')).toBeTruthy();
  expect(screen.getByText('Pitch Qonto')).toBeTruthy();
});
it('selects an inclusive calendar range and a single day and preserves dates in navigation',()=>{
  window.history.replaceState(null,'','/aufgaben?von=2026-11-10&bis=2026-11-10');
  const data={...base,tasks:[
    {...base.tasks[0],due_on:'2026-11-10'},
    {...base.tasks[1],due_on:'2026-11-12'},
    {...base.tasks[2],due_on:'2026-11-13'}
  ]};
  render(<TasksPage data={data}/>);
  fireEvent.click(screen.getByRole('button',{name:/10.11.2026/}));
  fireEvent.click(screen.getByRole('button',{name:'Zeitraum'}));
  fireEvent.click(screen.getByRole('button',{name:'2026-11-10'}));
  fireEvent.click(screen.getByRole('button',{name:'2026-11-12'}));
  fireEvent.click(screen.getByRole('button',{name:'Anwenden'}));
  expect(screen.getByText('Pitch Qonto')).toBeTruthy();
  expect(screen.getByText('Medienliste')).toBeTruthy();
  expect(screen.queryByText('Alt')).toBeNull();
  expect(screen.getByRole('link',{name:'Liste'}).getAttribute('href')).toContain('bis=2026-11-12');
  fireEvent.click(screen.getByRole('button',{name:/10.11.2026/}));
  fireEvent.click(screen.getByRole('button',{name:'Einzelner Tag'}));
  fireEvent.click(screen.getByRole('button',{name:'2026-11-12'}));
  fireEvent.click(screen.getByRole('button',{name:'Anwenden'}));
  expect(screen.queryByText('Pitch Qonto')).toBeNull();
  expect(screen.getByText('Medienliste')).toBeTruthy();
  expect(window.location.search).toContain('von=2026-11-12');
  fireEvent.click(screen.getByRole('button',{name:/12.11.2026/}));
  fireEvent.click(screen.getByRole('button',{name:'Alle Termine'}));
  expect(screen.getByText('Alt')).toBeTruthy();
});
it('offers a top-right view switch and all creation statuses',()=>{
  render(<TasksPage data={base}/>);
  const views=screen.getByRole('navigation',{name:'Ansicht'});
  expect(within(views).getByRole('link',{name:'Liste'})).toBeTruthy();
  expect(within(views).getByRole('link',{name:'Kanban'}).getAttribute('aria-current')).toBe('page');
  fireEvent.click(screen.getByRole('button',{name:'+ Neue Aufgabe'}));
  const status=screen.getByLabelText('Status der neuen Aufgabe');
  expect([...status.options].map(option=>option.value)).toEqual(['offen','in_arbeit','review','erledigt']);
  fireEvent.change(status,{target:{value:'review'}});
  expect(new FormData(status.closest('form')).get('status')).toBe('review');
});
it('renders task information in a table in list view',()=>{
  window.history.replaceState(null,'','/aufgaben?ansicht=liste');
  render(<TasksPage data={base}/>);
  const table=screen.getByRole('table');
  for(const name of ['Aufgabe','Status','Zuständig','Fälligkeit','Bereich','Priorität']) {
    expect(within(table).getByRole('columnheader',{name})).toBeTruthy();
  }
  expect(within(table).getByRole('link',{name:'Pitch Qonto'})).toBeTruthy();
  expect(within(table).getByText('@Lucas')).toBeTruthy();
});

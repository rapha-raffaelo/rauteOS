import React from 'react';
import {render,screen,fireEvent,cleanup,within} from '@testing-library/react';
import {afterEach,it,expect} from 'vitest';
import {WorkspaceTabs} from './WorkspaceTabs.jsx';
afterEach(()=>{cleanup();localStorage.clear();});
const props={boards:[{id:1,name:'Allgemein',open_count:0},{id:2,name:'rauteOS',open_count:2}],activeId:1,href:id=>`/aufgaben?board=${id}`,person:'raphael'};
const names=()=>within(screen.getByRole('navigation')).getAllByRole('link').map(a=>a.textContent);
it('reorders tabs with buttons and persists after remount',()=>{
 const {unmount}=render(<WorkspaceTabs {...props}/>);
 fireEvent.click(screen.getByText('Reiter anordnen'));
 fireEvent.click(screen.getByRole('button',{name:'rauteOS nach links'}));
 expect(names()[1]).toContain('rauteOS');
 unmount();render(<WorkspaceTabs {...props}/>);
 expect(names()[1]).toContain('rauteOS');
 expect(screen.getByRole('link',{name:/Allgemein/}).getAttribute('aria-current')).toBe('page');
});
it('supports dragging and appends new workspaces without losing the saved order',()=>{
 const {rerender}=render(<WorkspaceTabs {...props}/>);
 fireEvent.click(screen.getByText('Reiter anordnen'));
 const source=screen.getByRole('link',{name:/rauteOS/}).parentElement;
 const target=screen.getByRole('link',{name:/Alle Aufgaben/}).parentElement;
 fireEvent.dragStart(source,{dataTransfer:{setData(){}}});fireEvent.dragOver(target);fireEvent.drop(target);
 expect(names()[0]).toContain('rauteOS');
 rerender(<WorkspaceTabs {...props} boards={[...props.boards,{id:3,name:'Neu',open_count:0}]}/>);
 expect(names()[0]).toContain('rauteOS');expect(names()[3]).toContain('Neu');
});

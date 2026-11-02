import React from 'react';
import { it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ClientOverview } from './ClientOverview.jsx';

it('dates each opportunity card, with the year only when it is not this one', () => {
 const year = new Date().getFullYear();
 const data = {client:{name:'Remexian'},summary:null,twin:null,texts:[],activity:[],opportunities:[
  {context_kind:'developed',context_id:1,title:'Bedrocan-Insolvenz',status:'draft',created_at:`${year}-11-02T09:00:00Z`},
  {context_kind:'detected',context_id:2,title:'G-BA',status:'active',created_at:'2024-03-05T09:00:00Z'}]};
 render(<ClientOverview data={data} clientId={9}/>);
 expect(screen.getByText('2. November').getAttribute('datetime')).toBe(`${year}-11-02T09:00:00Z`);
 expect(screen.getByText('5. März 2024')).toBeTruthy();
});

import React from 'react';
import {render, screen, cleanup, within} from '@testing-library/react';
import {it, expect, afterEach} from 'vitest';
import {ClientTabs} from './shell.jsx';
afterEach(cleanup);
it('groups the Themen and exposes AI visibility and KPIs',()=>{
 render(<ClientTabs path="/client/1/monitoring/kpis" data={{client:{id:1},active:'monitoring_kpis'}}/>);
 expect(screen.getByRole('link',{name:'Themen'}).getAttribute('href')).toBe('/client/1/themen');
 expect(screen.getByRole('link',{name:'Assets'}).getAttribute('href')).toBe('/client/1/assets');
 expect(screen.getByRole('link',{name:'Monitoring'}).getAttribute('aria-current')).toBe('page');
 expect(screen.getByRole('link',{name:'Monitoring'}).getAttribute('href')).toBe('/client/1/ki');
 expect(screen.queryByRole('link',{name:'News',exact:true})).toBeNull();
 expect(within(screen.getByRole('navigation',{name:'Ansicht'})).getAllByRole('link').map(a=>a.textContent)).toEqual(['KI-Sichtbarkeit','KPIs']);
 expect(screen.getByRole('link',{name:'KPIs'}).getAttribute('aria-current')).toBe('page');
 expect(screen.queryByRole('link',{name:'Heute'})).toBeNull();
});
it('keeps legacy impulse details within the Themen',()=>{
 render(<ClientTabs path="/client/1/advice" data={{client:{id:1},active:'texte'}}/>);
 expect(screen.getByRole('link',{name:'Themen'}).getAttribute('aria-current')).toBe('page');
});

it('places Medien, Themen and Assets between strategy and monitoring',()=>{
 render(<ClientTabs path="/client/1/medien" data={{client:{id:1},active:'media'}}/>);
 const links=within(screen.getByRole('navigation',{name:'Mandant'})).getAllByRole('link');
 expect(links.map(a=>a.textContent)).toEqual(['Überblick','Kundenprofil','Strategie','Medien','Themen','Assets','Monitoring']);
 expect(screen.getByRole('link',{name:'Medien'}).getAttribute('aria-current')).toBe('page');
 expect(screen.getByRole('link',{name:'Medien'}).getAttribute('href')).toBe('/client/1/medien');
});

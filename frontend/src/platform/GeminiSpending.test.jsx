import React from 'react';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {it,expect,vi,afterEach} from 'vitest';
import GeminiSpending from './GeminiSpending.jsx';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('shows setup instead of inventing a zero balance',()=>{
 render(<GeminiSpending initial={{state:'not_configured'}}/>);
 expect(screen.getByText('Billing-Export verbinden')).toBeTruthy();
 expect(screen.queryByText('0,00 €')).toBeNull();
 fireEvent.click(screen.getByText('BigQuery verbinden'));
 expect(screen.getByLabelText('Gemini-Projekt-ID')).toBeTruthy();
});
it('shows net spend, credits and source freshness from billing',async()=>{
 const config={table:'billing-project.dataset.table',project:'gemini-project',services:['ABC']};
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>({config,state:'ready',month:'2026-11',net:'10.00',gross:'12.00',credits:'-2.00',currency:'EUR',checked_at:'2026-11-12T10:00:00Z'})})));
 render(<GeminiSpending initial={{config,state:'pending'}}/>);
 await screen.findByText('10,00 €');
 expect(screen.getByText('-2,00 €')).toBeTruthy();
 expect(screen.getByText(/Abgerufen:/)).toBeTruthy();
});

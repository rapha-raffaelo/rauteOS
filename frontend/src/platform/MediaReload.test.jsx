import React from 'react';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {afterEach,it,expect} from 'vitest';
import {MediaReload} from './MediaReload.jsx';
afterEach(cleanup);
it('submits selected days and separate customer search preferences',()=>{
 render(<MediaReload data={{clients:[{id:1,name:'Alpha',active:true,keywords:['Solar']},{id:2,name:'Beta',active:true,keywords:[]}],run_active:false}}/>);
 fireEvent.click(screen.getByText(/Kunden auswählen/));
 fireEvent.click(screen.getByLabelText('Beta'));
 fireEvent.click(screen.getByText('Alpha · Suche anpassen'));
 fireEvent.click(screen.getByLabelText('Unternehmensname und Aliasse'));
 const form=screen.getByRole('button',{name:'Auswahl nachladen'}).closest('form');
 const payload=new FormData(form);
 expect(payload.getAll('days')).toHaveLength(1);
 expect(JSON.parse(payload.get('choices'))).toEqual([{id:1,company:false,keywords:['Solar']}]);
 fireEvent.click(screen.getByText('Auswahl leeren'));
 expect(screen.getByRole('button',{name:'Auswahl nachladen'}).disabled).toBe(true);
});

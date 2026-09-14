import React from 'react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {fireEvent,render,screen} from '@testing-library/react';
import {ClientActions} from './ClientActions.jsx';
const client={id:7,name:'Alpha'};
const settings={revision:'current',values:{name:'Alpha',industry:'Tech',country:'DE',aliases:'A',keywords:'',alert_topics:'',excluded_terms:'',required_terms:'',actions_per_quarter:''}};
const response=(body,status=200)=>({ok:status<400,status,headers:new Headers({'content-type':'application/json'}),json:async()=>body});
beforeEach(()=>{HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');};});
afterEach(()=>vi.unstubAllGlobals());
it('saves the selected client and refreshes only after success',async()=>{
 const fetch=vi.fn().mockResolvedValueOnce(response(settings)).mockResolvedValueOnce(response({id:7,name:'Updated'}));vi.stubGlobal('fetch',fetch);const changed=vi.fn();render(<ClientActions client={client} onChanged={changed}/>);
 fireEvent.click(screen.getByRole('button',{name:'Alpha bearbeiten'}));fireEvent.change(await screen.findByLabelText('Name'),{target:{value:'Updated'}});
 fireEvent.click(screen.getByRole('button',{name:'Änderungen speichern'}));await vi.waitFor(()=>expect(changed).toHaveBeenCalledOnce());
 expect(fetch.mock.calls[1][0]).toBe('/api/v1/workbench/clients/7/settings');expect(fetch.mock.calls[1][1].method).toBe('PUT');expect(JSON.parse(fetch.mock.calls[1][1].body)).toMatchObject({name:'Updated',aliases:'A',revision:'current'});
});
it('does not delete on opening or cancelling and confirms the selected name',async()=>{
 const fetch=vi.fn().mockResolvedValue(response({deleted:true}));vi.stubGlobal('fetch',fetch);const changed=vi.fn();render(<ClientActions client={client} onChanged={changed}/>);
 fireEvent.click(screen.getByRole('button',{name:'Alpha löschen'}));expect(fetch).not.toHaveBeenCalled();fireEvent.click(screen.getByRole('button',{name:'Abbrechen'}));expect(fetch).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'Alpha löschen'}));fireEvent.click(screen.getByRole('button',{name:'Mandant löschen'}));await vi.waitFor(()=>expect(changed).toHaveBeenCalledOnce());
 expect(fetch.mock.calls[0][0]).toBe('/api/v1/workbench/clients/7');expect(fetch.mock.calls[0][1].method).toBe('DELETE');expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({name:'Alpha'});
});
it('keeps edits and the dialog when saving fails',async()=>{
 const fetch=vi.fn().mockResolvedValueOnce(response(settings)).mockResolvedValueOnce(response({detail:'Name bereits vorhanden.'},422));vi.stubGlobal('fetch',fetch);const changed=vi.fn();render(<ClientActions client={client} onChanged={changed}/>);
 fireEvent.click(screen.getByRole('button',{name:'Alpha bearbeiten'}));fireEvent.change(await screen.findByLabelText('Name'),{target:{value:'Beta'}});fireEvent.click(screen.getByRole('button',{name:'Änderungen speichern'}));await screen.findByRole('alert');expect(screen.getByLabelText('Name').value).toBe('Beta');expect(changed).not.toHaveBeenCalled();
});

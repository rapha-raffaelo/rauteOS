import React from 'react';
import {render, screen, fireEvent, waitFor} from '@testing-library/react';
import {it, expect, vi, afterEach} from 'vitest';
import {AutoPressRelease} from './AutoPressRelease.jsx';
const reply = data => ({ok: true, headers: new Headers({'content-type':'application/json'}), json: async () => data});
afterEach(() => vi.unstubAllGlobals());

it('automatically requests the existing impulse draft and displays it without a creation button', async () => {
 const fetch = vi.fn().mockResolvedValue(reply({status:'ready',title:'Unsere Pressemitteilung',body:'Ein bereits vorbereiteter Entwurf.',label:'Entwurf',url:'/saved'}));
 vi.stubGlobal('fetch', fetch);
 render(<AutoPressRelease clientId={1} angleId={2} />);
 await screen.findByText('Ein bereits vorbereiteter Entwurf.');
 expect(fetch.mock.calls[0][1].method).toBe('POST');
 expect(screen.queryByRole('button')).toBeNull();
 expect(screen.getByRole('link').getAttribute('href')).toBe('/saved');
});

it('shows progress while the draft is being prepared', async () => {
 vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply({status:'running',stage:'writing',preview:'Ein wachsender Text',words:3})));
 render(<AutoPressRelease clientId={1} angleId={2} />);
 await screen.findByText('Ein wachsender Text');
 expect(screen.getByRole('progressbar').value).toBe(1);
 expect(screen.getByRole('status').textContent).toContain('3 Wörter geschrieben');
 expect(screen.getByRole('region', {name:'Live-Textvorschau'}).textContent).toContain('Unvollständige Vorschau');
});

it('does not repeatedly spend model calls after failure and supports an explicit retry', async () => {
 const fetch = vi.fn().mockResolvedValueOnce(reply({status:'failed',reason:'Bitte erneut versuchen.'})).mockResolvedValue(reply({status:'ready',title:'Fertig',body:'Gespeichert',label:'Entwurf',url:'/saved'}));
 vi.stubGlobal('fetch', fetch);
 render(<AutoPressRelease clientId={1} angleId={2} />);
 await screen.findByRole('alert');
 expect(fetch).toHaveBeenCalledTimes(1);
 fireEvent.click(screen.getByRole('button',{name:'Erneut versuchen'}));
 await screen.findByText('Gespeichert');
 expect(fetch.mock.calls[1][0]).toContain('?retry=true');
});

it('stops polling on unmount without discarding other page state', async () => {
 const fetch = vi.fn().mockResolvedValue(reply({status:'waiting'})); vi.stubGlobal('fetch', fetch);
 const {unmount} = render(<AutoPressRelease clientId={1} angleId={2} />);
 await screen.findByText('IM HINTERGRUND EINGEPLANT');
 unmount();
 expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
});

it('distinguishes a complete body under review from a saved draft', async () => {
 vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply({status:'running',stage:'checking',preview:'Vollständiger Text',words:2})));
 render(<AutoPressRelease clientId={1} angleId={2} />);
 await screen.findByText('Vollständiger Text');
 expect(screen.getByRole('progressbar').value).toBe(2);
 expect(screen.getByRole('status').textContent).toContain('Quellen und Formulierungen');
 expect(screen.queryByRole('link')).toBeNull();
});

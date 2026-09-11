import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DeskPage } from './DeskPage.jsx';

const empty = {rows: [], decisions: [], in_flight: [], clients_active: 0, actions_month: 0,
  opportunities: 0, decisions_open: 0, twins_with_gaps: 0, twin_average: 0, timezone: 'Europe/Zurich'};
const row = {client: {id: 7, name: '<script>alert(1)</script>', industry: 'Energy'},
  twin: {percent: 20, profile_filled: 0, profile_total: 17, kickoff_settled: 0,
    kickoff_total: 20, gaps: ['Kickoff unvollständig']}, actions_month: {released: 1, logged: 2, total: 3},
  actions_quarter: {total: 3}, promised_quarter: null, on_track: null, status: 'krise', opportunities: 2};
const reply = (body, status = 200) => ({ok: status === 200, status,
  headers: new Headers({'content-type': 'application/json'}), json: async () => body});
afterEach(() => vi.unstubAllGlobals());

describe('Desk', () => {
  it('loads the same-origin JSON contract and explains an empty portfolio', async () => {
    const fetch = vi.fn().mockResolvedValue(reply(empty)); vi.stubGlobal('fetch', fetch);
    render(<DeskPage />);
    expect(screen.getByRole('status').textContent).toContain('geladen');
    await screen.findByText('Noch kein Mandant angelegt.');
    expect(screen.getByRole('link', {name: /Mandant hinzufügen/}).getAttribute('href')).toBe('/mandant/neu');
    expect(fetch.mock.calls[0][0]).toBe('/api/v1/desk');
    expect(fetch.mock.calls[0][1].credentials).toBe('same-origin');
  });

  it('shows delivery counts, unknown contracts and crisis status without interpreting client text as markup', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply({...empty, rows: [row], clients_active: 1,
      twins_with_gaps: 1, actions_month: 3})));
    const {container} = render(<DeskPage />);
    await screen.findByText('nicht hinterlegt');
    expect(screen.getByText('Krise offen')).toBeTruthy();
    expect(screen.getAllByText(row.client.name)).toHaveLength(4);
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('td[title]').textContent).toBe('3');
    const form = container.querySelector('form');
    expect(form.getAttribute('action')).toBe('/desk/action');
    expect(form.getAttribute('method')).toBe('post');
    expect(new FormData(form).get('client_id')).toBe('7');
    expect(new FormData(form).get('redirect_to')).toBe('/desk');
  });

  it('renders a zero contract as measured and dates in the server timezone', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply({...empty,
      rows: [{...row, promised_quarter: 0, on_track: true}],
      in_flight: [{client: row.client, title: 'Released', state: 'raus',
        since: '2026-09-08T23:30:00Z', href: '/client/7/advice#outreach-1'}]})));
    render(<DeskPage />);
    await screen.findByText('0 / 3');
    expect(screen.queryByText('nicht hinterlegt')).toBeNull();
    expect(screen.getByText('09.09.')).toBeTruthy();
  });

  it('offers sign-in on session expiry instead of showing a login page as data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply(null, 401)));
    render(<DeskPage translations={{'Sitzung abgelaufen.': 'Session expired.'}} />);
    await screen.findByText('Session expired.');
    expect(screen.getByRole('link', {name: 'Anmelden'}).getAttribute('href')).toBe('/login?next=/desk');
  });

  it('retries a failed request and keeps a classic-page escape route', async () => {
    const fetch = vi.fn().mockRejectedValueOnce(new Error('network')).mockResolvedValueOnce(reply(empty));
    vi.stubGlobal('fetch', fetch); render(<DeskPage />);
    fireEvent.click(await screen.findByRole('button', {name: 'Erneut versuchen'}));
    await screen.findByText('Noch kein Mandant angelegt.');
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('rejects an HTML error response and cancels an outstanding request on navigation', async () => {
    const fetch = vi.fn().mockResolvedValue({ok: true, status: 200,
      headers: new Headers({'content-type': 'text/html'})});
    vi.stubGlobal('fetch', fetch);
    const {unmount} = render(<DeskPage />);
    await screen.findByRole('alert');
    expect(screen.getByRole('link', {name: 'Klassischen Desk öffnen'}).getAttribute('href')).toBe('/desk?view=classic');
    unmount();
    await waitFor(() => expect(fetch.mock.calls[0][1].signal.aborted).toBe(true));
  });
});

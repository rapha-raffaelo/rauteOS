import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DeskPage, briefing, firstName } from './DeskPage.jsx';

const empty = {rows: [], decisions: [], in_flight: [], clients_active: 0, actions_month: 0,
  opportunities: 0, decisions_open: 0, twins_with_gaps: 0, twin_average: 0, timezone: 'Europe/Zurich'};
const row = {client: {id: 7, name: '<script>alert(1)</script>', industry: 'Energy'},
  twin: {percent: 20, profile_filled: 0, profile_total: 17,
    gaps: ['Profil unvollständig']}, actions_month: {released: 1, logged: 2, total: 3},
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
    expect(screen.getAllByText(row.client.name)).toHaveLength(2);
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

  it('links every figure to the list it counts and lets a task be ticked off', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply({...empty, rows: [row], decisions_open: 1,
      tasks_open: 1, tasks: [{id: 4, client: null, title: 'Pitch', priority: 'hoch', due_on: null, href: '/aufgaben#task-4'}],
      decisions: [{client: row.client, kind: 'kundenfreigabe', title: 'Brief', detail: '', since: null, href: '/client/7/x'}]})));
    const {container} = render(<DeskPage />);
    await screen.findByText('Pitch');
    const hrefs = [...container.querySelectorAll('.stat-row a.stat')].map((a) => a.getAttribute('href'));
    expect(hrefs).toEqual(['/aufgaben?board=all', '/aufgaben?workspace=decisions', '/today', '#mandanten']);
    const tick = screen.getByRole('button', {name: 'Erledigt: Pitch'}).closest('form');
    expect(tick.getAttribute('action')).toBe('/aufgaben/4');
    expect(new FormData(tick).get('status')).toBe('erledigt');
    const decision = screen.getByRole('link', {name: /Brief.*Prüfen/});
    expect(decision.getAttribute('href')).toBe('/client/7/x');
    expect(decision.querySelector('.task__box')).toBeNull();
    expect(new FormData(tick).get('redirect_to')).toBe('/desk');
    expect(screen.getByRole('link', {name: /Kundenfreigaben/}).getAttribute('href')).toBe('/aufgaben?workspace=decisions');
  });

  it('lists open chances across mandates and links each to its workspace', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply({...empty, rows: [row], opportunities: 1,
      chances: [{client: row.client, kind: 'detected', title: 'EZB verschärft Kreditbedingungen', status: 'draft',
        since: '2026-11-04T08:00:00Z', href: '/client/7/opportunities?kind=detected&context=3'}]})));
    render(<DeskPage />);
    const link = await screen.findByRole('link', {name: /EZB verschärft Kreditbedingungen/});
    expect(link.getAttribute('href')).toBe('/client/7/opportunities?kind=detected&context=3');
    expect(screen.getByRole('link', {name: /Intelligence öffnen/}).getAttribute('href')).toBe('/today');
  });
});

describe('Briefing', () => {
  const t = (text) => text;
  it('names the open decisions, a crisis and the open chances from the figures', () => {
    const decision = (id, name, kind) => ({client: {id, name}, kind, title: 'x', detail: '', since: null, href: '#'});
    const text = briefing({...empty, decisions_open: 3, opportunities: 2,
      rows: [{...row, client: {id: 9, name: 'Qonto'}, status: 'krise'}],
      decisions: [decision(1, 'Zenchef', 'kundenfreigabe'), decision(1, 'Zenchef', 'freigabe'), decision(2, 'Qonto', 'impuls')]}, t);
    expect(text.lead).toBe('3 offene Entscheidungen');
    expect(text.rest).toBe('Krise offen bei Qonto. Zenchef wartet auf eine Kundenfreigabe. Qonto hat einen neuen Impuls. 2 Chancen sind offen.');
    expect(text.rest).not.toMatch(/\u2014/);
  });
  it('names tasks that are due', () => {
    const text = briefing({...empty, timezone: 'Europe/Berlin', tasks: [{id: 1, title: 'x', priority: 'hoch', due_on: '2000-01-01', href: '#'}]}, t);
    expect(text.rest).toBe('1 Aufgabe ist heute fällig oder überfällig.');
  });
  it('takes a first name only from an address that starts with one', () => {
    expect(firstName('lucas@raute-kopf.com')).toBe('Lucas');
    expect(firstName('lucas.neurauter@raute-kopf.com')).toBe('Lucas');
    expect(firstName('r.mankopf@raute-kopf.com')).toBe('');
    expect(firstName(null)).toBe('');
    expect(firstName('raphaelmankopf@gmail.com')).toBe('');
    expect(firstName('raphaelmankopf@gmail.com', 'Raphael')).toBe('Raphael');
  });
});

describe('KI-Briefing', () => {
  it('asks once on click, shows RAUTE\'s text and keeps the figures as the fallback', async () => {
    const fetch = vi.fn((url, opts) => Promise.resolve(url.endsWith('/briefing')
      ? reply({text: 'Zenchef wartet auf die Freigabe der Pressemitteilung.', written_at: '2026-11-05T08:00:00Z'})
      : reply(empty)));
    vi.stubGlobal('fetch', fetch);
    render(<DeskPage />);
    await screen.findByText('Keine offene Entscheidung');
    fireEvent.click(screen.getByRole('button', {name: 'KI-Briefing'}));
    await screen.findByText('Zenchef wartet auf die Freigabe der Pressemitteilung.');
    expect(fetch.mock.calls[1][0]).toBe('/api/v1/desk/briefing');
    expect(fetch.mock.calls[1][1].method).toBe('POST');
    expect(screen.getByRole('button', {name: 'Neu formulieren'})).toBeTruthy();
  });
});

import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QuestionAudio } from './QuestionAudio.jsx';

afterEach(() => vi.unstubAllGlobals());
const item = {id: 'a1', question_key: 'Q01.02', status: 'ready', transcript: 'Wir wollen nach Österreich und in die Schweiz.',
  retained: true, review: '', answer_fact_id: null, created_at: '2026-11-07T09:30:00Z'};
const ok = body => Promise.resolve({ok: true, json: async () => body});

it('puts the transcript beside an answer field and saves what the consultant wrote', async () => {
  const fetch = vi.fn(() => ok({...item, answer_fact_id: 7}));
  vi.stubGlobal('fetch', fetch);
  const changed = vi.fn(async () => {});
  render(<QuestionAudio clientId={1} items={[item]} onChanged={changed} />);
  expect(screen.getByText(item.transcript)).toBeTruthy();
  expect(document.querySelector('audio').getAttribute('src')).toBe('/client/1/onboarding-audio/a1/content');
  fireEvent.change(screen.getByLabelText('Antwort aus dem Audio'), {target: {value: 'Ziel: DACH.'}});
  fireEvent.click(screen.getByRole('button', {name: 'Als Antwort speichern'}));
  await waitFor(() => expect(changed).toHaveBeenCalled());
  expect(fetch.mock.calls[0][0]).toBe('/client/1/onboarding-audio/a1/answer');
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({value: 'Ziel: DACH.'});
});

it('archives an answered recording and deletes a duplicate from the bin icon', async () => {
  const fetch = vi.fn(() => ok({ok: true}));
  vi.stubGlobal('fetch', fetch);
  vi.stubGlobal('confirm', () => true);
  render(<QuestionAudio clientId={1} items={[{...item, answer_fact_id: 7}, {...item, id: 'a2'}]} onChanged={async () => {}} />);
  expect(screen.getAllByRole('button', {name: 'Ins Archiv'})).toHaveLength(1);
  fireEvent.click(screen.getByRole('button', {name: 'Ins Archiv'}));
  await waitFor(() => expect(fetch.mock.calls[0][0]).toBe('/client/1/onboarding-audio/a1/archive'));
  fireEvent.click(screen.getAllByRole('button', {name: 'Aufnahme verwerfen'})[1]);
  await waitFor(() => expect(fetch.mock.calls[1]).toEqual(['/client/1/onboarding-audio/a2', expect.objectContaining({method: 'DELETE'})]));
});

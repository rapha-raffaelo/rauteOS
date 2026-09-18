import React from 'react';
import {render, screen, fireEvent, waitFor} from '@testing-library/react';
import {afterEach, expect, it, vi} from 'vitest';
import {CustomMessageComposer, consumeDraft} from './CustomMessageComposer.jsx';

const encoder = new TextEncoder();
const frame = (type, data) => encoder.encode(`event: ${type}\ndata: ${JSON.stringify(data)}\n\n`);
function response(stream) { return {ok: true, headers: new Headers({'content-type': 'text/event-stream'}), body: stream}; }
afterEach(() => vi.unstubAllGlobals());

it('only writes on submit and shows real live words before completing', async () => {
  let writer;
  const stream = new ReadableStream({start(c) {writer = c;}});
  const fetch = vi.fn().mockResolvedValue(response(stream)); vi.stubGlobal('fetch', fetch);
  render(<CustomMessageComposer clientId={1} angleId={2} />);
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', {name: 'Kundenmail'}));
  expect(screen.getByLabelText('Dein Auftrag').value).toContain('Kundenmail');
  fireEvent.change(screen.getByLabelText('Dein Auftrag'), {target: {value: 'Eine kurze Nachricht für unseren Kunden'}});
  fireEvent.click(screen.getByRole('button', {name: 'Eigene Nachricht schreiben'}));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  writer.enqueue(frame('preview', 'Hallo zusammen'));
  await screen.findByText('2 Wörter geschrieben');
  expect(screen.getByRole('progressbar').hasAttribute('value')).toBe(false);
  expect(JSON.parse(fetch.mock.calls[0][1].body).instruction).toBe('Eine kurze Nachricht für unseren Kunden');
  writer.enqueue(frame('saved', JSON.stringify({title:'Hallo',body:'Hallo zusammen',version:'new',url:'/saved',notice:'Entwurf gespeichert.'}))); writer.close();
  await screen.findByRole('link', {name: /Entwurf bearbeiten/});
  await waitFor(() => expect(screen.getByRole('progressbar').getAttribute('value')).toBe('1'));
});

it('keeps the instruction and partial preview on stream failure', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(new ReadableStream({start(c) {
    c.enqueue(frame('preview', 'Ein halber Text')); c.enqueue(frame('error', 'Erstellung fehlgeschlagen')); c.close();
  }}))));
  render(<CustomMessageComposer clientId={1} angleId={2} />);
  fireEvent.click(screen.getByRole('button', {name:'Statement'}));
  fireEvent.click(screen.getByRole('button', {name:'Eigene Nachricht schreiben'}));
  await screen.findByRole('alert');
  expect(screen.getByLabelText('Dein Auftrag').value).toContain('Statement');
  expect(screen.getByText('Ein halber Text')).toBeTruthy();
  expect(screen.queryByRole('link')).toBeNull();
  expect(screen.getByRole('button', {name:'Eigene Nachricht schreiben'}).disabled).toBe(false);
});

it('parses fragmented UTF-8 frames and rejects incomplete responses', async () => {
  const data = frame('preview','Grüße 🙂'); const received = [];
  const stream = new ReadableStream({start(c) {for (const byte of data) c.enqueue(new Uint8Array([byte])); c.close();}});
  await expect(consumeDraft(response(stream), (...event) => received.push(event))).rejects.toThrow('unterbrochen');
  expect(received).toEqual([['preview','Grüße 🙂']]);
});

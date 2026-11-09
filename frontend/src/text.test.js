import { expect, it } from 'vitest';
import { clip } from './text.js';

it('shortens at a whole word, never inside one', () => {
  expect(clip('Neobroker in Deutschland: Der Betrieb im Wachstum entscheidet, nicht der Start', 60))
    .toBe('Neobroker in Deutschland: Der Betrieb im Wachstum …');
  expect(clip('kurz', 60)).toBe('kurz');
});

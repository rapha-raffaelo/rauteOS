import React from 'react';
import {expect, it} from 'vitest';
import {fireEvent, render, screen, within} from '@testing-library/react';
import {MediaShortlist} from './MediaShortlist.jsx';
const entry = (name, articles = 2) => ({name, articles, last_seen:'2026-11-06T08:00:00Z'});
const base = {days:30, market_authors:[], own_authors:[], market_outlets:[], own_outlets:[]};
it('shows shared author labels once with separate coverage counts and an encoded contact search', () => {
  render(<MediaShortlist data={{...base, market_authors:[entry('Anna & Max', 7)], own_authors:[entry('Anna & Max', 3)]}}/>);
  const row = screen.getByRole('rowheader', {name:'Anna & Max'}).closest('tr');
  expect(within(row).getAllByRole('cell').map(cell=>cell.textContent).slice(0,2)).toEqual(['3','7']);
  expect(within(row).getByRole('link').getAttribute('href')).toBe('/contacts?q=Anna%20%26%20Max');
});
it('searches all 520 entries, resets pagination and separates coverage and media', () => {
  render(<MediaShortlist data={{...base, market_authors:Array.from({length:520},(_,i)=>entry(`Autor ${String(i).padStart(3,'0')}`)), own_authors:[entry('Kundenautor')], own_outlets:[entry('Zeitung')]}}/>);
  expect(screen.getAllByRole('rowheader')).toHaveLength(20);
  fireEvent.click(screen.getByRole('button',{name:'Weiter'}));
  expect(screen.getByText('2 / 27')).toBeTruthy();
  fireEvent.change(screen.getByRole('searchbox'),{target:{value:'Autor 519'}});
  expect(screen.getAllByRole('rowheader')).toHaveLength(1);
  expect(screen.getByRole('rowheader',{name:'Autor 519'})).toBeTruthy();
  fireEvent.change(screen.getByRole('combobox'),{target:{value:'own'}});
  expect(screen.getByText('Keine passenden Einträge gefunden.')).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Filter zurücksetzen'}));
  fireEvent.change(screen.getByRole('combobox'),{target:{value:'own'}});
  expect(screen.getAllByRole('rowheader')).toHaveLength(1);
  expect(screen.getByRole('rowheader',{name:'Kundenautor'})).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Medien'}));
  expect(screen.getByRole('rowheader',{name:'Zeitung'})).toBeTruthy();
  expect(screen.queryByRole('rowheader',{name:'Kundenautor'})).toBeNull();
});
it('explains missing author data without claiming there are no journalists', () => {
  render(<MediaShortlist data={base}/>);
  expect(screen.getByText('In diesem Zeitraum wurden keine Autorennamen von den Quellen mitgeliefert.')).toBeTruthy();
  expect(screen.getByRole('link',{name:/Kontaktbuch öffnen/}).getAttribute('href')).toBe('/contacts');
});

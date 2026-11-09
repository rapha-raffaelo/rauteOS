import React from 'react';
import {render,screen} from '@testing-library/react';
import {it,expect} from 'vitest';
import {FactValue,hasMissingFact} from './FactValue.jsx';
it('shows missing metrics in italics while preserving available facts',()=>{
 render(<p><FactValue text={'Mitarbeitende: nicht veröffentlicht\nUmsatz: unbekannt\nStammkapital: 4.000 €'}/></p>);
 expect(screen.getAllByText('bitte ergänzen').every(el=>el.tagName==='EM')).toBe(true);
 expect(screen.getByText(/Stammkapital: 4.000 €/)).toBeTruthy();
 expect(hasMissingFact('Umsatz: nicht veröffentlicht')).toBe(true);
 expect(hasMissingFact('Die behauptete Wirkung ist nicht unabhängig belegt.')).toBe(false);
});

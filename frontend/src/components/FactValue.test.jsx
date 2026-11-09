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
it('turns a sentence that reports a gap into open fields instead of prose',()=>{
 const text='Öffentlich bekannt ist nur ein Standort, der Firmensitz in Münchendorf in Niederösterreich. Zu Mitarbeiterzahl und Umsatz gibt es keine öffentlichen Angaben.';
 const {container}=render(<p><FactValue text={text}/></p>);
 expect(container.textContent).not.toMatch(/keine öffentlichen Angaben/);
 expect(container.textContent).toMatch(/Firmensitz in Münchendorf/);
 expect(container.textContent).toMatch(/Mitarbeitende: bitte ergänzen/);
 expect(container.textContent).toMatch(/Umsatz: bitte ergänzen/);
 expect(screen.getAllByText('bitte ergänzen').every(el=>el.tagName==='EM')).toBe(true);
 expect(hasMissingFact(text)).toBe(true);
 expect(hasMissingFact('Ein bislang unbekannter Hersteller übernahm 2021.')).toBe(false);
});

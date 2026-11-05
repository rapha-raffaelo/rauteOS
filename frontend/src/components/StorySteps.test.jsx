import React from 'react';
import { expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { currentStep, Stepper } from './OpportunitiesPage.jsx';
import { FitPanel } from './JournalistsPage.jsx';

it('puts a story on the first step whose work is not done', () => {
  expect(currentStep({ id: null })).toBe('analyse');
  expect(currentStep({ id: 1, storyline: '' })).toBe('storyline');
  expect(currentStep({ id: 1, storyline: 'x', assets: [] })).toBe('assets');
  expect(currentStep({ id: 1, storyline: 'x', assets: [{}], contact_ids: [] })).toBe('medien');
  expect(currentStep({ id: 1, storyline: 'x', assets: [{}], contact_ids: [2], status: 'active' })).toBe('outreach');
  expect(currentStep({ id: 1, storyline: 'x', assets: [{ released_at: '2026-11-05' }], contact_ids: [2], status: 'active' })).toBe('ergebnisse');
});

it('draws the six steps and marks the current one', () => {
  render(<Stepper current="assets" onPick={() => {}} />);
  const steps = screen.getAllByRole('button').map((b) => b.textContent);
  expect(steps).toEqual(['1Analyse', '2Storyline', '3Assets', '4Medien', '5Outreach', '6Ergebnisse']);
  expect(screen.getByRole('button', { name: /Assets/ }).getAttribute('aria-current')).toBe('step');
});

it('states the fit from what the profile holds and nothing else', () => {
  render(<FitPanel data={{ profile: { topics: ['Banking', 'KMU'], relationship_status: 'interessiert' },
    articles: [{}, {}], relationship_options: [{ value: 'interessiert', label: 'Interessiert' }] }} />);
  expect(screen.getByText('Thematischer Schwerpunkt: Banking · KMU')).toBeTruthy();
  expect(screen.getByText('2 Veröffentlichungen als Relevanzsignal')).toBeTruthy();
  expect(screen.getByText('Kontaktstatus: Interessiert')).toBeTruthy();
});

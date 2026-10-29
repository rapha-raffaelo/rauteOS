import {readFileSync} from 'node:fs';
import {expect,it} from 'vitest';
import {missingTranslations} from './onboardingText.js';
// Every sentence the customer page passes through tr() needs an English version.
it('has an English version of every customer-facing sentence',()=>{
  const sources=['components/OnboardingPage.jsx','components/OnboardingAudio.jsx'].map(f=>readFileSync(new URL(f,import.meta.url),'utf8')).join('\n');
  const texts=[...sources.matchAll(/\btr\((['"])(.+?)\1\)/g)].map(m=>m[2]);
  expect(texts.length).toBeGreaterThan(60);
  expect(missingTranslations(texts)).toEqual([]);
});

import React from 'react';
import { createRoot } from 'react-dom/client';
import { OnboardingPage } from './components/OnboardingPage.jsx';
import './onboarding.css';
import {createDemoApi} from './onboardingDemo.js';
const demo = document.getElementById('onboarding-demo');
const demoApi = demo ? createDemoApi(JSON.parse(demo.textContent)) : null;
createRoot(document.getElementById('onboarding-root')).render(<OnboardingPage demoApi={demoApi} />);

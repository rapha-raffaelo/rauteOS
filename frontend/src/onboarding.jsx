import React from 'react';
import { createRoot } from 'react-dom/client';
import { OnboardingPage } from './components/OnboardingPage.jsx';
import './onboarding.css';
createRoot(document.getElementById('onboarding-root')).render(<OnboardingPage />);

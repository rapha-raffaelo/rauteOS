import React from 'react';
import { createRoot } from 'react-dom/client';
import { DeskPage } from './components/DeskPage.jsx';
import './desk.css';

const root = document.getElementById('react-desk');
if (root) {
  const translations = JSON.parse(document.getElementById('desk-translations').textContent);
  createRoot(root).render(<DeskPage translations={translations} language={document.documentElement.lang} />);
}

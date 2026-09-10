import React from 'react';
import { createRoot } from 'react-dom/client';
import { TwinPage } from './components/TwinPage.jsx';
import './twin.css';
const root = document.getElementById('react-twin');
if (root) createRoot(root).render(<TwinPage clientId={Number(root.dataset.clientId)} />);

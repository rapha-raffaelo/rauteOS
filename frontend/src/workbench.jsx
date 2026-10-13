import React from 'react';
import {createRoot} from 'react-dom/client';
import {WorkbenchPage} from './components/WorkbenchPage.jsx';
import './twin.css';
import './workbench.css';
const root=document.getElementById('react-workbench');
// Was der Server in das Element geschrieben hat, zählt nur beim ersten Aufbau.
// Danach ist die Adresse die Wahrheit — siehe router.jsx.
if(root)createRoot(root).render(<WorkbenchPage page={root.dataset.page} clientId={Number(root.dataset.clientId)||null}/>);

import React from 'react';
import {createRoot} from 'react-dom/client';
import {ThemenPage} from './components/ThemenPage.jsx';
import './twin.css';
import './opportunities.css';
import './themen.css';
const root=document.getElementById('react-themen');
if(root)createRoot(root).render(<ThemenPage clientId={Number(root.dataset.clientId)}/>);

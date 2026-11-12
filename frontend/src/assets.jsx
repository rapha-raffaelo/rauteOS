import React from 'react';
import {createRoot} from 'react-dom/client';
import {AssetsPage} from './components/AssetsPage.jsx';
import './twin.css';
import './opportunities.css';
import './themen.css';
const root=document.getElementById('react-assets');
if(root)createRoot(root).render(<AssetsPage clientId={Number(root.dataset.clientId)}/>);

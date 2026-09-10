import React from 'react';
import {createRoot} from 'react-dom/client';
import {OpportunitiesPage} from './components/OpportunitiesPage.jsx';
import './twin.css';
import './journalists.css';
import './opportunities.css';
const root=document.getElementById('react-opportunities');
if(root)createRoot(root).render(<OpportunitiesPage clientId={Number(root.dataset.clientId)}/>);

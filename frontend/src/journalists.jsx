import React from 'react';
import {createRoot} from 'react-dom/client';
import {JournalistsPage} from './components/JournalistsPage.jsx';
import './twin.css';
import './journalists.css';
const root=document.getElementById('react-journalists');
if(root) createRoot(root).render(<JournalistsPage/>);

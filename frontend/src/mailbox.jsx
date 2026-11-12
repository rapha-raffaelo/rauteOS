import React from 'react';
import {createRoot} from 'react-dom/client';
import {MailboxPage} from './components/MailboxPage.jsx';
import './twin.css';
import './themen.css';
import './mailbox.css';
const root=document.getElementById('react-mailbox');
if(root)createRoot(root).render(<MailboxPage/>);

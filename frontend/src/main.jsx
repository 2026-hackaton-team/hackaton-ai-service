import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './styles.css';
import './forms.css';
import './people-ledger.css';
import './home-overview.css';
import './warm-theme.css';
import './sidebar-layout.css';
import './occasion-theme.css';
import './mobile.css';
import './account-status.css';

createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>);

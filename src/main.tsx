import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { ApiKeyGate } from './components/ApiKeyGate';
import { AppProvider } from './core/store';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppProvider>
      <ApiKeyGate>
        <App />
      </ApiKeyGate>
    </AppProvider>
  </React.StrictMode>
);

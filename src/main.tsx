import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import {ApiKeyGate} from './components/ApiKeyGate.tsx';
import {AppProvider} from './core/store.tsx';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppProvider>
      <ApiKeyGate>
        <App />
      </ApiKeyGate>
    </AppProvider>
  </StrictMode>,
);

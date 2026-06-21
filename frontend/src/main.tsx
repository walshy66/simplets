import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { AuthProvider } from './auth';
import { applyTheme, readStoredTheme, resolveInitialTheme, systemPrefersDark } from './theme';

// Apply the saved/system theme before first paint to avoid a flash of light mode.
applyTheme(resolveInitialTheme(readStoredTheme(), systemPrefersDark()));

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </React.StrictMode>,
);

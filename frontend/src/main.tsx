import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Provider } from 'react-redux';
import { RouterProvider } from 'react-router-dom';
import { store } from '@/app/store';
import { router } from '@/router';
import { startAuthStorageSync } from '@/features/auth/storageSync';
import { retryPendingLogout } from '@/api/auth';
import { startThemeSync } from '@/lib/theme';
import { registerServiceWorker } from '@/lib/push';
import { startRealtimeSync } from '@/features/realtime/realtime';
import '@/i18n';
import '@/styles/index.css';

startAuthStorageSync(store);
startRealtimeSync(store);
void retryPendingLogout();
startThemeSync();
void registerServiceWorker();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Provider store={store}>
      <RouterProvider router={router} />
    </Provider>
  </StrictMode>,
);

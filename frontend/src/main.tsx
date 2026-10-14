// Self-hosted fonts (latin subset only): no render-blocking third-party request, tighter CSP.
import '@fontsource/inter/latin-400.css';
import '@fontsource/inter/latin-500.css';
import '@fontsource/inter/latin-600.css';
import '@fontsource/inter/latin-700.css';
import '@fontsource/jetbrains-mono/latin-400.css';
import '@fontsource/jetbrains-mono/latin-600.css';
import { ChakraProvider, ColorModeScript, localStorageManager } from '@chakra-ui/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { HelmetProvider } from 'react-helmet-async';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { queryClient } from './lib/queryClient';
import theme from './theme';

/** Light mode only: ignore any dark mode a visitor's browser saved from the old theme. */
const lightOnly: typeof localStorageManager = {
  ...localStorageManager,
  get: () => 'light',
  set: () => undefined,
};

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element #root not found');
}

createRoot(rootElement).render(
  <StrictMode>
    <ColorModeScript initialColorMode="light" type="localStorage" />
    <HelmetProvider>
      <ChakraProvider theme={theme} colorModeManager={lightOnly}>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </QueryClientProvider>
      </ChakraProvider>
    </HelmetProvider>
  </StrictMode>,
);

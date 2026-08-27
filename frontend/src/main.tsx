import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ThemeProvider } from './components/theme-provider'
import { TelemetryErrorBoundary } from './components/TelemetryErrorBoundary'
import { initFrontendTelemetry } from './lib/telemetry'
import './index.css'
import App from './App.tsx'

// Register global error/unhandled-rejection listeners (privacy-safe)
initFrontendTelemetry()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <TelemetryErrorBoundary componentName="App">
        <App />
      </TelemetryErrorBoundary>
    </ThemeProvider>
  </StrictMode>,
)


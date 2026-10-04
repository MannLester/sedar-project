import { Navigate, Route, Routes } from 'react-router-dom'
import { EmbeddedFrame } from './components/layout/EmbeddedFrame'
import { Shell } from './components/layout/Shell'
import { ChiefEngineerHomePage } from './pages/chief-engineer/ChiefEngineerHomePage'
import { ChiefEngineerMonitoringPage } from './pages/chief-engineer/ChiefEngineerMonitoringPage'
import { DailyEngineLogHistory } from './pages/chief-engineer/DailyEngineLogHistory'

const routes = (
  <Routes>
    <Route path="/" element={<ChiefEngineerHomePage />} />
    <Route path="/monitoring" element={<ChiefEngineerMonitoringPage />} />
    <Route path="/monitoring/history" element={<DailyEngineLogHistory />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
)

// Embedded: shown inside Odoo's own screen. Standalone: its own page with its own sidebar, which also works offline.
export default function App({ embedded = false }: { embedded?: boolean }) {
  if (embedded) return <EmbeddedFrame>{routes}</EmbeddedFrame>
  return (
    <Shell>
      <main className="technical-dashboard">{routes}</main>
    </Shell>
  )
}

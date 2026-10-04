import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App'
import { EngineRoomProvider } from './context/EngineRoomContext'
import './fonts.css'
import './index.css'
import './engine-room.css'
import './print.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HashRouter>
      <EngineRoomProvider>
        <App />
      </EngineRoomProvider>
    </HashRouter>
  </StrictMode>,
)

if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {})

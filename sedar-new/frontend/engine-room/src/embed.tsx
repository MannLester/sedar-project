import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import App from './App'
import { EngineRoomProvider } from './context/EngineRoomContext'
import fontStyles from './fonts.css?inline'
import styles from './index.css?inline'
import frameStyles from './engine-room.css?inline'
import printStyles from './print.css?inline'

const PROPERTY_RULES = /@property\s+--[\w-]+\s*\{[^}]*\}/g

// Odoo owns the page, so Ed's CSS lives in a shadow root. Only what cannot work there goes to the page:
// Tailwind's @property registrations, the @font-face rules and the print sheet, which is attached to the body.
function installPageStyles() {
  if (document.getElementById('sedar-engine-room-page-styles')) return
  const style = document.createElement('style')
  style.id = 'sedar-engine-room-page-styles'
  style.textContent = `${styles.match(PROPERTY_RULES)?.join('\n') ?? ''}\n${fontStyles}\n${printStyles}`
  document.head.appendChild(style)
}

export function mount(host: HTMLElement): () => void {
  installPageStyles()
  const shadow = host.shadowRoot ?? host.attachShadow({ mode: 'open' })
  const style = document.createElement('style')
  style.textContent = `:host{all:initial;display:block;height:100%;overflow:auto}\n${styles.replace(/:root/g, ':host')}\n${frameStyles}`
  const container = document.createElement('div')
  container.style.height = '100%'
  shadow.replaceChildren(style, container)
  const root = createRoot(container)
  root.render(
    <StrictMode>
      <MemoryRouter>
        <EngineRoomProvider>
          <App embedded />
        </EngineRoomProvider>
      </MemoryRouter>
    </StrictMode>,
  )
  return () => {
    root.unmount()
    shadow.replaceChildren()
  }
}

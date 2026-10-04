import { useEffect, useState, type ReactNode } from 'react'
import { Gauge, History, LayoutDashboard, LogOut, Menu, PanelLeft, RefreshCw, X } from 'lucide-react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useEngineRoom } from '../../context/engineRoomStore'
import { Toast } from '../ui/Toast'
import { Banners } from './Banners'

const NAV = [
  { label: 'Dashboard', path: '/', icon: LayoutDashboard, end: true },
  { label: 'Daily Engine Log', path: '/monitoring', icon: Gauge, end: true },
  { label: 'Daily Logs History', path: '/monitoring/history', icon: History, end: true },
]

export function Shell({ children }: { children: ReactNode }) {
  const { currentRole, userName, tugs, activeTug, selectTug, online, queue, lastSynced, syncNow, toast, clearToast } = useEngineRoom()
  const [desktopOpen, setDesktopOpen] = useState(() => localStorage.getItem('engine-room:sidebar') !== 'closed')
  const [mobileOpen, setMobileOpen] = useState(false)
  const navigate = useNavigate()
  const { pathname } = useLocation()

  useEffect(() => localStorage.setItem('engine-room:sidebar', desktopOpen ? 'open' : 'closed'), [desktopOpen])

  const waiting = queue.filter((item) => !item.error).length
  const logo = `${import.meta.env.BASE_URL}logo.png`

  return (
    <div className={desktopOpen ? 'app-shell' : 'app-shell sidebar-collapsed'}>
      <aside className={`sidebar${desktopOpen ? '' : ' desktop-collapsed'}${mobileOpen ? ' mobile-open' : ''}`} aria-label="Engine room navigation">
        <div className="brand-block">
          {desktopOpen ? (
            <div className="brand-mark"><img src={logo} alt="" /></div>
          ) : (
            <button type="button" className="brand-mark brand-expand" aria-label="Expand sidebar" title="Expand sidebar" onClick={() => setDesktopOpen(true)}><img src={logo} alt="" /></button>
          )}
          <div className="brand-copy"><strong>SEDAR</strong></div>
          <button type="button" className="sidebar-close desktop-collapse" aria-label="Collapse sidebar" aria-expanded={desktopOpen} onClick={() => setDesktopOpen(false)}><PanelLeft size={17} /></button>
          <button type="button" className="sidebar-close mobile-close" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={17} /></button>
        </div>
        {desktopOpen && tugs.length > 1 && (
          <div className="grid gap-1 px-4 pb-3">
            <label htmlFor="tug-select" className="nav-group-label">Tugboat</label>
            <select
              id="tug-select"
              value={activeTug?.id ?? ''}
              onChange={(event) => {
                selectTug(Number(event.target.value))
                navigate(pathname)
              }}
              className="h-10 rounded-md border border-white/20 bg-white/10 px-2 text-sm font-bold text-white"
            >
              {tugs.map((tug) => (
                <option key={tug.id} value={tug.id} className="text-slate-900">{tug.name}</option>
              ))}
            </select>
          </div>
        )}
        <nav className="sidebar-nav" aria-label="Engine room navigation">
          <section className="nav-group">
            <h2 className="nav-group-label">Active Operations</h2>
            <ul className="nav-list">
              {NAV.map(({ label, path, icon: Icon, end }) => (
                <li key={path}>
                  <NavLink to={path} end={end} className={({ isActive }) => (isActive ? 'sidebar-link active' : 'sidebar-link')} aria-label={label} title={desktopOpen ? undefined : label} onClick={() => setMobileOpen(false)}>
                    <Icon aria-hidden="true" size={16} />
                    <span>{label}</span>
                  </NavLink>
                </li>
              ))}
              <li>
                <a className="sidebar-link" href="/odoo" aria-label="Back to Odoo" title={desktopOpen ? undefined : 'Back to Odoo'}>
                  <LogOut aria-hidden="true" size={16} />
                  <span>Back to Odoo</span>
                </a>
              </li>
            </ul>
          </section>
        </nav>
        <div className="sidebar-footer-wrapper">
          <div className="sidebar-footer">
            <div className="footer-avatar" role="img" aria-label={currentRole}>{(userName || 'S').charAt(0).toUpperCase()}</div>
            <div className="footer-department-info">
              <strong>{userName || 'Not signed in'}</strong>
              <span>{currentRole} · {online ? 'Online' : 'Offline'}{waiting ? ` · ${waiting} waiting` : ''}</span>
            </div>
            <button type="button" className="sidebar-close" aria-label="Sync now" title={lastSynced ? `Data from ${lastSynced} UTC` : 'Not synced yet'} onClick={syncNow}><RefreshCw size={14} /></button>
          </div>
        </div>
      </aside>
      {mobileOpen && <button className="sidebar-backdrop" type="button" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
      <main className="workspace">
        <button type="button" className="mb-3 inline-flex items-center gap-2 text-sm font-bold text-slate-700 md:hidden" aria-label="Open navigation" onClick={() => setMobileOpen(true)}>
          <Menu size={18} aria-hidden="true" /> Menu
        </button>
        <Banners />
        {children}
        {toast && <Toast message={toast} onClose={clearToast} />}
      </main>
    </div>
  )
}

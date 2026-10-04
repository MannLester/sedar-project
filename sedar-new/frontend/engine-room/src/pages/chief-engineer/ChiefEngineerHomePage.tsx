import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Clock3, Fuel, Gauge, Wrench } from 'lucide-react'
import { RecentWatchLogsCard } from '../../components/chief-engineer/RecentWatchLogsCard'
import { useEngineRoom } from '../../context/engineRoomStore'
import { todayISO } from '../../utils/engineLog'

const consoleTitle = 'Engine Room Console'

const summaryCards = [
  { key: 'hours', label: 'Total Running Hours', icon: Clock3 },
  { key: 'fuel', label: 'Fuel R.O.B. Remaining', icon: Fuel },
  { key: 'tasks', label: 'Open PMS Tasks', icon: Wrench },
] as const

export function ChiefEngineerHomePage() {
  const { activeTug, reports, draftSummary, selectLog } = useEngineRoom()
  const [now, setNow] = useState(() => new Date())

  useEffect(() => selectLog(null), [selectLog])

  useEffect(() => {
    const clock = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(clock)
  }, [])

  const dateLabel = now.toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' })
  const timeLabel = now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })

  const today = todayISO()
  const todays = reports.filter((report) => report.date === today && report.state !== 'draft')
  const draftToday = draftSummary?.date === today ? draftSummary : null
  const hoursToday = todays.reduce((total, report) => total + report.hours, 0) + (draftToday?.hours ?? 0)
  const mainEngine = activeTug?.engines[0]
  const fuelRob = draftSummary?.fuelRob ?? mainEngine?.last_fuel_rob ?? 0

  const summaryValues: Record<(typeof summaryCards)[number]['key'], { value: string; detail: string }> = {
    hours: {
      value: hoursToday.toFixed(1),
      detail: [
        todays.length ? `${todays.length} watch log${todays.length > 1 ? 's' : ''} today` : 'No watch logged today',
        draftToday ? 'plus the log in progress' : '',
      ].filter(Boolean).join(' · '),
    },
    fuel: { value: fuelRob.toLocaleString(), detail: mainEngine ? `Litres · ${mainEngine.name.replace(activeTug?.name ?? '', '').trim()}` : 'Litres' },
    tasks: { value: String(activeTug?.open_pm_tasks ?? 0), detail: 'Across all maintenance intervals' },
  }

  return (
    <>
      <header className="tech-dashboard-header">
        <div className="tech-header-text">
          <span className="tech-header-kicker">{consoleTitle}</span>
          <h1>{activeTug?.name ?? 'No tugboat'}</h1>
        </div>
        <div className="tech-header-actions">
          <div className="text-right">
            <span className="block text-[11px] font-bold uppercase tracking-[.14em] text-[#5f6873]">{dateLabel}</span>
            <strong className="block text-3xl font-bold tabular-nums leading-tight text-[#152f48]">{timeLabel}</strong>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {summaryCards.map((card) => {
          const Icon = card.icon
          const summary = summaryValues[card.key]
          return (
            <article key={card.key} className="tech-summary-card">
              <div className="tech-card-header">
                <span className="tech-card-label">{card.label}</span>
                <span className="tech-card-icon" style={{ color: '#315d82', background: '#f2f5f8' }}>
                  <Icon size={18} />
                </span>
              </div>
              <strong className="tech-card-value" style={{ color: '#152f48' }}>{summary.value}</strong>
              <span className="tech-card-detail">{summary.detail}</span>
            </article>
          )
        })}
      </div>

      <div className="grid gap-4 md:grid-cols-1">
        <Link to="/monitoring" className="tech-panel chief-entry-tile chief-entry-filled group flex min-h-[200px] flex-col p-6">
          <span className="grid size-12 place-items-center rounded-[10px] bg-white/10 text-white">
            <Gauge size={24} aria-hidden="true" />
          </span>
          <h3 className="mt-4 text-lg font-bold text-white">Daily Engine Monitoring</h3>
          <p className="mt-2 text-sm leading-relaxed text-white/75">
            Record start/stop times, RPM, oil pressure, water temperature and fuel R.O.B. for the main and auxiliary engines.
          </p>
          <span className="mt-auto inline-flex items-center gap-1.5 pt-4 text-xs font-bold uppercase tracking-wider text-white">
            Open module
            <ArrowRight size={15} aria-hidden="true" className="transition-transform group-hover:translate-x-1" />
          </span>
        </Link>
      </div>

      <RecentWatchLogsCard reports={reports.slice(0, 5)} />
    </>
  )
}

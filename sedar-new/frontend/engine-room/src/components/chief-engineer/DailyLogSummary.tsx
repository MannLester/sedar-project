import type { EngineLog } from '../../types/engineLog'

interface DailyLogSummaryProps {
  logs: EngineLog[]
  vesselName: string
  now: Date
  watchStart: string
  watchStop: string
}

function roundTo(value: number, decimals: number): number {
  const factor = 10 ** decimals
  return Math.round(value * factor) / factor
}

function watchHoursOf(log: EngineLog): number {
  return Math.max(0, roundTo(log.meterCurrent - log.meterPrevious, 1))
}

function consumedOf(log: EngineLog): number {
  return Math.max(0, log.fuelRobStart - log.fuelRobStop)
}

const STATUS_META = {
  running: { label: 'Operated', chip: 'bg-green-100 text-green-800' },
  stopped: { label: 'No Operation', chip: 'bg-amber-100 text-amber-800' },
  standby: { label: 'Standby', chip: 'bg-slate-100 text-slate-700' },
} as const

function statusOf(log: EngineLog): keyof typeof STATUS_META {
  if (!log.timeStart) return 'standby'
  return log.timeStop ? 'stopped' : 'running'
}

export function DailyLogSummary({ logs, vesselName, now, watchStart, watchStop }: DailyLogSummaryProps) {
  const totalHours = logs.reduce((sum, log) => sum + watchHoursOf(log), 0)
  const totalConsumed = logs.reduce((sum, log) => sum + consumedOf(log), 0)
  const dateLabel = now.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
  // Exact times entered by the user, regardless of each engine's OPERATED / NO OPERATION badge.
  // While the log is still being filled (no cut-off yet) it reads "06:00 – ongoing".
  const windowLabel = watchStop ? `${watchStart || '—'} – ${watchStop}` : `${watchStart || '—'} – ongoing`

  return (
    <section aria-label="Watch log review summary" className="overflow-hidden rounded-[10px] border border-slate-200 bg-white">
      {/* TODO (Print layout): when the Chief clicks "APPROVE, SAVE & PRINT" — or when viewing an approved log —
          format this review view as a printable A4 sheet with signature blocks at the bottom:
          Prepared by: [Name], Approved by: [Name]. */}
      <header className="border-b border-slate-200 px-5 py-4">
        <span className="text-xs font-bold uppercase tracking-[.14em] text-[#ff4d2f]">Review &amp; Confirmation</span>
        <h2 className="mt-1 text-lg font-bold text-[#152f48]">Watch Log Summary</h2>
        <p className="mt-1 text-sm text-slate-500">
          {vesselName} · {dateLabel} · Watch window: <strong className="font-bold text-slate-700">{windowLabel}</strong> · Read-only
          preview of all entries before final submission.
        </p>
      </header>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[980px] text-left">
          <thead>
            <tr className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-5 py-4">Engine</th>
              <th scope="col" className="px-5 py-4">Status</th>
              <th scope="col" className="px-5 py-4">Start – Stop</th>
              <th scope="col" className="px-5 py-4">Meter Prev (HRS)</th>
              <th scope="col" className="px-5 py-4">Meter Current (HRS)</th>
              <th scope="col" className="px-5 py-4">Watch Hours</th>
              <th scope="col" className="px-5 py-4">R.O.B. Start (L)</th>
              <th scope="col" className="px-5 py-4">R.O.B. Stop (L)</th>
              <th scope="col" className="px-5 py-4">Consumed (L)</th>
              <th scope="col" className="px-5 py-4">RPM</th>
              <th scope="col" className="px-5 py-4">Oil (bar)</th>
              <th scope="col" className="px-5 py-4">Water (°C)</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => {
              const status = STATUS_META[statusOf(log)]
              return (
                <tr key={log.id} className="border-t border-slate-200 text-sm text-slate-900">
                  <td className="px-5 py-4 font-bold">{log.label}</td>
                  <td className="px-5 py-4">
                    <span className={`inline-flex rounded-full px-3 py-1 text-[11px] font-black uppercase tracking-wide ${status.chip}`}>
                      {status.label}
                    </span>
                  </td>
                  <td className="px-5 py-4 font-bold tabular-nums text-slate-700">{windowLabel}</td>
                  <td className="px-5 py-4 tabular-nums">{log.meterPrevious.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}</td>
                  <td className="px-5 py-4 font-bold tabular-nums">{log.meterCurrent.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}</td>
                  <td className="px-5 py-4 font-bold tabular-nums">{watchHoursOf(log).toFixed(1)}</td>
                  <td className="px-5 py-4 tabular-nums">{log.fuelRobStart.toLocaleString()}</td>
                  <td className="px-5 py-4 tabular-nums">{log.fuelRobStop.toLocaleString()}</td>
                  <td className="px-5 py-4 font-bold tabular-nums">{consumedOf(log).toLocaleString()}</td>
                  <td className="px-5 py-4 tabular-nums">{log.rpm.toLocaleString()}</td>
                  <td className="px-5 py-4 tabular-nums">{log.oilPressure.toFixed(1)}</td>
                  <td className="px-5 py-4 tabular-nums">{log.waterTemp}</td>
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            {/* TODO (Validation): cross-check that (WATCH STOP − WATCH START) roughly matches the computed
                "Watch Hours" column (meterCurrent − meterPrevious per engine) and its totals; flag
                discrepancies for review before approval. */}
            <tr className="border-t-2 border-slate-950 bg-slate-50 text-sm font-black uppercase tracking-wide text-[#152f48]">
              <td colSpan={5} className="px-5 py-4 text-right">Totals (all engines)</td>
              <td className="px-5 py-4 tabular-nums">{totalHours.toFixed(1)}</td>
              <td colSpan={2} className="px-5 py-4" />
              <td className="px-5 py-4 tabular-nums">{totalConsumed.toLocaleString()}</td>
              <td colSpan={3} className="px-5 py-4" />
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  )
}

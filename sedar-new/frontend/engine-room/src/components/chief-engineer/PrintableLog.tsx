import { createPortal } from 'react-dom'
import type { EngineLog, WatchLogReviewStatus } from '../../types/engineLog'
import { runStateOf } from '../../utils/engineLog'

interface PrintableLogProps {
  vesselName: string
  date: string
  logs: EngineLog[]
  watchStart: string
  watchStop: string
  preparedBy: string
  approvedBy: string
  status: WatchLogReviewStatus
}

const STATUS_TEXT: Record<WatchLogReviewStatus, string> = {
  draft: 'Draft, not yet submitted',
  returned: 'Returned for correction',
  pending: 'Submitted, waiting for approval',
  approved: 'Approved',
}

const RUN_TEXT = { standby: 'Standby', no_operation: 'No Operation', operated: 'Operated' } as const

const number = (value: number, digits = 0) => value.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })

// Rendered outside the app shell so printing shows only the A4 sheet; print.css hides it on screen.
export function PrintableLog({ vesselName, date, logs, watchStart, watchStop, preparedBy, approvedBy, status }: PrintableLogProps) {
  const dateLabel = new Date(`${date}T00:00:00`).toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' })
  const hoursOf = (log: EngineLog) => Math.max(0, log.meterCurrent - log.meterPrevious)
  const consumedOf = (log: EngineLog) => (runStateOf(log) === 'operated' ? Math.max(0, log.fuelRobStart - log.fuelRobStop) : 0)

  return createPortal(
    <div className="print-sheet" aria-hidden="true">
      <header>
        <img src={`${import.meta.env.BASE_URL}logo.png`} alt="" />
        <div>
          <h1>Daily Engine Monitoring Report</h1>
          <p>
            {vesselName} · {dateLabel} · Watch window {watchStart || '—'} – {watchStop || '—'}
          </p>
          <p className="print-status">{STATUS_TEXT[status]}</p>
        </div>
      </header>

      <table>
        <thead>
          <tr>
            <th>Engine</th>
            <th>Status</th>
            <th>Watch</th>
            <th>Meter prev (h)</th>
            <th>Meter now (h)</th>
            <th>Hours run</th>
            <th>R.O.B. start (L)</th>
            <th>R.O.B. stop (L)</th>
            <th>Consumed (L)</th>
            <th>RPM</th>
            <th>Oil (bar)</th>
            <th>Water (°C)</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => {
            const state = runStateOf(log)
            return (
              <tr key={log.id}>
                <th scope="row">{log.label}</th>
                <td>{RUN_TEXT[state]}</td>
                <td>
                  {state === 'standby' ? '—' : `${watchStart} – ${watchStop || '—'}`}
                </td>
                <td>{number(log.meterPrevious, 1)}</td>
                <td>{number(log.meterCurrent, 1)}</td>
                <td>{number(hoursOf(log), 1)}</td>
                <td>{number(log.fuelRobStart)}</td>
                <td>{number(log.fuelRobStop)}</td>
                <td>{number(consumedOf(log))}</td>
                <td>{number(log.rpm)}</td>
                <td>{number(log.oilPressure, 1)}</td>
                <td>{number(log.waterTemp)}</td>
              </tr>
            )
          })}
        </tbody>
        <tfoot>
          <tr>
            <th colSpan={5}>Totals (all engines)</th>
            <td>{number(logs.reduce((sum, log) => sum + hoursOf(log), 0), 1)}</td>
            <td colSpan={2} />
            <td>{number(logs.reduce((sum, log) => sum + consumedOf(log), 0))}</td>
            <td colSpan={3} />
          </tr>
        </tfoot>
      </table>

      <footer>
        <div>
          <strong>{preparedBy || ' '}</strong>
          <span>Prepared by</span>
        </div>
        <div>
          <strong>{approvedBy || ' '}</strong>
          <span>Approved by (Chief Engineer)</span>
        </div>
      </footer>
    </div>,
    document.body,
  )
}

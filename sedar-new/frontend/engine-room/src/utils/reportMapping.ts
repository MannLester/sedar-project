import type { ApiEngine, ApiLine, ApiReport, ApiTug, LogPayload } from '../api'
import type { EngineLog, EngineTab, WatchWindowLogs } from '../types/engineLog'
import { clockToHours, computeWatchDurationHours, currentClockTime, hoursToClock, roundTo, runStateOf } from './engineLog'

function engineLabel(engine: ApiEngine, tug: ApiTug): string {
  const label = engine.name.startsWith(tug.name) ? engine.name.slice(tug.name.length).trim() : engine.name
  return label || engine.name
}

export function engineTabs(tug: ApiTug): EngineTab[] {
  return tug.engines.map((engine) => ({ id: String(engine.id), label: engineLabel(engine, tug), className: engine.kind }))
}

function standbyLog(engine: ApiEngine, tug: ApiTug, date: string): EngineLog {
  return {
    id: `log-${tug.id}-${engine.id}`,
    engineId: String(engine.id),
    engineClass: engine.kind,
    label: engineLabel(engine, tug),
    date,
    timeStart: null,
    timeStop: null,
    rpm: 0,
    oilPressure: 0,
    waterTemp: 0,
    fuelRobStart: engine.last_fuel_rob,
    fuelRobStop: engine.last_fuel_rob,
    meterPrevious: engine.hours,
    meterCurrent: engine.hours,
    nextPm: engine.next_pm && {
      name: engine.next_pm.name,
      intervalHours: engine.next_pm.interval_hours,
      remainingHours: engine.next_pm.remaining_hours,
    },
  }
}

function savedLog(base: EngineLog, line: ApiLine, posted: boolean): EngineLog {
  const stamp = `${base.date}T00:00:00`
  return {
    ...base,
    timeStart: line.engine_status === 'standby' ? null : stamp,
    timeStop: line.engine_status === 'no_operation' ? stamp : null,
    rpm: line.rpm,
    oilPressure: line.oil_pressure,
    waterTemp: line.water_temp,
    fuelRobStart: line.fuel_rob_start,
    fuelRobStop: line.fuel_rob_stop,
    meterPrevious: line.meter_previous,
    meterCurrent: line.meter_previous + line.hours_run,
    nextPm: base.nextPm && { ...base.nextPm, remainingHours: base.nextPm.remainingHours + (posted ? line.hours_run : 0) },
  }
}

export function windowFromReport(tug: ApiTug, report: ApiReport): WatchWindowLogs {
  const posted = report.state === 'posted'
  return {
    watchStart: hoursToClock(report.watch_start),
    watchStop: hoursToClock(report.watch_stop),
    logs: tug.engines.map((engine) => {
      const line = report.lines.find((candidate) => candidate.equipment_id === engine.id)
      const base = standbyLog(engine, tug, report.date)
      return line ? savedLog(base, line, posted) : base
    }),
  }
}

export function blankWindow(tug: ApiTug, date: string): WatchWindowLogs {
  return { watchStart: currentClockTime(), watchStop: '', logs: tug.engines.map((engine) => standbyLog(engine, tug, date)) }
}

// A stored draft keeps what the crew typed, but the engines' hours and maintenance come from the latest snapshot.
export function refreshDraft(tug: ApiTug, date: string, draft: WatchWindowLogs): WatchWindowLogs {
  return {
    ...draft,
    logs: tug.engines.map((engine) => {
      const fresh = standbyLog(engine, tug, date)
      const typed = draft.logs.find((log) => log.engineId === fresh.engineId)
      return typed ? { ...fresh, ...typed, label: fresh.label, engineClass: fresh.engineClass, meterPrevious: fresh.meterPrevious, nextPm: fresh.nextPm } : fresh
    }),
  }
}

// Hours come only from the watch window, so every engine's meter is derived here and never trusted from the form.
export function withDerivedMeters(window: WatchWindowLogs): WatchWindowLogs {
  const delta = computeWatchDurationHours(window.watchStart, window.watchStop)
  return {
    ...window,
    logs: window.logs.map((log) => ({
      ...log,
      meterCurrent: roundTo(log.meterPrevious + (runStateOf(log) === 'operated' ? (delta ?? 0) : 0), 1),
    })),
  }
}

export function toPayload(tug: ApiTug, date: string, window: WatchWindowLogs, logId: string): LogPayload {
  return {
    log_id: logId,
    tugboat_id: tug.id,
    report_date: date,
    watch_start: clockToHours(window.watchStart),
    watch_stop: clockToHours(window.watchStop || window.watchStart),
    lines: window.logs.map((log) => {
      const state = runStateOf(log)
      return {
        equipment_id: Number(log.engineId),
        engine_status: state,
        rpm: state === 'operated' ? log.rpm : 0,
        oil_pressure: log.oilPressure,
        water_temp: log.waterTemp,
        fuel_rob_start: log.fuelRobStart,
        fuel_rob_stop: state === 'operated' ? log.fuelRobStop : log.fuelRobStart,
      }
    }),
  }
}

// "06:00 - 12:30", as Ed's history lists each watch.
export function timeRangeOf(start: number, stop: number): string {
  return `${hoursToClock(start)} - ${hoursToClock(stop)}`
}

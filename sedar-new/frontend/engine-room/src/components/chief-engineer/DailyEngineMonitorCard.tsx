import { useCallback, useEffect } from 'react'
import { Minus, Plus, Fuel, Clock, Activity, AlertTriangle, ChevronDown } from 'lucide-react'
import { useEngineRoom } from '../../context/engineRoomStore'
import type { ReactNode } from 'react'
import type { EngineLog, EngineTab } from '../../types/engineLog'
import { computeWatchDurationHours, currentClockTime } from '../../utils/engineLog'

interface DailyEngineMonitorCardProps {
  log: EngineLog
  tabs: EngineTab[]
  notice?: ReactNode
  onEngineChange: (engineId: EngineLog['engineId']) => void
  onUpdate: (log: EngineLog) => void
  readOnly?: boolean
  stopError?: boolean
}

interface MetricStepperProps {
  label: string
  unit: string
  value: number
  min: number
  max: number
  step: number
  decimals?: number
  disabled?: boolean
  onChange: (value: number) => void
}

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

const TIME_INPUT_CLS =
  'h-14 w-44 max-w-full rounded-lg border-2 border-slate-300 bg-white px-4 text-xl font-black tabular-nums text-slate-900 outline-none transition focus:border-[#315d82] focus:ring-2 focus:ring-[#315d82]/15 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400'

const STATUS_SELECT_CLS =
  'h-14 w-full cursor-pointer appearance-none rounded-lg border-2 pl-9 pr-9 text-base font-black uppercase tracking-wider transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#ff8b77] disabled:cursor-not-allowed disabled:opacity-60'

const ROW_LABEL_CLS = 'text-[11px] font-extrabold uppercase tracking-[.08em] text-[#5f6873]'

function roundTo(value: number, decimals: number): number {
  const factor = 10 ** decimals
  return Math.round(value * factor) / factor
}

const DONUT_CIRCUMFERENCE = 2 * Math.PI * 34

const PMS_TONES = {
  critical: {
    card: 'border-red-300 bg-red-50 text-red-900',
    track: 'text-red-100',
    ring: 'text-red-600',
    percent: 'text-red-600',
    chip: 'border-red-300 bg-red-100 text-red-700',
    value: 'text-red-700',
    label: 'text-red-700/80',
    helper: 'text-red-800/70',
  },
  warning: {
    card: 'border-amber-300 bg-amber-50 text-amber-900',
    track: 'text-amber-100',
    ring: 'text-amber-500',
    percent: 'text-amber-600',
    chip: 'border-amber-300 bg-amber-100 text-amber-800',
    value: 'text-amber-700',
    label: 'text-amber-700/80',
    helper: 'text-amber-800/70',
  },
  normal: {
    card: 'border-blue-200 bg-blue-50 text-blue-900',
    track: 'text-blue-100',
    ring: 'text-blue-600',
    percent: 'text-blue-600',
    chip: 'border-blue-300 bg-blue-100 text-blue-700',
    value: 'text-blue-900',
    label: 'text-blue-700/70',
    helper: 'text-blue-800/70',
  },
} as const

type PmsTone = keyof typeof PMS_TONES

const STATUS_OPTIONS = [
  { id: 'operated', label: 'Operated', bg: 'bg-green-100', text: 'text-green-800', edge: 'border-green-300', hover: 'hover:bg-green-200' },
  { id: 'no-operation', label: 'No Operation', bg: 'bg-amber-100', text: 'text-amber-800', edge: 'border-amber-300', hover: 'hover:bg-amber-200' },
  { id: 'standby', label: 'Standby', bg: 'bg-slate-100', text: 'text-slate-700', edge: 'border-slate-300', hover: 'hover:bg-slate-200' },
] as const

type EngineStatus = (typeof STATUS_OPTIONS)[number]['id']

function MetricStepper({ label, unit, value, min, max, step, decimals = 0, disabled = false, onChange }: MetricStepperProps) {
  const bump = (direction: 1 | -1) => {
    onChange(roundTo(clamp(value + step * direction, min, max), decimals))
  }

  return (
    <div className="flex h-full flex-col rounded-lg border border-[#d4d4d4] bg-white p-3">
      <span className="text-[10px] font-bold uppercase tracking-[.08em] text-[#5f6873]">{label}</span>
      <div className="mt-3 flex flex-row items-stretch overflow-hidden rounded-lg border border-slate-200 bg-white">
        <button
          type="button"
          aria-label={`Decrease ${label}`}
          onClick={() => bump(-1)}
          disabled={disabled}
          className="flex w-16 items-center justify-center bg-slate-50 text-slate-700 transition-colors hover:bg-slate-100 active:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Minus size={24} strokeWidth={3} />
        </button>
        <div className="flex min-w-0 flex-1 flex-col items-center justify-center border-x border-slate-200 p-3 focus-within:border-[#4b718f]">
          <input
            type="number"
            inputMode="decimal"
            aria-label={label}
            min={min}
            max={max}
            step={step}
            value={value}
            disabled={disabled}
            onChange={(event) => {
              const next = Number(event.target.value)
              onChange(Number.isFinite(next) && next >= 0 ? next : 0)
            }}
            className="no-number-spinner w-full bg-transparent text-center text-3xl font-black tabular-nums leading-none text-[#111820] outline-none disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
          />
          <span className="mt-1 text-[10px] font-bold uppercase tracking-widest text-[#7c8994]">{unit}</span>
        </div>
        <button
          type="button"
          aria-label={`Increase ${label}`}
          onClick={() => bump(1)}
          disabled={disabled}
          className="flex w-16 items-center justify-center bg-slate-50 text-slate-700 transition-colors hover:bg-slate-100 active:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus size={24} strokeWidth={3} />
        </button>
      </div>
    </div>
  )
}

export function DailyEngineMonitorCard({ log, tabs, notice, onEngineChange, onUpdate, readOnly = false, stopError = false }: DailyEngineMonitorCardProps) {
  const { watchStart, watchStop, setWatchStart, setWatchStop } = useEngineRoom()
  const isRunning = Boolean(log.timeStart) && !log.timeStop
  const hasStarted = Boolean(log.timeStart)
  const consumption = Math.max(0, log.fuelRobStart - log.fuelRobStop)

  const activeStatus: EngineStatus = isRunning ? 'operated' : hasStarted ? 'no-operation' : 'standby'
  const activeStatusOption = STATUS_OPTIONS.find((option) => option.id === activeStatus) ?? STATUS_OPTIONS[0]
  const isNoOperation = activeStatus === 'no-operation'

  // Strict auto-calculation: hours run this watch come purely from WATCH START → WATCH STOP.
  // 0 while NO OPERATION · null while the times are incomplete · otherwise decimal hours (overnight included).
  const watchDelta = activeStatus === 'no-operation' ? 0 : computeWatchDurationHours(watchStart, watchStop)
  // Current Meter = Previous + delta; null until both times exist, so the field falls back to the previous reading.
  const derivedMeter = watchDelta === null ? null : roundTo(log.meterPrevious + watchDelta, 1)
  const displayMeter = derivedMeter ?? log.meterPrevious
  // Derived from the rounded meter so "Hours for this Watch" and the meter card can never disagree.
  const watchHours = derivedMeter === null ? 0 : roundTo(derivedMeter - log.meterPrevious, 1)

  // Planned Maintenance comes from the engine's nearest PM Task; its remaining hours count down with this watch.
  const pm = log.nextPm
  const pmIntervalHours = pm?.intervalHours ?? 0
  const pmRemaining = pm ? Math.max(0, roundTo(pm.remainingHours - watchHours, 1)) : 0
  const sinceService = pm ? Math.max(0, roundTo(pmIntervalHours - pmRemaining, 1)) : 0
  const pmProgress = pm && pmIntervalHours ? clamp((sinceService / pmIntervalHours) * 100, 0, 100) : 0
  const pmTone: PmsTone = pmRemaining < 10 ? 'critical' : pmRemaining < 50 ? 'warning' : 'normal'
  const tone = PMS_TONES[pmTone]

  const bumpRobStart = (direction: 1 | -1) => {
    onUpdate({ ...log, fuelRobStart: clamp(log.fuelRobStart + 10 * direction, 0, 999999) })
  }

  const bumpRobStop = (direction: 1 | -1) => {
    onUpdate({ ...log, fuelRobStop: clamp(log.fuelRobStop + 10 * direction, 0, 999999) })
  }

  const selectStatus = useCallback(
    (next: EngineStatus) => {
      if (next === activeStatus) return
      const stamp = new Date().toISOString()
      if (next === 'no-operation') {
        // NO OPERATION enforces zero consumption: ROB stop = ROB start, rpm 0. The meter follows
        // automatically through the reconciliation effect below (delta 0 ⇒ meter = previous).
        // The watch window resets to the current wall-clock time with STOP pinned to START, so the
        // duration is 0 by construction — both stay editable, see the keep-stop-matched effect.
        const clock = currentClockTime()
        onUpdate({
          ...log,
          timeStart: log.timeStart ?? stamp,
          timeStop: stamp,
          fuelRobStop: log.fuelRobStart,
          rpm: 0,
        })
        setWatchStart(clock)
        setWatchStop(clock)
      } else if (next === 'operated') {
        onUpdate({ ...log, timeStart: log.timeStart ?? stamp, timeStop: null })
      } else onUpdate({ ...log, timeStart: null, timeStop: null })
    },
    [activeStatus, log, onUpdate, setWatchStart, setWatchStop],
  )

  // Single owner of the auto-derived fields: mirror the computed meter (keeps the Review table and the
  // PMS card in agreement) and, under NO OPERATION, keep ROB STOP = ROB START so Fuel Consumed reads 0.
  // One effect (not two) so two onUpdate calls can never clobber each other's {...log} snapshot.
  // Equality guards make it loop-free; review mode never writes.
  useEffect(() => {
    if (readOnly) return
    const next = { ...log }
    let changed = false
    if (derivedMeter !== null && log.meterCurrent !== derivedMeter) {
      next.meterCurrent = derivedMeter
      changed = true
    }
    if (isNoOperation && log.fuelRobStop !== log.fuelRobStart) {
      next.fuelRobStop = log.fuelRobStart
      changed = true
    }
    if (changed) onUpdate(next)
  }, [derivedMeter, isNoOperation, log, onUpdate, readOnly])

  // While NO OPERATION, STOP always mirrors START (duration 0 by construction). The equality guard
  // keeps it loop-free; it also repairs logs that open as NO OPERATION with an empty stop time.
  useEffect(() => {
    if (readOnly || !isNoOperation) return
    if (watchStop === watchStart) return
    setWatchStop(watchStart)
  }, [isNoOperation, readOnly, watchStart, watchStop, setWatchStop])

  return (
    <section className="tech-panel tech-console" aria-label="Daily Engine Monitor">
      <div
        className="profile-tabs shrink-0"
        role="tablist"
        aria-label="Engine selector"
        style={{ borderTop: 'none', borderLeft: 'none', borderRight: 'none' }}
      >
        {tabs.map((tab) => {
          const active = tab.id === log.engineId
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => onEngineChange(tab.id)}
              className={active ? 'active flex flex-col items-center justify-center' : 'flex flex-col items-center justify-center'}
            >
              {tab.label}
              <span className="text-[9px] font-semibold opacity-70">{tab.className === 'main' ? 'MAIN' : 'AUX'}</span>
            </button>
          )
        })}
      </div>

      <div className="tech-console-body flex flex-col p-4 sm:p-5">
        {notice && <div className="mb-4 grid gap-3">{notice}</div>}
        <div>
          <span className="mb-4 flex items-center gap-2">
            <Clock size={16} className="text-[#ff4d2f]" aria-hidden="true" />
            <span className="text-[13px] font-extrabold uppercase tracking-[.1em] text-[#152f48]">Watch Timeline</span>
          </span>

          <div className="flex flex-wrap items-end gap-4">
            <label className="grid w-[240px] shrink-0 gap-1">
              <span className={ROW_LABEL_CLS}>Engine Status</span>
              <div className={`relative ${activeStatusOption.text}`}>
                <span
                  className={`pointer-events-none absolute left-3.5 top-1/2 size-3 -translate-y-1/2 rounded-full bg-current ${isRunning ? 'animate-pulse' : ''}`}
                  aria-hidden="true"
                />
                <select
                  aria-label="Engine status"
                  value={activeStatus}
                  disabled={readOnly}
                  onChange={(event) => selectStatus(event.target.value as EngineStatus)}
                  className={`${STATUS_SELECT_CLS} ${activeStatusOption.bg} ${activeStatusOption.text} ${activeStatusOption.edge} ${activeStatusOption.hover}`}
                >
                  {STATUS_OPTIONS.map((option) => (
                    <option key={option.id} value={option.id} className={`${option.bg} ${option.text}`}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <ChevronDown size={18} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 opacity-70" aria-hidden="true" />
              </div>
            </label>

            <label className="grid gap-1">
              <span className={ROW_LABEL_CLS}>Watch Start Time</span>
              <input
                type="time"
                aria-label="Watch start time"
                value={watchStart}
                disabled={readOnly}
                onChange={(event) => setWatchStart(event.target.value)}
                className={TIME_INPUT_CLS}
              />
            </label>
            <label className="grid gap-1">
              <span className={ROW_LABEL_CLS}>Watch Stop Time (Cut-off)</span>
              <input
                type="time"
                aria-label="Watch stop time"
                value={watchStop}
                disabled={readOnly || isNoOperation}
                onChange={(event) => setWatchStop(event.target.value)}
                className={`${TIME_INPUT_CLS}${stopError && !watchStop ? ' border-red-400 focus:border-red-400 focus:ring-red-200' : ''}`}
              />
              {stopError && !watchStop && (
                <span className="text-[10px] font-bold text-red-600">A stop / cut-off time is required before review.</span>
              )}
            </label>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex h-full flex-col rounded-lg border border-[#d4d4d4] bg-white p-3">
              <span className="text-[10px] font-bold uppercase tracking-[.08em] text-[#5f6873]">Previous Meter Reading</span>
              <div className="mt-3 flex min-h-14 flex-1 flex-col items-center justify-center rounded-md border border-[#cdd3d8] bg-[#f7f9fa] px-1 py-1">
                <span className="truncate text-3xl font-black tabular-nums leading-none text-[#111820]">
                  {log.meterPrevious.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                </span>
                <span className="mt-1 text-[10px] font-bold uppercase tracking-widest text-[#7c8994]">HRS</span>
              </div>
            </div>

            <div className="flex h-full flex-col rounded-lg border border-[#d4d4d4] bg-white p-3">
              <span className="text-[10px] font-bold uppercase tracking-[.08em] text-[#5f6873]">Current Meter Reading</span>
              <div className="mt-3 flex min-h-14 flex-1 flex-col items-center justify-center rounded-md border border-[#cdd3d8] bg-[#f7f9fa] px-1 py-1">
                <input
                  type="text"
                  inputMode="decimal"
                  readOnly
                  tabIndex={-1}
                  aria-label="Current meter reading (auto-computed from watch times)"
                  value={displayMeter.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                  className="no-number-spinner w-full cursor-not-allowed bg-transparent text-center text-3xl font-black tabular-nums leading-none text-[#111820] outline-none focus:outline-none"
                />
                <span className="mt-1 text-[10px] font-bold uppercase tracking-widest text-[#7c8994]">HRS</span>
              </div>
            </div>

            <div className="flex h-full flex-col rounded-lg border border-[#a8d9bc] bg-green-50 p-3 text-green-800">
              <span className="text-[10px] font-bold uppercase tracking-[.08em]">Hours for this Watch</span>
              <div className="mt-3 flex min-h-14 flex-1 flex-col items-center justify-center rounded-md border border-green-200 bg-white/60 px-1 py-1">
                <strong className="text-3xl font-black tabular-nums leading-none">{watchHours.toFixed(1)}</strong>
                <span className="mt-1 text-[10px] font-bold uppercase tracking-widest text-green-700/70">HRS</span>
              </div>
            </div>

            {pm ? (
              <div className={`flex h-full flex-col rounded-lg border p-3 ${tone.card}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-[.08em]">Next Maintenance</span>
                  {pmTone === 'critical' && (
                    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${tone.chip}`}>
                      <AlertTriangle size={10} aria-hidden="true" /> Critical
                    </span>
                  )}
                </div>
                <div className="mt-3 flex flex-row items-center gap-3.5">
                  <div
                    role="progressbar"
                    aria-label={`${pm.name} progress`}
                    aria-valuenow={Math.round(pmProgress)}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    className="relative size-20 shrink-0"
                  >
                    <svg viewBox="0 0 80 80" className="size-20 -rotate-90" aria-hidden="true">
                      <circle cx="40" cy="40" r="34" fill="none" strokeWidth="10" className={`stroke-current ${tone.track}`} />
                      <circle
                        cx="40"
                        cy="40"
                        r="34"
                        fill="none"
                        strokeWidth="10"
                        strokeLinecap="round"
                        className={`stroke-current transition-[stroke-dashoffset] duration-500 ${tone.ring}`}
                        strokeDasharray={DONUT_CIRCUMFERENCE}
                        strokeDashoffset={DONUT_CIRCUMFERENCE * (1 - pmProgress / 100)}
                      />
                    </svg>
                    <span className={`absolute inset-0 grid place-items-center text-[11px] font-black tabular-nums ${tone.percent}`}>
                      {Math.round(pmProgress)}%
                    </span>
                  </div>
                  <div className="flex min-w-0 flex-1 flex-col">
                    <strong className={`text-5xl font-black tabular-nums leading-none ${tone.value}`}>
                      {pmRemaining.toFixed(1)}
                    </strong>
                    <span className={`mt-1 text-[10px] font-bold uppercase tracking-widest ${tone.label}`}>Hrs to {pm.name}</span>
                    <span className="mt-2 text-[10px] text-slate-500">
                      Elapsed Since Last Service: {sinceService.toFixed(1)} HRS
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex h-full flex-col rounded-lg border border-[#d4d4d4] bg-white p-3 text-slate-500">
                <span className="text-[10px] font-bold uppercase tracking-[.08em]">Next Maintenance</span>
                <span className="mt-3 text-sm">No Planned Maintenance Task is set for this engine.</span>
              </div>
            )}
          </div>
        </div>

        <hr className="my-8 border-slate-200" />

        <div>
          <span className="mb-4 flex items-center gap-2">
            <Fuel size={16} className="text-[#ff4d2f]" aria-hidden="true" />
            <span className="text-[13px] font-extrabold uppercase tracking-[.1em] text-[#152f48]">Fuel R.O.B. (Remaining On Board)</span>
          </span>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="flex h-full flex-col rounded-lg border border-[#d4d4d4] bg-white p-3">
              <span className="text-[10px] font-bold uppercase tracking-[.08em] text-[#5f6873]">ROB Start (L)</span>
              <div className="mt-3 flex flex-row items-stretch overflow-hidden rounded-lg border border-slate-200 bg-white">
                <button
                  type="button"
                  aria-label="Decrease ROB start"
                  onClick={() => bumpRobStart(-1)}
                  disabled={isNoOperation || readOnly}
                  className="flex w-16 items-center justify-center bg-slate-50 text-slate-700 transition-colors hover:bg-slate-100 active:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Minus size={24} strokeWidth={3} />
                </button>
                <div className="flex min-w-0 flex-1 flex-col items-center justify-center border-x border-slate-200 p-3 focus-within:border-[#4b718f]">
                  <input
                    type="number"
                    inputMode="numeric"
                    min={0}
                    step={10}
                    aria-label="ROB Start"
                    value={log.fuelRobStart}
                    disabled={isNoOperation || readOnly}
                    onChange={(event) => {
                      const next = Number(event.target.value)
                      onUpdate({ ...log, fuelRobStart: Number.isFinite(next) && next >= 0 ? next : 0 })
                    }}
                    className="no-number-spinner w-full bg-transparent text-center text-3xl font-black tabular-nums leading-none text-[#111820] outline-none disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                  />
                  <span className="mt-1 text-[10px] font-bold uppercase tracking-widest text-[#7c8994]">L</span>
                </div>
                <button
                  type="button"
                  aria-label="Increase ROB start"
                  onClick={() => bumpRobStart(1)}
                  disabled={isNoOperation || readOnly}
                  className="flex w-16 items-center justify-center bg-slate-50 text-slate-700 transition-colors hover:bg-slate-100 active:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Plus size={24} strokeWidth={3} />
                </button>
              </div>
            </div>

            <div className="flex h-full flex-col rounded-lg border border-[#d4d4d4] bg-white p-3">
              <span className="text-[10px] font-bold uppercase tracking-[.08em] text-[#5f6873]">ROB Stop (L)</span>
              <div className="mt-3 flex flex-row items-stretch overflow-hidden rounded-lg border border-slate-200 bg-white">
                <button
                  type="button"
                  aria-label="Decrease ROB stop"
                  onClick={() => bumpRobStop(-1)}
                  disabled={isNoOperation || readOnly}
                  className="flex w-16 items-center justify-center bg-slate-50 text-slate-700 transition-colors hover:bg-slate-100 active:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Minus size={24} strokeWidth={3} />
                </button>
                <div className="flex min-w-0 flex-1 flex-col items-center justify-center border-x border-slate-200 p-3 focus-within:border-[#4b718f]">
                  <input
                    type="number"
                    inputMode="numeric"
                    min={0}
                    step={10}
                    aria-label="ROB Stop"
                    value={log.fuelRobStop}
                    disabled={isNoOperation || readOnly}
                    onChange={(event) => {
                      const next = Number(event.target.value)
                      onUpdate({ ...log, fuelRobStop: Number.isFinite(next) && next >= 0 ? next : 0 })
                    }}
                    className="no-number-spinner w-full bg-transparent text-center text-3xl font-black tabular-nums leading-none text-[#111820] outline-none disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                  />
                  <span className="mt-1 text-[10px] font-bold uppercase tracking-widest text-[#7c8994]">L</span>
                </div>
                <button
                  type="button"
                  aria-label="Increase ROB stop"
                  onClick={() => bumpRobStop(1)}
                  disabled={isNoOperation || readOnly}
                  className="flex w-16 items-center justify-center bg-slate-50 text-slate-700 transition-colors hover:bg-slate-100 active:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Plus size={24} strokeWidth={3} />
                </button>
              </div>
            </div>

            <div className="flex h-full flex-col rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-900">
              <span className="text-[10px] font-bold uppercase tracking-[.08em]">Fuel Consumed</span>
              <div className="mt-3 flex min-h-14 flex-1 flex-col items-center justify-center rounded-md border border-amber-200 bg-white/60 px-1 py-1">
                <strong className="text-3xl font-black tabular-nums">{consumption.toLocaleString()}</strong>
                <span className="mt-1 text-[10px] font-bold uppercase tracking-widest text-amber-700/70">L</span>
              </div>
            </div>
          </div>
        </div>

        <hr className="my-8 border-slate-200" />

        <div>
          <span className="mb-4 flex items-center gap-2">
            <Activity size={16} className="text-[#ff4d2f]" aria-hidden="true" />
            <span className="text-[13px] font-extrabold uppercase tracking-[.1em] text-[#152f48]">Engine Parameters</span>
          </span>
          <div className="grid gap-3 md:grid-cols-3">
            <MetricStepper label="RPM" unit="rev/min" value={log.rpm} min={0} max={1000} step={5} disabled={isNoOperation || readOnly} onChange={(rpm) => onUpdate({ ...log, rpm })} />
            <MetricStepper label="Oil Pressure" unit="bar" value={log.oilPressure} min={0} max={8} step={0.1} decimals={1} disabled={readOnly} onChange={(oilPressure) => onUpdate({ ...log, oilPressure })} />
            <MetricStepper label="Water Temp" unit="°C" value={log.waterTemp} min={0} max={110} step={1} disabled={readOnly} onChange={(waterTemp) => onUpdate({ ...log, waterTemp })} />
          </div>
        </div>
      </div>
    </section>
  )
}

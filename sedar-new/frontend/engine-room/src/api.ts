export type EngineStatus = 'operated' | 'no_operation' | 'standby'

export interface ApiLine {
  equipment_id: number
  engine_status: EngineStatus
  hours_run: number
  rpm: number
  oil_pressure: number
  water_temp: number
  fuel_rob_start: number
  fuel_rob_stop: number
  fuel_consumed: number
  meter_previous: number
}

export interface ApiReport {
  id: number
  log_id: string
  date: string
  watch_start: number
  watch_stop: number
  state: 'draft' | 'submitted' | 'posted'
  return_reason: string
  prepared_by: string
  approved_by: string
  hours: number
  fuel: number
  lines: ApiLine[]
}

export interface ApiEngine {
  id: number
  name: string
  kind: 'main' | 'auxiliary'
  hours: number
  last_fuel_rob: number
  next_pm: { name: string; interval_hours: number; remaining_hours: number } | null
}

export interface ApiTug {
  id: number
  name: string
  engines: ApiEngine[]
  reports: ApiReport[]
  open_pm_tasks: number
}

export interface Snapshot {
  generated_at: string
  user: string
  can_approve: boolean
  tugs: ApiTug[]
}

export type UploadLine = Pick<
  ApiLine,
  'equipment_id' | 'engine_status' | 'rpm' | 'oil_pressure' | 'water_temp' | 'fuel_rob_start' | 'fuel_rob_stop'
>

export interface LogPayload {
  log_id: string
  tugboat_id: number
  report_date: string
  watch_start: number
  watch_stop: number
  lines: UploadLine[]
}

export interface QueueItem extends LogPayload {
  client_id: string
  kind: 'report'
  label: string
  error?: string
}

export interface SyncResult {
  client_id: string
  ok: boolean
  message: string
}

export type ReviewRequest =
  | ({ action: 'approve' } & LogPayload)
  | { action: 'approve'; log_id: string }
  | { action: 'return'; log_id: string; reason: string }

export class RpcError extends Error {
  expired: boolean
  unreachable: boolean

  constructor(message: string, expired = false, unreachable = false) {
    super(message)
    this.expired = expired
    this.unreachable = unreachable
  }
}

export async function rpc<T>(path: string, params: object): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params }),
    })
  } catch {
    throw new RpcError('Cannot reach the server.', false, true)
  }
  const body = await response.json()
  if (body.error) {
    const name: string = body.error.data?.name ?? ''
    throw new RpcError(body.error.data?.message || body.error.message, name.includes('SessionExpired'))
  }
  return body.result as T
}

export const fetchSnapshot = () => rpc<Snapshot>('/sedar/engine-room/snapshot', {})
export const syncQueue = (items: QueueItem[]) =>
  rpc<SyncResult[]>('/sedar/ship-log/sync', {
    items: items.map((item) => Object.fromEntries(Object.entries(item).filter(([key]) => key !== 'label' && key !== 'error'))),
  })
export const reviewReport = (item: ReviewRequest) => rpc<ApiReport>('/sedar/engine-room/review', { item })

export function readStored<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(`engine-room:${key}`)
    return raw === null ? fallback : (JSON.parse(raw) as T)
  } catch {
    return fallback
  }
}

export function writeStored(key: string, value: unknown): void {
  try {
    localStorage.setItem(`engine-room:${key}`, JSON.stringify(value))
  } catch {
    // storage full or blocked: the page still works, it just cannot survive a reload
  }
}

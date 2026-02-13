/** API мини-аппа: эндпоинты, заголовки, запросы. */

export const API = {
  me: '/api/miniapp/me',
  slots: (date: string) => `/api/miniapp/slots?date=${date}`,
  myAppointments: '/api/miniapp/appointments/my',
  createAppointment: '/api/miniapp/appointments',
  cancelAppointment: (id: number) => `/api/miniapp/appointments/${id}/cancel`,
  rescheduleAppointment: (id: number) => `/api/miniapp/appointments/${id}/reschedule`,
  masterAppointments: (date: string, dateTo?: string) =>
    dateTo
      ? `/api/miniapp/master/appointments?date=${date}&date_to=${dateTo}`
      : `/api/miniapp/master/appointments?date=${date}`,
  masterClients: '/api/miniapp/master/clients',
  masterClient: (id: number) => `/api/miniapp/master/clients/${id}`,
  masterSettings: '/api/miniapp/master/settings',
  masterBlockedSlots: (dateFrom: string, dateTo: string) =>
    `/api/miniapp/master/blocked-slots?date_from=${dateFrom}&date_to=${dateTo}`,
  masterBlockedSlotsPost: '/api/miniapp/master/blocked-slots',
  masterBlockedSlot: (id: number) => `/api/miniapp/master/blocked-slots/${id}`,
  masterRescheduleAppointment: (id: number) => `/api/miniapp/master/appointments/${id}`,
}

export type Slot = { start_utc_iso: string }
export type Appointment = {
  id: number
  label: string
  datetime_start_utc: string
  status: string
  source: string
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData?: string
        initDataUnsafe?: { user?: { id: number; first_name?: string; last_name?: string } }
        openLink?: (url: string) => void
      }
    }
  }
}

export function getTelegramUser(): { id: number; name: string } | null {
  const user = window.Telegram?.WebApp?.initDataUnsafe?.user
  if (!user?.id) return null
  const name = [user.first_name, user.last_name].filter(Boolean).join(' ') || 'Клиент'
  return { id: user.id, name }
}

/** Есть ли данные для идентификации (initData или telegram_id в query/user). */
export function hasAuthForRequest(): boolean {
  if (window.Telegram?.WebApp?.initData) return true
  if (getTelegramUser()?.id) return true
  if (new URLSearchParams(window.location.search).get('telegram_id')) return true
  return false
}

export function authHeaders(): HeadersInit {
  const h: HeadersInit = { 'Content-Type': 'application/json' }
  const initData = window.Telegram?.WebApp?.initData
  if (initData) (h as Record<string, string>)['X-Telegram-Init-Data'] = initData
  const user = getTelegramUser()
  if (user) (h as Record<string, string>)['X-Telegram-Id'] = String(user.id)
  else {
    const q = new URLSearchParams(window.location.search).get('telegram_id')
    if (q) (h as Record<string, string>)['X-Telegram-Id'] = q
  }
  return h
}

const ERROR_CODE_MESSAGES: Record<string, string> = {
  slot_busy: 'Это время уже занято, выберите другое.',
  booking_disabled: 'Запись временно отключена.',
  client_blocked: 'Онлайн-запись для вас недоступна.',
  invalid_init_data: 'Не удалось загрузить. Нажмите «Повторить».',
  missing_telegram_id: 'Не удалось загрузить. Нажмите «Повторить».',
  invalid_telegram_id: 'Не удалось загрузить. Нажмите «Повторить».',
}

const SERVER_ERROR_MESSAGE = 'Временная ошибка. Попробуйте позже.'
const TIMEOUT_MESSAGE = 'Время ожидания истекло. Попробуйте ещё раз.'
const FETCH_TIMEOUT_MS = 15000

export function normalizeApiError(text: string): string {
  if (text.trimStart().toLowerCase().startsWith('<!doctype') || text.includes('</html>'))
    return SERVER_ERROR_MESSAGE
  const lower = text.toLowerCase()
  if (/500|502|503|internal server error|got itself in trouble/.test(lower))
    return SERVER_ERROR_MESSAGE
  if (/telegram id is required|x-telegram-id header/.test(lower))
    return ERROR_CODE_MESSAGES.missing_telegram_id
  try {
    const j = JSON.parse(text) as { error?: string; detail?: string; message?: string; code?: string }
    const code = j.code
    if (code && ERROR_CODE_MESSAGES[code] !== undefined) return ERROR_CODE_MESSAGES[code]
    const result = j.error ?? j.detail ?? j.message ?? text
    if (typeof result === 'string' && /telegram id is required|x-telegram-id header/.test(result.toLowerCase()))
      return ERROR_CODE_MESSAGES.missing_telegram_id
    return result
  } catch {
    return text
  }
}

async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number
): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const r = await fetch(url, { ...init, signal: controller.signal })
    clearTimeout(timeoutId)
    return r
  } catch (e) {
    clearTimeout(timeoutId)
    if (e instanceof Error && e.name === 'AbortError') throw new Error(TIMEOUT_MESSAGE)
    throw e
  }
}

async function fetchWithRetry(
  url: string,
  init: RequestInit,
  retries = 3,
  timeoutMs = FETCH_TIMEOUT_MS
): Promise<Response> {
  try {
    const r = await fetchWithTimeout(url, init, timeoutMs)
    if (r.ok || r.status < 500 || retries === 0) return r
    await new Promise((resolve) => setTimeout(resolve, 600))
    return fetchWithRetry(url, init, retries - 1, timeoutMs)
  } catch (e) {
    if (retries === 0) throw e
    await new Promise((resolve) => setTimeout(resolve, 600))
    return fetchWithRetry(url, init, retries - 1, timeoutMs)
  }
}

export async function apiGet<T>(url: string): Promise<T> {
  const r = await fetchWithRetry(url, { headers: authHeaders() }, 3)
  const text = await r.text()
  if (!r.ok) throw new Error(normalizeApiError(text))
  try {
    return JSON.parse(text) as T
  } catch {
    throw new Error(normalizeApiError(text))
  }
}

export async function apiPost<T>(url: string, body?: object): Promise<T> {
  const r = await fetchWithRetry(
    url,
    {
      method: 'POST',
      headers: authHeaders(),
      body: body ? JSON.stringify(body) : undefined,
    },
    2
  )
  const text = await r.text()
  if (!r.ok) throw new Error(normalizeApiError(text))
  try {
    return JSON.parse(text) as T
  } catch {
    throw new Error(normalizeApiError(text))
  }
}

export async function apiPatch<T>(url: string, body: object): Promise<T> {
  const r = await fetchWithRetry(
    url,
    {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify(body),
    },
    2
  )
  const text = await r.text()
  if (!r.ok) throw new Error(normalizeApiError(text))
  try {
    return JSON.parse(text) as T
  } catch {
    throw new Error(normalizeApiError(text))
  }
}

/** API мини-аппа: эндпоинты, заголовки, запросы. */

export const API = {
  me: '/api/miniapp/me',
  slots: (date: string) => `/api/miniapp/slots?date=${date}`,
  myAppointments: '/api/miniapp/appointments/my',
  createAppointment: '/api/miniapp/appointments',
  cancelAppointment: (id: number) => `/api/miniapp/appointments/${id}/cancel`,
  rescheduleAppointment: (id: number) => `/api/miniapp/appointments/${id}/reschedule`,
  masterAppointments: (date: string) => `/api/miniapp/master/appointments?date=${date}`,
  masterClients: '/api/miniapp/master/clients',
  masterClient: (id: number) => `/api/miniapp/master/clients/${id}`,
  masterSettings: '/api/miniapp/master/settings',
  masterBlockedSlots: (dateFrom: string, dateTo: string) =>
    `/api/miniapp/master/blocked-slots?date_from=${dateFrom}&date_to=${dateTo}`,
  masterBlockedSlotsPost: '/api/miniapp/master/blocked-slots',
  masterBlockedSlot: (id: number) => `/api/miniapp/master/blocked-slots/${id}`,
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
  invalid_init_data: 'Откройте приложение в Telegram.',
}

export function normalizeApiError(text: string): string {
  if (text.trimStart().toLowerCase().startsWith('<!doctype') || text.includes('</html>'))
    return 'Сервер недоступен. Проверьте подключение.'
  try {
    const j = JSON.parse(text) as { error?: string; detail?: string; message?: string; code?: string }
    const code = j.code
    if (code && ERROR_CODE_MESSAGES[code]) return ERROR_CODE_MESSAGES[code]
    return j.error ?? j.detail ?? j.message ?? text
  } catch {
    return text
  }
}

export async function apiGet<T>(url: string): Promise<T> {
  const r = await fetch(url, { headers: authHeaders() })
  const text = await r.text()
  if (!r.ok) throw new Error(normalizeApiError(text))
  try {
    return JSON.parse(text) as T
  } catch {
    throw new Error(normalizeApiError(text))
  }
}

export async function apiPost<T>(url: string, body?: object): Promise<T> {
  const r = await fetch(url, {
    method: 'POST',
    headers: authHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  })
  const text = await r.text()
  if (!r.ok) throw new Error(normalizeApiError(text))
  try {
    return JSON.parse(text) as T
  } catch {
    throw new Error(normalizeApiError(text))
  }
}

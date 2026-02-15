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

/** Цвета темы Telegram (см. ThemeParams). */
export type TelegramThemeParams = {
  bg_color?: string
  text_color?: string
  hint_color?: string
  link_color?: string
  button_color?: string
  button_text_color?: string
  secondary_bg_color?: string
  header_bg_color?: string
}

/** Кнопка «Назад» в шапке Mini App (BackButton). */
export interface TelegramBackButton {
  isVisible: boolean
  onClick: (callback: () => void) => TelegramBackButton
  offClick: (callback: () => void) => TelegramBackButton
  show: () => TelegramBackButton
  hide: () => TelegramBackButton
}

/** Нижняя кнопка: main или secondary (BottomButton). */
export interface TelegramBottomButton {
  readonly type: 'main' | 'secondary'
  text: string
  color: string
  textColor: string
  isVisible: boolean
  isActive: boolean
  hasShineEffect?: boolean
  position?: 'left' | 'right' | 'top' | 'bottom'
  readonly isProgressVisible: boolean
  setText: (text: string) => TelegramBottomButton
  onClick: (callback: () => void) => TelegramBottomButton
  offClick: (callback: () => void) => TelegramBottomButton
  show: () => TelegramBottomButton
  hide: () => TelegramBottomButton
  enable: () => TelegramBottomButton
  disable: () => TelegramBottomButton
  showProgress: (leaveActive?: boolean) => TelegramBottomButton
  hideProgress: () => TelegramBottomButton
  setParams: (params: Partial<{ text: string; color: string; text_color: string; has_shine_effect: boolean; position: string; is_active: boolean; is_visible: boolean }>) => TelegramBottomButton
}

/** Параметры запуска DeviceOrientation. */
export interface TelegramDeviceOrientationStartParams {
  refresh_rate?: number
  need_absolute?: boolean
}

/** Ориентация устройства (DeviceOrientation). */
export interface TelegramDeviceOrientation {
  isStarted: boolean
  absolute: boolean
  alpha: number
  beta: number
  gamma: number
  start: (params?: TelegramDeviceOrientationStartParams, callback?: (success: boolean) => void) => TelegramDeviceOrientation
  stop: (callback?: (success: boolean) => void) => TelegramDeviceOrientation
}

/** Тактильная отдача (HapticFeedback). */
export interface TelegramHapticFeedback {
  impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => TelegramHapticFeedback
  notificationOccurred: (type: 'error' | 'success' | 'warning') => TelegramHapticFeedback
  selectionChanged: () => TelegramHapticFeedback
}

/** Параметры emoji-статуса (EmojiStatusParams). */
export interface TelegramEmojiStatusParams {
  duration?: number
}

/** Кнопка в нативном попапе (PopupButton). */
export interface TelegramPopupButton {
  id?: string
  type?: 'default' | 'ok' | 'close' | 'cancel' | 'destructive'
  text?: string
}

/** Пользователь Mini App (WebAppUser). */
export interface TelegramWebAppUser {
  id: number
  is_bot?: boolean
  first_name: string
  last_name?: string
  username?: string
  language_code?: string
  is_premium?: boolean
  added_to_attachment_menu?: boolean
  allows_write_to_pm?: boolean
  photo_url?: string
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData?: string
        initDataUnsafe?: { user?: TelegramWebAppUser }
        themeParams?: TelegramThemeParams
        colorScheme?: 'light' | 'dark'
        BackButton?: TelegramBackButton
        MainButton?: TelegramBottomButton
        SecondaryButton?: TelegramBottomButton
        HapticFeedback?: TelegramHapticFeedback
        DeviceOrientation?: TelegramDeviceOrientation
        openLink?: (url: string) => void
        openTelegramLink?: (url: string) => void
        ready?: () => void
        expand?: () => void
        setHeaderColor?: (color: string) => void
        setBackgroundColor?: (color: string) => void
        onEvent?: (eventType: string, handler: () => void) => void
        showAlert?: (message: string) => void
      }
    }
  }
}

/** Сырая строка initData: из WebApp.initData или из location.hash (tgWebAppData). */
export function getRawInitData(): string {
  if (typeof window === 'undefined') return ''
  const fromWebApp = (window.Telegram?.WebApp?.initData ?? '').trim()
  if (fromWebApp) return fromWebApp
  const hash = window.location.hash.slice(1)
  if (!hash) return ''
  const params = new URLSearchParams(hash)
  const tgWebAppData = params.get('tgWebAppData') ?? ''
  return tgWebAppData.trim()
}

export function getTelegramUser(): { id: number; name: string } | null {
  const user = window.Telegram?.WebApp?.initDataUnsafe?.user
  if (user?.id) {
    const name = [user.first_name, user.last_name].filter(Boolean).join(' ') || 'Клиент'
    return { id: user.id, name }
  }
  const raw = getRawInitData()
  const id = raw ? getTelegramIdFromInitDataString(raw) : null
  if (id == null) return null
  return { id, name: 'Клиент' }
}

/** Достать user.id из строки initData (на случай когда initDataUnsafe ещё не готов). */
export function getTelegramIdFromInitDataString(initData: string): number | null {
  if (!initData.trim()) return null
  try {
    const params = new URLSearchParams(initData)
    const userStr = params.get('user')
    if (!userStr) return null
    const user = JSON.parse(decodeURIComponent(userStr)) as { id?: number }
    return user?.id ?? null
  } catch {
    return null
  }
}

/** Текущий telegram_id для запроса (все источники). stateTelegramId — из /me, передаёт вызывающий код. */
export function getTelegramIdForRequest(stateTelegramId: number | null): number | null {
  const user = getTelegramUser()
  const queryId = new URLSearchParams(typeof window !== 'undefined' ? window.location.search : '').get('telegram_id')
  const parsedQuery = queryId ? parseInt(queryId, 10) : null
  const initData = getRawInitData()
  const fromInitData = initData ? getTelegramIdFromInitDataString(initData) : null
  return (user ? user.id : null) ?? (Number.isInteger(parsedQuery) ? parsedQuery : null) ?? fromInitData ?? stateTelegramId ?? telegramIdFallback
}

/** Добавить telegram_id в URL (для надёжной передачи на бэкенд). */
export function appendTelegramIdToUrl(url: string, telegramId: number | null): string {
  if (telegramId == null) return url
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}telegram_id=${telegramId}`
}

/** Есть ли данные для идентификации (initData или telegram_id в query/user). */
export function hasAuthForRequest(): boolean {
  if (getRawInitData()) return true
  if (getTelegramUser()?.id) return true
  if (new URLSearchParams(window.location.search).get('telegram_id')) return true
  return false
}

let telegramIdFallback: number | null = null
/** Подставить telegram_id в заголовки после успешного /me (fallback при сбое initData). */
export function setTelegramIdFallback(id: number | null): void {
  telegramIdFallback = id
}

export function authHeaders(): HeadersInit {
  const h: HeadersInit = { 'Content-Type': 'application/json' }
  const initData = getRawInitData()
  if (initData) (h as Record<string, string>)['X-Telegram-Init-Data'] = initData
  const user = getTelegramUser()
  const queryId = new URLSearchParams(window.location.search).get('telegram_id')
  const fromInitData = initData ? getTelegramIdFromInitDataString(initData) : null
  const telegramId =
    (user ? String(user.id) : null) ??
    queryId ??
    (fromInitData != null ? String(fromInitData) : null) ??
    (telegramIdFallback != null ? String(telegramIdFallback) : null)
  if (telegramId) (h as Record<string, string>)['X-Telegram-Id'] = telegramId
  return h
}

const ERROR_CODE_MESSAGES: Record<string, string> = {
  slot_busy: 'Это время уже занято, выберите другое.',
  slot_in_past: 'Нельзя записаться на прошедшую дату. Выберите сегодня или позже.',
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

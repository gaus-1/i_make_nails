/** Рендер панели мастера: расписание, клиенты, настройки. */

import {
  API,
  apiGet,
  apiPatch,
  appendTelegramIdToUrl,
  authHeaders,
  getTelegramIdForRequest,
  normalizeApiError,
  setTelegramIdFallback,
} from './api'
import type { Slot } from './api'
import {
  state,
  type BlockedSlotItem,
  type MasterAppointment,
  type MasterClient,
  type MasterSettings,
  type WorkScheduleItem,
} from './state'
import { addDays, formatSlotTime, toYYYYMMDD } from './utils'

const DAY_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

/** Открыть чат с пользователем в Telegram. openLink/openTelegramLink требуют вызова в контексте клика (user gesture). */
function openTelegramChat(telegramId: number, e?: MouseEvent): void {
  e?.preventDefault()
  e?.stopPropagation()
  window.Telegram?.WebApp?.HapticFeedback?.impactOccurred?.('light')
  // openmessage — формат по документации для открытия чата по user_id; user?id — запасной вариант
  const urls = [`tg://openmessage?user_id=${telegramId}`, `tg://user?id=${telegramId}`]
  const webApp = window.Telegram?.WebApp
  for (const url of urls) {
    if (webApp?.openTelegramLink) {
      try {
        webApp.openTelegramLink(url)
        return
      } catch {
        /* в части клиентов tg:// выдаёт "Url protocol is not supported" */
      }
    }
    if (webApp?.openLink) {
      try {
        webApp.openLink(url)
        return
      } catch {
        /* fallback дальше */
      }
    }
  }
  setTimeout(() => {
    const w = window.open(urls[0], '_blank')
    if (w) return
    try {
      if (webApp?.openLink) webApp.openLink(urls[0])
      else window.location.href = urls[0]
    } catch {
      webApp?.showAlert?.(`Не удалось открыть чат. Найдите в Telegram по ID: ${telegramId}`)
    }
  }, 0)
}
/** Обёртка: выставляет masterLoading и перерисовывает после загрузки. Не вызывает scheduleRender до завершения — иначе при открытии Настроек получается двойной shell. */
async function withMasterLoading(
  scheduleRender: () => void,
  fn: () => Promise<void>
): Promise<void> {
  state.masterLoading = true
  state.masterError = null
  try {
    await fn()
  } finally {
    state.masterLoading = false
    scheduleRender()
  }
}

function parseDateStr(s: string): Date {
  return new Date(s + 'T12:00:00')
}

function getMonthDayDates(dateStr: string): string[] {
  const d = parseDateStr(dateStr)
  const year = d.getFullYear()
  const month = d.getMonth()
  const first = new Date(year, month, 1)
  const last = new Date(year, month + 1, 0)
  const out: string[] = []
  const cur = new Date(first)
  while (cur <= last) {
    out.push(toYYYYMMDD(cur))
    cur.setDate(cur.getDate() + 1)
  }
  return out
}

async function loadMasterAppointments(scheduleRender: () => void): Promise<void> {
  await withMasterLoading(scheduleRender, async () => {
    const uid = getTelegramIdForRequest(state.telegramId)
    const tab = state.masterTab
    const date = state.masterScheduleDate
    const view = state.masterScheduleView
    try {
      if (view === 'week') {
        const dateTo = toYYYYMMDD(addDays(parseDateStr(date), 6))
        const appointmentsRes = await apiGet<{ date: string; appointments: MasterAppointment[] }>(
          appendTelegramIdToUrl(API.masterAppointments(date, dateTo), uid)
        )
        if (state.masterTab !== tab || state.masterScheduleDate !== date) return
        state.masterAppointments = appointmentsRes.appointments
        const dayDates: string[] = []
        for (let i = 0; i < 7; i++) {
          dayDates.push(toYYYYMMDD(addDays(parseDateStr(date), i)))
        }
        const slotResponses = await Promise.all(
          dayDates.map((d) =>
            apiGet<{ date: string; slots: Slot[]; slot_duration_minutes: number }>(
              appendTelegramIdToUrl(API.slots(d), uid)
            )
          )
        )
        if (state.masterTab !== tab || state.masterScheduleDate !== date) return
        state.masterSlotsByDate = {}
        for (let i = 0; i < dayDates.length; i++) {
          state.masterSlotsByDate[dayDates[i]] = slotResponses[i].slots
        }
        state.masterSlots = slotResponses[0]?.slots ?? []
        state.masterSlotDurationMinutes = slotResponses[0]?.slot_duration_minutes ?? null
      } else if (view === 'month') {
        const dayDates = getMonthDayDates(date)
        const dateTo = dayDates[dayDates.length - 1]
        const dateFrom = dayDates[0]
        const appointmentsRes = await apiGet<{ date: string; appointments: MasterAppointment[] }>(
          appendTelegramIdToUrl(API.masterAppointments(dateFrom, dateTo), uid)
        )
        if (state.masterTab !== tab || state.masterScheduleDate !== date) return
        state.masterAppointments = appointmentsRes.appointments
        const slotResponses = await Promise.all(
          dayDates.map((d) =>
            apiGet<{ date: string; slots: Slot[]; slot_duration_minutes: number }>(
              appendTelegramIdToUrl(API.slots(d), uid)
            )
          )
        )
        if (state.masterTab !== tab || state.masterScheduleDate !== date) return
        state.masterSlotsByDate = {}
        for (let i = 0; i < dayDates.length; i++) {
          state.masterSlotsByDate[dayDates[i]] = slotResponses[i].slots
        }
        state.masterSlots = slotResponses[0]?.slots ?? []
        state.masterSlotDurationMinutes = slotResponses[0]?.slot_duration_minutes ?? null
      } else {
        const [appointmentsRes, slotsRes] = await Promise.all([
          apiGet<{ date: string; appointments: MasterAppointment[] }>(
            appendTelegramIdToUrl(API.masterAppointments(date), uid)
          ),
          apiGet<{ date: string; slots: Slot[]; slot_duration_minutes: number }>(
            appendTelegramIdToUrl(API.slots(date), uid)
          ),
        ])
        if (state.masterTab !== tab || state.masterScheduleDate !== date) return
        state.masterAppointments = appointmentsRes.appointments
        state.masterSlots = slotsRes.slots
        state.masterSlotsByDate = {}
        state.masterSlotDurationMinutes = slotsRes.slot_duration_minutes ?? null
      }
    } catch {
      if (state.masterTab !== tab) return
      state.masterAppointments = []
      state.masterSlots = []
      state.masterSlotsByDate = {}
    }
  })
}

async function loadMasterClients(scheduleRender: () => void): Promise<void> {
  await withMasterLoading(scheduleRender, async () => {
    const uid = getTelegramIdForRequest(state.telegramId)
    const tab = state.masterTab
    try {
      const data = await apiGet<{ clients: MasterClient[] }>(
        appendTelegramIdToUrl(API.masterClients, uid)
      )
      if (state.masterTab !== tab) return
      state.masterClients = data.clients
    } catch {
      if (state.masterTab !== tab) return
      state.masterClients = []
    }
  })
}

/** Загрузка настроек без глобального masterLoading — не блокирует вкладки Расписание/Клиенты. */
async function loadMasterSettings(scheduleRender: () => void): Promise<void> {
  const uid = getTelegramIdForRequest(state.telegramId)
  const tab = state.masterTab
  state.masterError = null
  state.masterSettingsLoading = true
  scheduleRender()
  const settingsUrl = appendTelegramIdToUrl(API.masterSettings, uid)
  const tryFetch = async (): Promise<MasterSettings> => apiGet<MasterSettings>(settingsUrl)
  try {
    let data: MasterSettings
    try {
      data = await tryFetch()
    } catch {
      await new Promise((r) => setTimeout(r, 400))
      if (state.masterTab !== tab) return
      data = await tryFetch()
    }
    if (state.masterTab !== tab) return
    state.masterSettings = data
  } catch {
    if (state.masterTab !== tab) return
    state.masterSettings = null
    state.masterError = 'Не удалось загрузить настройки.'
  } finally {
    if (state.masterTab === tab) {
      state.masterSettingsLoading = false
      scheduleRender()
    }
  }
}

function getMonthRange(): { from: string; to: string } {
  const d = new Date()
  const y = d.getFullYear()
  const m = d.getMonth()
  const from = toYYYYMMDD(new Date(y, m, 1))
  const to = toYYYYMMDD(new Date(y, m + 1, 0))
  return { from, to }
}

async function loadMasterBlockedSlots(scheduleRender: () => void): Promise<void> {
  await withMasterLoading(scheduleRender, async () => {
    const uid = getTelegramIdForRequest(state.telegramId)
    const tab = state.masterTab
    try {
      const { from, to } = getMonthRange()
      const data = await apiGet<{ blocked_slots: BlockedSlotItem[] }>(
        appendTelegramIdToUrl(API.masterBlockedSlots(from, to), uid)
      )
      if (state.masterTab !== tab) return
      state.masterBlockedSlots = data.blocked_slots
    } catch {
      if (state.masterTab !== tab) return
      state.masterBlockedSlots = []
    }
  })
}

async function loadMasterRescheduleSlots(dateStr: string, scheduleRender: () => void): Promise<void> {
  const uid = getTelegramIdForRequest(state.telegramId)
  try {
    const data = await apiGet<{ slots: Slot[] }>(appendTelegramIdToUrl(API.slots(dateStr), uid))
    if (state.masterRescheduleAppointmentId === null) return
    state.masterRescheduleSlots = data.slots
  } catch {
    state.masterRescheduleSlots = []
  }
  scheduleRender()
}

async function createBlockedSlot(
  dateStart: string,
  dateEnd: string,
  reason: string | null,
  scheduleRender: () => void,
  onSuccess?: () => void
): Promise<void> {
  try {
    const body: { date_start: string; date_end?: string; reason?: string | null } = {
      date_start: dateStart,
    }
    if (dateEnd !== dateStart) body.date_end = dateEnd
    if (reason) body.reason = reason
    const uid = getTelegramIdForRequest(state.telegramId)
    const r = await fetch(appendTelegramIdToUrl(API.masterBlockedSlotsPost, uid), {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(body),
    })
    const text = await r.text()
    if (!r.ok) throw new Error(normalizeApiError(text))
    await loadMasterBlockedSlots(scheduleRender)
    onSuccess?.()
  } catch {
    scheduleRender()
  }
}

async function deleteBlockedSlot(id: number, scheduleRender: () => void): Promise<void> {
  const uid = getTelegramIdForRequest(state.telegramId)
  try {
    const r = await fetch(appendTelegramIdToUrl(API.masterBlockedSlot(id), uid), {
      method: 'DELETE',
      headers: authHeaders(),
    })
    const text = await r.text()
    if (!r.ok) throw new Error(normalizeApiError(text))
    state.masterBlockedSlots = state.masterBlockedSlots.filter((b) => b.id !== id)
  } catch {
    /* без сообщения пользователю */
  }
  scheduleRender()
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

function formatTimeInput(t: string): string {
  if (!t) return '09:00'
  const part = t.split(':')
  return `${part[0] ?? '09'}:${part[1] ?? '00'}`
}

/** Нормализует ввод к HH:MM (24ч без AM/PM). */
function normalizeTimeInput(value: string): string {
  const digits = value.replace(/\D/g, '')
  if (digits.length >= 2) {
    const h = Math.min(23, parseInt(digits.slice(0, 2), 10))
    const m = digits.length >= 4 ? Math.min(59, parseInt(digits.slice(2, 4), 10)) : 0
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
  }
  if (digits.length === 1) return digits + ':'
  return value.length >= 5 ? value.slice(0, 5) : value
}

async function patchClientBookingAllowed(
  clientId: number,
  bookingAllowed: boolean,
  scheduleRender: () => void
): Promise<void> {
  if (state.masterClientPatchingId !== null) return
  state.masterClientPatchingId = clientId
  scheduleRender()
  const uid = getTelegramIdForRequest(state.telegramId)
  try {
    const updated = await apiPatch<MasterClient>(
      appendTelegramIdToUrl(API.masterClient(clientId), uid),
      { booking_allowed: bookingAllowed }
    )
    const idx = state.masterClients.findIndex((c) => c.id === clientId)
    if (idx >= 0) state.masterClients[idx] = updated
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Не удалось изменить доступ к записи.'
    window.Telegram?.WebApp?.showAlert?.(msg)
  } finally {
    state.masterClientPatchingId = null
    scheduleRender()
  }
}

async function patchMasterSettings(
  payload: { booking_enabled?: boolean; timezone?: string; work_schedule?: { day_of_week: number; time_start: string; time_end: string }[] },
  scheduleRender: () => void
): Promise<void> {
  const uid = getTelegramIdForRequest(state.telegramId)
  try {
    const settingsUrl = appendTelegramIdToUrl(API.masterSettings, uid)
    const r = await fetch(settingsUrl, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify(payload),
    })
    const text = await r.text()
    if (!r.ok) throw new Error(normalizeApiError(text))
    try {
      state.masterSettings = JSON.parse(text) as MasterSettings
    } catch {
      /* без сообщения пользователю */
    }
  } catch {
    /* без сообщения пользователю */
  }
  scheduleRender()
}

function renderAppointmentList(
  container: HTMLElement,
  appointments: MasterAppointment[],
  showSlots: Slot[],
  scheduleRender: () => void
): void {
  const subApp = document.createElement('h3')
  subApp.className = 'shell__section-caption shell__settings-ws-title'
  subApp.textContent = 'Записи'
  container.appendChild(subApp)
  if (appointments.length === 0) {
    const p = document.createElement('p')
    p.className = 'shell__section-caption'
    p.textContent = 'Нет записей.'
    container.appendChild(p)
  } else {
    const list = document.createElement('div')
    list.className = 'shell__appointments-list'
    for (const a of appointments) {
      const item = document.createElement('div')
      item.className = 'shell__appointment-item shell__appointment-item--with-actions'
      const name = document.createElement('div')
      name.className = 'shell__appointment-name'
      name.textContent = `${formatTime(a.datetime_local)} · ${a.client_name} · ${a.service_name}`
      const meta = document.createElement('div')
      meta.className = 'shell__appointment-meta'
      const contactText = a.client_phone ?? (a.client_telegram_id != null ? `Telegram ID: ${a.client_telegram_id}` : '—')
      meta.textContent = contactText
      item.appendChild(name)
      item.appendChild(meta)
      if (a.client_telegram_id != null) {
        const writeBtn = document.createElement('button')
        writeBtn.type = 'button'
        writeBtn.className = 'shell__pill shell__pill--small'
        writeBtn.textContent = 'Написать'
        writeBtn.addEventListener('click', (e) => openTelegramChat(a.client_telegram_id!, e))
        item.appendChild(writeBtn)
      }
      const isFutureConfirmed =
        a.status === 'confirmed' && new Date(a.datetime_local) > new Date()
      if (isFutureConfirmed) {
        const rescheduleBtn = document.createElement('button')
        rescheduleBtn.type = 'button'
        rescheduleBtn.className = 'shell__pill shell__pill--small'
        rescheduleBtn.textContent = 'Перенести'
        rescheduleBtn.addEventListener('click', async () => {
          state.masterRescheduleAppointmentId = a.id
          state.masterRescheduleDate = a.datetime_local.slice(0, 10)
          state.masterRescheduleSlots = []
          scheduleRender()
          await loadMasterRescheduleSlots(state.masterRescheduleDate!, scheduleRender)
        })
        item.appendChild(rescheduleBtn)
      }
      list.appendChild(item)
    }
    container.appendChild(list)
  }
  const subSlots = document.createElement('h3')
  subSlots.className = 'shell__section-caption shell__settings-ws-title'
  subSlots.textContent = 'Свободные слоты'
  container.appendChild(subSlots)
  if (showSlots.length === 0) {
    const p = document.createElement('p')
    p.className = 'shell__section-caption'
    p.textContent = 'Нет свободных слотов.'
    container.appendChild(p)
  } else {
    const slotsRow = document.createElement('div')
    slotsRow.className = 'shell__slots-row'
    for (const slot of showSlots) {
      const span = document.createElement('span')
      span.className = 'shell__slot-tag'
      span.textContent = formatSlotTime(slot.start_utc_iso)
      slotsRow.appendChild(span)
    }
    container.appendChild(slotsRow)
  }
}

function renderScheduleTab(main: HTMLElement, scheduleRender: () => void): void {
  const card = document.createElement('section')
  card.className = 'shell__card shell__section master-schedule'
  const title = document.createElement('h2')
  title.className = 'shell__section-title'
  title.textContent = 'Расписание'
  card.appendChild(title)
  const dateInput = document.createElement('input')
  dateInput.type = 'date'
  dateInput.value = state.masterScheduleDate
  dateInput.className = 'shell__input shell__date-input'
  const today = new Date()
  const maxDate = addDays(today, 31)
  dateInput.min = toYYYYMMDD(today)
  dateInput.max = toYYYYMMDD(maxDate)
  dateInput.addEventListener('change', () => {
    state.masterScheduleDate = dateInput.value
    loadMasterAppointments(scheduleRender)
  })
  card.appendChild(dateInput)
  const viewTabs = document.createElement('div')
  viewTabs.className = 'shell__period-tabs'
  const dayBtn = document.createElement('button')
  dayBtn.type = 'button'
  dayBtn.className = 'shell__period-tab' + (state.masterScheduleView === 'day' ? ' shell__period-tab--active' : '')
  dayBtn.textContent = 'День'
  dayBtn.addEventListener('click', () => {
    state.masterScheduleView = 'day'
    loadMasterAppointments(scheduleRender)
  })
  const weekBtn = document.createElement('button')
  weekBtn.type = 'button'
  weekBtn.className = 'shell__period-tab' + (state.masterScheduleView === 'week' ? ' shell__period-tab--active' : '')
  weekBtn.textContent = 'Неделя'
  weekBtn.addEventListener('click', () => {
    state.masterScheduleView = 'week'
    loadMasterAppointments(scheduleRender)
  })
  const monthBtn = document.createElement('button')
  monthBtn.type = 'button'
  monthBtn.className = 'shell__period-tab' + (state.masterScheduleView === 'month' ? ' shell__period-tab--active' : '')
  monthBtn.textContent = 'Месяц'
  monthBtn.addEventListener('click', () => {
    state.masterScheduleView = 'month'
    loadMasterAppointments(scheduleRender)
  })
  viewTabs.appendChild(dayBtn)
  viewTabs.appendChild(weekBtn)
  viewTabs.appendChild(monthBtn)
  card.appendChild(viewTabs)
  if (state.masterRescheduleAppointmentId != null) {
    const rescheduleBlock = document.createElement('div')
    rescheduleBlock.className = 'shell__form-block'
    const rescheduleTitle = document.createElement('p')
    rescheduleTitle.className = 'shell__section-caption'
    rescheduleTitle.textContent = 'Перенести запись на:'
    rescheduleBlock.appendChild(rescheduleTitle)
    const slotsRow = document.createElement('div')
    slotsRow.className = 'shell__slots-row'
    for (const slot of state.masterRescheduleSlots) {
      const btn = document.createElement('button')
      btn.type = 'button'
      btn.className = 'shell__pill shell__pill--small'
      btn.textContent = formatSlotTime(slot.start_utc_iso)
      btn.addEventListener('click', async () => {
        const id = state.masterRescheduleAppointmentId
        if (id === null) return
        const uid = getTelegramIdForRequest(state.telegramId)
        try {
          await apiPatch(appendTelegramIdToUrl(API.masterRescheduleAppointment(id), uid), {
            slot_start_utc: slot.start_utc_iso,
          })
          state.masterRescheduleAppointmentId = null
          state.masterRescheduleDate = null
          state.masterRescheduleSlots = []
          await loadMasterAppointments(scheduleRender)
        } finally {
          scheduleRender()
        }
      })
      slotsRow.appendChild(btn)
    }
    rescheduleBlock.appendChild(slotsRow)
    const cancelBtn = document.createElement('button')
    cancelBtn.type = 'button'
    cancelBtn.className = 'shell__pill'
    cancelBtn.textContent = 'Отмена'
    cancelBtn.addEventListener('click', () => {
      state.masterRescheduleAppointmentId = null
      state.masterRescheduleDate = null
      state.masterRescheduleSlots = []
      scheduleRender()
    })
    rescheduleBlock.appendChild(cancelBtn)
    card.appendChild(rescheduleBlock)
  }
  if (state.masterLoading) {
    const p = document.createElement('p')
    p.className = 'shell__section-caption'
    p.textContent = 'Загрузка…'
    card.appendChild(p)
  } else if (state.masterScheduleView === 'week') {
    const container = document.createElement('div')
    container.className = 'shell__day-cards-container'
    const dayDates: string[] = []
    for (let i = 0; i < 7; i++) {
      dayDates.push(toYYYYMMDD(addDays(parseDateStr(state.masterScheduleDate), i)))
    }
    for (const dateStr of dayDates) {
      const dayCard = document.createElement('div')
      dayCard.className = 'shell__day-card'
      const dayTitle = document.createElement('h3')
      dayTitle.className = 'shell__section-title shell__day-card-title'
      const d = parseDateStr(dateStr)
      dayTitle.textContent = d.toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric', month: 'short' })
      dayCard.appendChild(dayTitle)
      const dayAppointments = state.masterAppointments.filter(
        (a) => (a.datetime_local.slice(0, 10)) === dateStr
      )
      const daySlots = state.masterSlotsByDate[dateStr] ?? []
      renderAppointmentList(dayCard, dayAppointments, daySlots, scheduleRender)
      container.appendChild(dayCard)
    }
    card.appendChild(container)
  } else if (state.masterScheduleView === 'month') {
    const container = document.createElement('div')
    container.className = 'shell__day-cards-container shell__day-cards-container--month'
    const dayDates = getMonthDayDates(state.masterScheduleDate)
    for (const dateStr of dayDates) {
      const dayCard = document.createElement('div')
      dayCard.className = 'shell__day-card'
      const dayTitle = document.createElement('h3')
      dayTitle.className = 'shell__section-title shell__day-card-title'
      const d = parseDateStr(dateStr)
      dayTitle.textContent = d.toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric', month: 'short' })
      dayCard.appendChild(dayTitle)
      const dayAppointments = state.masterAppointments.filter(
        (a) => (a.datetime_local.slice(0, 10)) === dateStr
      )
      const daySlots = state.masterSlotsByDate[dateStr] ?? []
      renderAppointmentList(dayCard, dayAppointments, daySlots, scheduleRender)
      container.appendChild(dayCard)
    }
    card.appendChild(container)
  } else {
    renderAppointmentList(
      card,
      state.masterAppointments,
      state.masterSlots,
      scheduleRender
    )
  }
  main.appendChild(card)
}

function renderClientsTab(main: HTMLElement, scheduleRender: () => void): void {
  const card = document.createElement('section')
  card.className = 'shell__card shell__section master-clients'
  const title = document.createElement('h2')
  title.className = 'shell__section-title'
  title.textContent = 'Клиенты'
  card.appendChild(title)
  if (state.masterLoading) {
    const p = document.createElement('p')
    p.className = 'shell__section-caption'
    p.textContent = 'Загрузка…'
    card.appendChild(p)
  } else {
    const allowed = state.masterClients.filter((c) => c.booking_allowed)
    const forbidden = state.masterClients.filter((c) => !c.booking_allowed)

    const renderClientItem = (c: MasterClient) => {
      const item = document.createElement('div')
      item.className = 'shell__appointment-item shell__appointment-item--with-actions'
      const name = document.createElement('div')
      name.className = 'shell__appointment-name'
      name.textContent = c.name
      const meta = document.createElement('div')
      meta.className = 'shell__appointment-meta'
      const contactText = c.phone ?? (c.telegram_id != null ? `Telegram ID: ${c.telegram_id}` : '—')
      meta.textContent = `${contactText} · записей впереди: ${c.future_appointments_count}`
      item.appendChild(name)
      item.appendChild(meta)
      const actions = document.createElement('div')
      actions.className = 'shell__client-actions'
      if (c.telegram_id != null) {
        const writeBtn = document.createElement('button')
        writeBtn.type = 'button'
        writeBtn.className = 'shell__pill shell__pill--small'
        writeBtn.textContent = 'Написать'
        writeBtn.addEventListener('click', (e) => openTelegramChat(c.telegram_id!, e))
        actions.appendChild(writeBtn)
      }
      const bookingBtn = document.createElement('button')
      bookingBtn.type = 'button'
      const isPatching = state.masterClientPatchingId === c.id
      bookingBtn.disabled = isPatching
      bookingBtn.className = c.booking_allowed ? 'shell__pill shell__pill--danger-outline' : 'shell__pill shell__pill--small'
      bookingBtn.textContent = isPatching
        ? 'Подождите…'
        : c.booking_allowed
          ? 'Запретить запись'
          : 'Разрешить запись'
      bookingBtn.addEventListener('click', async () => {
        await patchClientBookingAllowed(c.id, !c.booking_allowed, scheduleRender)
      })
      actions.appendChild(bookingBtn)
      item.appendChild(actions)
      return item
    }

    const list = document.createElement('div')
    list.className = 'shell__appointments-list shell__clients-list'
    for (const c of allowed) list.appendChild(renderClientItem(c))

    if (forbidden.length > 0) {
      const blockTitle = document.createElement('h3')
      blockTitle.className = 'shell__section-caption shell__clients-blocked-title'
      blockTitle.textContent = 'Запись запрещена'
      card.appendChild(list)
      card.appendChild(blockTitle)
      const forbiddenList = document.createElement('div')
      forbiddenList.className = 'shell__appointments-list shell__clients-list shell__clients-list--blocked'
      for (const c of forbidden) forbiddenList.appendChild(renderClientItem(c))
      card.appendChild(forbiddenList)
    } else {
      card.appendChild(list)
    }
  }
  main.appendChild(card)
}

function renderSettingsTab(main: HTMLElement, scheduleRender: () => void): void {
  const card = document.createElement('section')
  card.className = 'shell__card shell__section shell__section--settings'
  const title = document.createElement('h2')
  title.className = 'shell__section-title'
  title.textContent = 'Настройки'
  card.appendChild(title)
  if (!state.masterSettings) {
    const p = document.createElement('p')
    p.className = 'shell__section-caption'
    p.textContent = state.masterError ?? 'Загрузка…'
    card.appendChild(p)
    if (!state.masterSettingsLoading && !state.masterError) {
      loadMasterSettings(scheduleRender)
    }
  } else {
    const s = state.masterSettings
    const bookingWrap = document.createElement('div')
    bookingWrap.className = 'shell__form-block'
    const bookingLabel = document.createElement('label')
    bookingLabel.className = 'shell__label-row'
    const bookingCb = document.createElement('input')
    bookingCb.type = 'checkbox'
    bookingCb.checked = s.booking_enabled
    bookingCb.addEventListener('change', () => {
      patchMasterSettings({ booking_enabled: bookingCb.checked }, scheduleRender)
    })
    bookingLabel.appendChild(bookingCb)
    bookingLabel.append('Онлайн-запись включена')
    const bookingHint = document.createElement('span')
    bookingHint.className = 'shell__section-caption'
    bookingHint.style.display = 'block'
    bookingHint.style.marginTop = '2px'
    bookingHint.textContent = 'Снять — клиенты не увидят свободные слоты.'
    bookingWrap.appendChild(bookingLabel)
    bookingWrap.appendChild(bookingHint)
    card.appendChild(bookingWrap)

    const wsHeader = document.createElement('button')
    wsHeader.type = 'button'
    wsHeader.className = 'shell__settings-ws-toggle'
    wsHeader.textContent = state.masterSettingsWorkScheduleCollapsed
      ? 'Рабочие часы по дням ▶'
      : 'Рабочие часы по дням ▼'
    wsHeader.addEventListener('click', () => {
      state.masterSettingsWorkScheduleCollapsed = !state.masterSettingsWorkScheduleCollapsed
      scheduleRender()
    })
    card.appendChild(wsHeader)
    const wsBlock = document.createElement('div')
    wsBlock.className = 'shell__settings-ws-block'
    if (!state.masterSettingsWorkScheduleCollapsed) {
      const byDay = new Map<number, WorkScheduleItem>()
      for (const ws of s.work_schedule) byDay.set(ws.day_of_week, ws)
      for (let d = 0; d < 7; d++) {
        const wrap = document.createElement('div')
        wrap.className = 'shell__settings-day-wrap'
        const rowTimes = document.createElement('div')
        rowTimes.className = 'shell__settings-row-times'
        const item = byDay.get(d)
        const startStr = item ? String(item.time_start).slice(0, 5) : ''
        const endStr = item ? String(item.time_end).slice(0, 5) : ''
        const isDayOff = !item || startStr === '00:00' || startStr === endStr
        const startInput = document.createElement('input')
        startInput.type = 'text'
        startInput.inputMode = 'numeric'
        startInput.autocomplete = 'off'
        startInput.className = 'shell__input shell__input--time'
        startInput.placeholder = '08:00'
        startInput.maxLength = 5
        startInput.value = item && !isDayOff ? formatTimeInput(item.time_start) : '00:00'
        startInput.addEventListener('blur', () => {
          startInput.value = normalizeTimeInput(startInput.value)
        })
        startInput.addEventListener('input', () => {
          const v = startInput.value.replace(/[^\d:]/g, '')
          if (v.length === 2 && !v.includes(':')) startInput.value = v + ':'
          else if (v.length <= 5) startInput.value = v
        })
        const endInput = document.createElement('input')
        endInput.type = 'text'
        endInput.inputMode = 'numeric'
        endInput.autocomplete = 'off'
        endInput.className = 'shell__input shell__input--time'
        endInput.placeholder = '21:30'
        endInput.maxLength = 5
        endInput.value = item && !isDayOff ? formatTimeInput(item.time_end) : '00:00'
        endInput.addEventListener('blur', () => {
          endInput.value = normalizeTimeInput(endInput.value)
        })
        endInput.addEventListener('input', () => {
          const v = endInput.value.replace(/[^\d:]/g, '')
          if (v.length === 2 && !v.includes(':')) endInput.value = v + ':'
          else if (v.length <= 5) endInput.value = v
        })
        const dayLabel = document.createElement('span')
        dayLabel.className = 'shell__settings-day'
        dayLabel.textContent = DAY_NAMES[d]
        const dash = document.createElement('span')
        dash.className = 'shell__settings-dash'
        dash.textContent = '–'
        const rowActions = document.createElement('div')
        rowActions.className = 'shell__settings-row-actions'
        const offBtn = document.createElement('button')
        offBtn.type = 'button'
        offBtn.className = 'shell__pill shell__pill--small shell__settings-off-btn'
        offBtn.textContent = isDayOff ? 'Выходной' : 'Вых.'
        offBtn.title = isDayOff ? 'Выходной' : 'Сделать выходным'
        offBtn.addEventListener('click', () => {
          startInput.value = '00:00'
          endInput.value = '00:00'
          scheduleRender()
        })
        const saveBtn = document.createElement('button')
        saveBtn.className = 'shell__pill shell__pill--small'
        saveBtn.type = 'button'
        saveBtn.disabled = state.masterSavingDay === d
        saveBtn.textContent = state.masterSavingDay === d ? '…' : 'Сохранить'
        saveBtn.addEventListener('click', async () => {
          const rest = s.work_schedule.filter((w) => w.day_of_week !== d)
          const start = normalizeTimeInput(startInput.value) || '00:00'
          const end = normalizeTimeInput(endInput.value) || '00:00'
          const startVal = start.length === 5 ? start + ':00' : start
          const endVal = end.length === 5 ? end + ':00' : end
          const newWs = [...rest, { day_of_week: d, time_start: startVal, time_end: endVal }]
          state.masterSavingDay = d
          scheduleRender()
          try {
            await patchMasterSettings(
              { work_schedule: newWs.map((w) => ({ day_of_week: w.day_of_week, time_start: w.time_start, time_end: w.time_end })) },
              scheduleRender
            )
          } finally {
            state.masterSavingDay = null
            scheduleRender()
          }
        })
        rowActions.appendChild(offBtn)
        rowActions.appendChild(saveBtn)
        const firstLine = document.createElement('div')
        firstLine.className = 'shell__settings-day-first'
        firstLine.appendChild(dayLabel)
        firstLine.appendChild(rowActions)
        rowTimes.appendChild(startInput)
        rowTimes.appendChild(dash)
        rowTimes.appendChild(endInput)
        wrap.appendChild(firstLine)
        wrap.appendChild(rowTimes)
        wsBlock.appendChild(wrap)
      }
    }
    card.appendChild(wsBlock)
  }
  main.appendChild(card)
}

function renderBlockedTab(main: HTMLElement, scheduleRender: () => void): void {
  const card = document.createElement('section')
  card.className = 'shell__card shell__section'
  const title = document.createElement('h2')
  title.className = 'shell__section-title'
  title.textContent = 'Закрытия'
  card.appendChild(title)
  const addDiv = document.createElement('div')
  addDiv.className = 'shell__form-row'
  const dateStartInput = document.createElement('input')
  dateStartInput.type = 'date'
  dateStartInput.className = 'shell__input'
  dateStartInput.placeholder = 'Дата от'
  const dateEndInput = document.createElement('input')
  dateEndInput.type = 'date'
  dateEndInput.className = 'shell__input'
  dateEndInput.placeholder = 'Дата до (необязательно)'
  const reasonInput = document.createElement('input')
  reasonInput.type = 'text'
  reasonInput.className = 'shell__input shell__input--reason'
  reasonInput.placeholder = 'Причина (необязательно)'
  const addBtn = document.createElement('button')
  addBtn.className = 'shell__pill shell__pill--primary'
  addBtn.type = 'button'
  addBtn.disabled = state.masterBlockedSubmitting
  addBtn.textContent = state.masterBlockedSubmitting ? 'Подождите…' : 'Закрыть'
  addBtn.addEventListener('click', async () => {
    const start = dateStartInput.value
    if (!start) return
    const end = dateEndInput.value || start
    state.masterBlockedSubmitting = true
    scheduleRender()
    try {
      await createBlockedSlot(start, end, reasonInput.value || null, scheduleRender, () => {
        dateStartInput.value = ''
        dateEndInput.value = ''
        reasonInput.value = ''
      })
    } finally {
      state.masterBlockedSubmitting = false
      scheduleRender()
    }
  })
  addDiv.appendChild(dateStartInput)
  addDiv.appendChild(dateEndInput)
  addDiv.appendChild(reasonInput)
  addDiv.appendChild(addBtn)
  card.appendChild(addDiv)
  if (state.masterLoading && state.masterBlockedSlots.length === 0) {
    const p = document.createElement('p')
    p.className = 'shell__section-caption'
    p.textContent = 'Загрузка…'
    card.appendChild(p)
  } else if (state.masterBlockedSlots.length === 0) {
    const p = document.createElement('p')
    p.className = 'shell__section-caption'
    p.textContent = 'Нет закрытых периодов.'
    card.appendChild(p)
  } else {
    const list = document.createElement('div')
    list.className = 'shell__appointments-list'
    for (const b of state.masterBlockedSlots) {
      const item = document.createElement('div')
      item.className = 'shell__appointment-item'
      const name = document.createElement('div')
      name.className = 'shell__appointment-name'
      name.textContent = b.date_start === b.date_end
        ? b.date_start + (b.reason ? ` · ${b.reason}` : '')
        : `${b.date_start} – ${b.date_end}` + (b.reason ? ` · ${b.reason}` : '')
      item.appendChild(name)
      const delBtn = document.createElement('button')
      delBtn.className = 'shell__pill'
      delBtn.type = 'button'
      delBtn.textContent = 'Отменить'
      delBtn.addEventListener('click', () => deleteBlockedSlot(b.id, scheduleRender))
      item.appendChild(delBtn)
      list.appendChild(item)
    }
    card.appendChild(list)
  }
  main.appendChild(card)
}

export function renderMaster(shell: HTMLElement, scheduleRender: () => void): void {
  const main = document.createElement('main')
  main.className = 'shell__main shell__main--master'

  const tabs = document.createElement('div')
  tabs.className = 'shell__period-tabs shell__period-tabs--master'
  tabs.setAttribute('role', 'tablist')
  tabs.setAttribute('aria-label', 'Разделы панели мастера')
  const tabsData: { key: 'schedule' | 'clients' | 'settings' | 'blocked'; label: string }[] = [
    { key: 'schedule', label: 'Расписание' },
    { key: 'settings', label: 'Настройки' },
    { key: 'clients', label: 'Клиенты' },
    { key: 'blocked', label: 'Закрытия' },
  ]
  for (const t of tabsData) {
    const btn = document.createElement('button')
    btn.className = 'shell__period-tab' + (state.masterTab === t.key ? ' shell__period-tab--active' : '')
    btn.type = 'button'
    btn.textContent = t.label
    btn.setAttribute('role', 'tab')
    btn.setAttribute('aria-selected', String(state.masterTab === t.key))
    btn.id = `master-tab-${t.key}`
    btn.setAttribute('aria-controls', `master-panel-${t.key}`)
    btn.addEventListener('click', async () => {
      state.masterTab = t.key
      state.masterError = null
      scheduleRender()
      if (t.key === 'schedule') await loadMasterAppointments(scheduleRender)
      else if (t.key === 'clients') await loadMasterClients(scheduleRender)
      else if (t.key === 'settings' && !state.masterSettings && !state.masterSettingsLoading) {
        await loadMasterSettings(scheduleRender)
      }
      else if (t.key === 'blocked') await loadMasterBlockedSlots(scheduleRender)
    })
    tabs.appendChild(btn)
  }
  main.appendChild(tabs)

  const messagesZone = document.createElement('div')
  messagesZone.className = 'shell__messages'
  messagesZone.setAttribute('aria-live', 'polite')
  messagesZone.setAttribute('aria-atomic', 'true')
  main.appendChild(messagesZone)

  const panel = document.createElement('div')
  panel.className = 'shell__tabpanel'
  panel.setAttribute('role', 'tabpanel')
  panel.id = `master-panel-${state.masterTab}`
  panel.setAttribute('aria-labelledby', `master-tab-${state.masterTab}`)
  if (state.masterTab === 'schedule') renderScheduleTab(panel, scheduleRender)
  else if (state.masterTab === 'clients') renderClientsTab(panel, scheduleRender)
  else if (state.masterTab === 'settings') renderSettingsTab(panel, scheduleRender)
  else renderBlockedTab(panel, scheduleRender)
  main.appendChild(panel)

  shell.appendChild(main)
}

export async function initMaster(scheduleRender: () => void): Promise<void> {
  const uid = getTelegramIdForRequest(state.telegramId)
  try {
    const me = await apiGet<{ telegram_id: number; role: string; is_owner: boolean }>(
      appendTelegramIdToUrl(API.me, uid)
    )
    state.telegramId = me.telegram_id
    state.userRole = me.role
    state.userIsOwner = me.is_owner ?? false
    setTelegramIdFallback(me.telegram_id)
  } catch {
    state.telegramId = null
    state.userRole = null
    state.userIsOwner = false
    setTelegramIdFallback(null)
  }
  scheduleRender()
  if (state.masterTab === 'schedule') await loadMasterAppointments(scheduleRender)
  else if (state.masterTab === 'clients') await loadMasterClients(scheduleRender)
  else if (state.masterTab === 'settings') await loadMasterSettings(scheduleRender)
  else if (state.masterTab === 'blocked') await loadMasterBlockedSlots(scheduleRender)
}

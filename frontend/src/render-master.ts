/** Рендер панели мастера: расписание, клиенты, настройки. */

import { API, apiGet, authHeaders } from './api'
import {
  state,
  type BlockedSlotItem,
  type MasterAppointment,
  type MasterClient,
  type MasterSettings,
  type WorkScheduleItem,
} from './state'

const DAY_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
const TIMEZONES = [
  'Europe/Moscow',
  'Europe/Samara',
  'Asia/Yekaterinburg',
  'Asia/Novosibirsk',
]

async function loadMasterAppointments(scheduleRender: () => void): Promise<void> {
  state.masterLoading = true
  state.masterError = null
  scheduleRender()
  try {
    const data = await apiGet<{ date: string; appointments: MasterAppointment[] }>(
      API.masterAppointments(state.masterScheduleDate)
    )
    state.masterAppointments = data.appointments
  } catch (e) {
    state.masterAppointments = []
    state.masterError = e instanceof Error ? e.message : String(e)
  }
  state.masterLoading = false
  scheduleRender()
}

async function loadMasterClients(scheduleRender: () => void): Promise<void> {
  state.masterLoading = true
  state.masterError = null
  scheduleRender()
  try {
    const data = await apiGet<{ clients: MasterClient[] }>(API.masterClients)
    state.masterClients = data.clients
  } catch (e) {
    state.masterClients = []
    state.masterError = e instanceof Error ? e.message : String(e)
  }
  state.masterLoading = false
  scheduleRender()
}

async function loadMasterSettings(scheduleRender: () => void): Promise<void> {
  state.masterLoading = true
  state.masterError = null
  scheduleRender()
  try {
    const data = await apiGet<MasterSettings>(API.masterSettings)
    state.masterSettings = data
  } catch (e) {
    state.masterSettings = null
    state.masterError = e instanceof Error ? e.message : String(e)
  }
  state.masterLoading = false
  scheduleRender()
}

function getMonthRange(): { from: string; to: string } {
  const d = new Date()
  const y = d.getFullYear()
  const m = d.getMonth()
  const from = `${y}-${String(m + 1).padStart(2, '0')}-01`
  const lastDay = new Date(y, m + 1, 0).getDate()
  const to = `${y}-${String(m + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`
  return { from, to }
}

async function loadMasterBlockedSlots(scheduleRender: () => void): Promise<void> {
  state.masterLoading = true
  state.masterError = null
  scheduleRender()
  try {
    const { from, to } = getMonthRange()
    const data = await apiGet<{ blocked_slots: BlockedSlotItem[] }>(
      API.masterBlockedSlots(from, to)
    )
    state.masterBlockedSlots = data.blocked_slots
  } catch (e) {
    state.masterBlockedSlots = []
    state.masterError = e instanceof Error ? e.message : String(e)
  }
  state.masterLoading = false
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
    const r = await fetch(API.masterBlockedSlotsPost, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(body),
    })
    const text = await r.text()
    if (!r.ok) throw new Error(JSON.parse(text)?.error ?? text)
    state.masterError = null
    await loadMasterBlockedSlots(scheduleRender)
    onSuccess?.()
  } catch (e) {
    state.masterError = e instanceof Error ? e.message : String(e)
    scheduleRender()
  }
}

async function deleteBlockedSlot(id: number, scheduleRender: () => void): Promise<void> {
  try {
    const r = await fetch(API.masterBlockedSlot(id), { method: 'DELETE', headers: authHeaders() })
    if (!r.ok) throw new Error((await r.json())?.error ?? 'Ошибка удаления')
    state.masterBlockedSlots = state.masterBlockedSlots.filter((b) => b.id !== id)
    state.masterError = null
  } catch (e) {
    state.masterError = e instanceof Error ? e.message : String(e)
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

async function patchClientBookingAllowed(
  clientId: number,
  bookingAllowed: boolean,
  scheduleRender: () => void
): Promise<void> {
  try {
    const r = await fetch(API.masterClient(clientId), {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify({ booking_allowed: bookingAllowed }),
    })
    const text = await r.text()
    if (!r.ok) throw new Error(JSON.parse(text)?.error ?? text)
    const updated = JSON.parse(text) as MasterClient
    const idx = state.masterClients.findIndex((c) => c.id === clientId)
    if (idx >= 0) state.masterClients[idx] = updated
  } catch (e) {
    state.masterError = e instanceof Error ? e.message : String(e)
  }
  scheduleRender()
}

async function patchMasterSettings(
  payload: { booking_enabled?: boolean; timezone?: string; work_schedule?: { day_of_week: number; time_start: string; time_end: string }[] },
  scheduleRender: () => void
): Promise<void> {
  try {
    const r = await fetch(API.masterSettings, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify(payload),
    })
    const text = await r.text()
    if (!r.ok) throw new Error(JSON.parse(text)?.error ?? text)
    state.masterSettings = JSON.parse(text) as MasterSettings
    state.masterError = null
  } catch (e) {
    state.masterError = e instanceof Error ? e.message : String(e)
  }
  scheduleRender()
}

function renderScheduleTab(main: HTMLElement, scheduleRender: () => void): void {
  const card = document.createElement('section')
  card.className = 'shell__card shell__section master-schedule'
  const title = document.createElement('h2')
  title.className = 'shell__section-title'
  title.textContent = 'Расписание дня'
  card.appendChild(title)
  const dateInput = document.createElement('input')
  dateInput.type = 'date'
  dateInput.value = state.masterScheduleDate
  dateInput.className = 'shell__input shell__date-input'
  dateInput.addEventListener('change', () => {
    state.masterScheduleDate = dateInput.value
    loadMasterAppointments(scheduleRender)
  })
  card.appendChild(dateInput)
  if (state.masterLoading) {
    const p = document.createElement('p')
    p.className = 'shell__section-caption'
    p.textContent = 'Загрузка…'
    card.appendChild(p)
  } else if (state.masterAppointments.length === 0) {
    const p = document.createElement('p')
    p.className = 'shell__section-caption'
    p.textContent = 'Нет записей.'
    card.appendChild(p)
  } else {
    const list = document.createElement('div')
    list.className = 'shell__appointments-list'
    for (const a of state.masterAppointments) {
      const item = document.createElement('div')
      item.className = 'shell__appointment-item'
      const name = document.createElement('div')
      name.className = 'shell__appointment-name'
      name.textContent = `${formatTime(a.datetime_local)} · ${a.client_name} · ${a.service_name}`
      const meta = document.createElement('div')
      meta.className = 'shell__appointment-meta'
      meta.textContent = a.client_phone ?? '—'
      item.appendChild(name)
      item.appendChild(meta)
      list.appendChild(item)
    }
    card.appendChild(list)
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
    const list = document.createElement('div')
    list.className = 'shell__appointments-list shell__clients-list'
    for (const c of state.masterClients) {
      const item = document.createElement('div')
      item.className = 'shell__appointment-item'
      const name = document.createElement('div')
      name.className = 'shell__appointment-name'
      name.textContent = c.name
      const meta = document.createElement('div')
      meta.className = 'shell__appointment-meta'
      meta.textContent = `${c.phone ?? '—'} · записей впереди: ${c.future_appointments_count}`
      item.appendChild(name)
      item.appendChild(meta)
      const label = document.createElement('label')
      label.className = 'shell__label-row'
      const cb = document.createElement('input')
      cb.type = 'checkbox'
      cb.checked = c.booking_allowed
      cb.addEventListener('change', () => {
        patchClientBookingAllowed(c.id, cb.checked, scheduleRender)
      })
      label.appendChild(cb)
      label.append('Разрешить запись')
      item.appendChild(label)
      list.appendChild(item)
    }
    card.appendChild(list)
  }
  main.appendChild(card)
}

function renderSettingsTab(main: HTMLElement, scheduleRender: () => void): void {
  const card = document.createElement('section')
  card.className = 'shell__card shell__section'
  const title = document.createElement('h2')
  title.className = 'shell__section-title'
  title.textContent = 'Настройки'
  card.appendChild(title)
  if (state.masterLoading && !state.masterSettings) {
    const p = document.createElement('p')
    p.className = 'shell__section-caption'
    p.textContent = 'Загрузка…'
    card.appendChild(p)
  } else if (state.masterSettings) {
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
    bookingWrap.appendChild(bookingLabel)
    card.appendChild(bookingWrap)

    const tzWrap = document.createElement('div')
    tzWrap.className = 'shell__form-block'
    const tzLabel = document.createElement('label')
    tzLabel.textContent = 'Часовой пояс '
    const tzSelect = document.createElement('select')
    tzSelect.className = 'shell__input'
    for (const tz of TIMEZONES) {
      const opt = document.createElement('option')
      opt.value = tz
      opt.textContent = tz
      if (tz === s.timezone) opt.selected = true
      tzSelect.appendChild(opt)
    }
    tzSelect.addEventListener('change', () => {
      patchMasterSettings({ timezone: tzSelect.value }, scheduleRender)
    })
    tzLabel.appendChild(tzSelect)
    tzWrap.appendChild(tzLabel)
    card.appendChild(tzWrap)

    const wsTitle = document.createElement('h3')
    wsTitle.className = 'shell__section-caption shell__settings-ws-title'
    wsTitle.textContent = 'Рабочие часы по дням'
    card.appendChild(wsTitle)
    const byDay = new Map<number, WorkScheduleItem>()
    for (const ws of s.work_schedule) byDay.set(ws.day_of_week, ws)
    for (let d = 0; d < 7; d++) {
      const row = document.createElement('div')
      row.className = 'shell__settings-row'
      const item = byDay.get(d)
      const startInput = document.createElement('input')
      startInput.type = 'time'
      startInput.className = 'shell__input'
      startInput.value = item ? formatTimeInput(item.time_start) : '09:00'
      const endInput = document.createElement('input')
      endInput.type = 'time'
      endInput.className = 'shell__input'
      endInput.value = item ? formatTimeInput(item.time_end) : '18:00'
      row.appendChild(document.createTextNode(DAY_NAMES[d] + ' '))
      row.appendChild(startInput)
      row.appendChild(document.createTextNode(' – '))
      row.appendChild(endInput)
      const saveBtn = document.createElement('button')
      saveBtn.className = 'shell__pill'
      saveBtn.type = 'button'
      saveBtn.disabled = state.masterSavingDay === d
      saveBtn.textContent = state.masterSavingDay === d ? 'Подождите…' : 'Сохранить'
      saveBtn.addEventListener('click', async () => {
        const rest = s.work_schedule.filter((w) => w.day_of_week !== d)
        const start = startInput.value.length === 5 ? startInput.value + ':00' : startInput.value
        const end = endInput.value.length === 5 ? endInput.value + ':00' : endInput.value
        const newWs = [...rest, { day_of_week: d, time_start: start, time_end: end }]
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
      row.appendChild(saveBtn)
      card.appendChild(row)
    }
  }
  main.appendChild(card)
}

function renderBlockedTab(main: HTMLElement, scheduleRender: () => void): void {
  const card = document.createElement('section')
  card.className = 'shell__card shell__section'
  const title = document.createElement('h2')
  title.className = 'shell__section-title'
  title.textContent = 'Закрытые даты'
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
  main.className = 'shell__main'

  const tabs = document.createElement('div')
  tabs.className = 'shell__period-tabs shell__period-tabs--master'
  const tabsData: { key: 'schedule' | 'clients' | 'settings' | 'blocked'; label: string }[] = [
    { key: 'schedule', label: 'Расписание' },
    { key: 'clients', label: 'Клиенты' },
    { key: 'settings', label: 'Настройки' },
    { key: 'blocked', label: 'Закрытые даты' },
  ]
  for (const t of tabsData) {
    const btn = document.createElement('button')
    btn.className = 'shell__period-tab' + (state.masterTab === t.key ? ' shell__period-tab--active' : '')
    btn.type = 'button'
    btn.textContent = t.label
    btn.addEventListener('click', async () => {
      state.masterTab = t.key
      state.masterError = null
      scheduleRender()
      if (t.key === 'schedule') await loadMasterAppointments(scheduleRender)
      else if (t.key === 'clients') await loadMasterClients(scheduleRender)
      else if (t.key === 'settings') await loadMasterSettings(scheduleRender)
      else if (t.key === 'blocked') await loadMasterBlockedSlots(scheduleRender)
    })
    tabs.appendChild(btn)
  }
  main.appendChild(tabs)

  const messagesZone = document.createElement('div')
  messagesZone.className = 'shell__messages'
  if (state.masterError) {
    const err = document.createElement('p')
    err.className = 'shell__error'
    err.textContent = state.masterError
    messagesZone.appendChild(err)
  }
  main.appendChild(messagesZone)

  if (state.masterTab === 'schedule') renderScheduleTab(main, scheduleRender)
  else if (state.masterTab === 'clients') renderClientsTab(main, scheduleRender)
  else if (state.masterTab === 'settings') renderSettingsTab(main, scheduleRender)
  else renderBlockedTab(main, scheduleRender)

  shell.appendChild(main)
}

export async function initMaster(scheduleRender: () => void): Promise<void> {
  if (state.masterTab === 'schedule') await loadMasterAppointments(scheduleRender)
  else if (state.masterTab === 'clients') await loadMasterClients(scheduleRender)
  else if (state.masterTab === 'settings') await loadMasterSettings(scheduleRender)
  else if (state.masterTab === 'blocked') await loadMasterBlockedSlots(scheduleRender)
}

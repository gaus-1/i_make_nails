import './style.css'

const app = document.querySelector<HTMLDivElement>('#app')
if (!app) throw new Error('Root element #app not found')

const API = {
  services: '/api/miniapp/services',
  slots: (date: string, serviceId: number) =>
    `/api/miniapp/slots?date=${date}&service_id=${serviceId}`,
  myAppointments: '/api/miniapp/appointments/my',
  createAppointment: '/api/miniapp/appointments',
  cancelAppointment: (id: number) => `/api/miniapp/appointments/${id}/cancel`,
}

type Service = { id: number; name: string; duration_minutes: number }
type Slot = { start_utc_iso: string }
type Appointment = {
  id: number
  service_name: string
  datetime_start_utc: string
  status: string
  source: string
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initDataUnsafe?: { user?: { id: number; first_name?: string; last_name?: string } }
      }
    }
  }
}

function getTelegramUser(): { id: number; name: string } | null {
  const user = window.Telegram?.WebApp?.initDataUnsafe?.user
  if (!user?.id) return null
  const name = [user.first_name, user.last_name].filter(Boolean).join(' ') || 'Клиент'
  return { id: user.id, name }
}

function authHeaders(): HeadersInit {
  const user = getTelegramUser()
  const h: HeadersInit = { 'Content-Type': 'application/json' }
  if (user) (h as Record<string, string>)['X-Telegram-Id'] = String(user.id)
  return h
}

function normalizeApiError(text: string): string {
  if (text.trimStart().toLowerCase().startsWith('<!doctype') || text.includes('</html>'))
    return 'Сервер недоступен. Проверьте подключение.'
  try {
    const j = JSON.parse(text)
    return j.detail ?? j.message ?? text
  } catch {
    return text
  }
}

async function apiGet<T>(url: string): Promise<T> {
  const r = await fetch(url, { headers: authHeaders() })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(normalizeApiError(t))
  }
  return r.json() as Promise<T>
}

async function apiPost<T>(url: string, body?: object): Promise<T> {
  const r = await fetch(url, {
    method: 'POST',
    headers: authHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) {
    const t = await r.text()
    throw new Error(normalizeApiError(t))
  }
  return r.json() as Promise<T>
}

const MONTHS_RU = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
]

function formatSlotTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

function formatDateLabel(dateStr: string): string {
  const d = new Date(dateStr + 'Z')
  const day = d.getUTCDate()
  const month = MONTHS_RU[d.getUTCMonth()]
  const weekday = d.toLocaleDateString('ru-RU', { weekday: 'short' })
  return `${day} ${month}, ${weekday}`
}

function toYYYYMMDD(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function addDays(d: Date, n: number): Date {
  const out = new Date(d)
  out.setDate(out.getDate() + n)
  return out
}

const STATUS_RU: Record<string, string> = {
  confirmed: 'Подтверждена',
  completed: 'Состоялась',
  cancelled: 'Отменена',
  no_show: 'Не пришёл',
}

function statusLabel(status: string): string {
  return STATUS_RU[status] ?? status
}

function toDateStrLocal(iso: string): string {
  const d = new Date(iso)
  return toYYYYMMDD(d)
}

function groupAppointmentsByPeriod(
  appointments: Appointment[],
  period: 'day' | 'week' | 'month',
  anchor: Date
): { dateStr: string; items: Appointment[] }[] {
  const byDate = new Map<string, Appointment[]>()
  for (const a of appointments) {
    const dateStr = toDateStrLocal(a.datetime_start_utc)
    if (!byDate.has(dateStr)) byDate.set(dateStr, [])
    byDate.get(dateStr)!.push(a)
  }
  for (const arr of byDate.values())
    arr.sort((a, b) => a.datetime_start_utc.localeCompare(b.datetime_start_utc))

  const anchorDate = new Date(anchor)
  anchorDate.setHours(0, 0, 0, 0)

  if (period === 'day') {
    const dateStr = toYYYYMMDD(anchorDate)
    return [{ dateStr, items: byDate.get(dateStr) ?? [] }]
  }

  let start: Date
  let end: Date
  if (period === 'week') {
    const day = anchorDate.getDay()
    const diff = day === 0 ? -6 : 1 - day
    start = new Date(anchorDate)
    start.setDate(anchorDate.getDate() + diff)
    end = addDays(start, 7)
  } else {
    start = new Date(anchorDate.getFullYear(), anchorDate.getMonth(), 1)
    end = new Date(anchorDate.getFullYear(), anchorDate.getMonth() + 1, 1)
  }

  const result: { dateStr: string; items: Appointment[] }[] = []
  const cur = new Date(start)
  while (cur < end) {
    const dateStr = toYYYYMMDD(cur)
    result.push({ dateStr, items: byDate.get(dateStr) ?? [] })
    cur.setDate(cur.getDate() + 1)
  }
  if (period === 'month') return result.filter((g) => g.items.length > 0)
  return result
}

const state = {
  view: 'booking' as 'booking' | 'my',
  services: [] as Service[],
  selectedServiceId: null as number | null,
  selectedDate: null as string | null,
  slots: [] as Slot[],
  selectedSlotUtc: null as string | null,
  appointments: [] as Appointment[],
  loading: false,
  error: null as string | null,
  success: null as string | null,
  weekStart: new Date(),
  myPeriod: 'week' as 'day' | 'week' | 'month',
  myPeriodAnchor: new Date(),
}

function getWeekStart(d: Date): Date {
  const day = d.getDay()
  const diff = day === 0 ? -6 : 1 - day
  const out = new Date(d)
  out.setDate(d.getDate() + diff)
  out.setHours(0, 0, 0, 0)
  return out
}

function render() {
  const shell = document.createElement('div')
  shell.className = 'shell'

  const header = document.createElement('header')
  header.className = 'shell__header'
  const openBtn = document.createElement('button')
  openBtn.className = 'shell__pill shell__pill--primary'
  openBtn.type = 'button'
  openBtn.textContent = 'Открыть запись'
  openBtn.addEventListener('click', () => {
    state.view = 'booking'
    state.success = null
    state.error = null
    const main = document.querySelector('.shell__main')
    main?.scrollIntoView({ behavior: 'smooth' })
    render()
  })
  header.appendChild(openBtn)
  shell.appendChild(header)

  const main = document.createElement('main')
  main.className = 'shell__main'

  const hero = document.createElement('section')
  hero.className = 'shell__card shell__hero'
  const heroP = document.createElement('p')
  heroP.className = 'shell__subtitle'
  heroP.textContent =
    'Выберите услугу, время и подтвердите запись. Напоминания приходят за 24 ч и за 2 ч — в любое время суток.'
  hero.appendChild(heroP)
  main.appendChild(hero)

  const tabs = document.createElement('section')
  tabs.className = 'shell__tabs'
  const tabBook = document.createElement('button')
  tabBook.className = 'shell__tab' + (state.view === 'booking' ? ' shell__tab--active' : '')
  tabBook.type = 'button'
  tabBook.textContent = 'Записаться'
  tabBook.addEventListener('click', () => {
    state.view = 'booking'
    state.error = null
    state.success = null
    render()
  })
  const tabMy = document.createElement('button')
  tabMy.className = 'shell__tab' + (state.view === 'my' ? ' shell__tab--active' : '')
  tabMy.type = 'button'
  tabMy.textContent = 'Мои записи'
  tabMy.addEventListener('click', async () => {
    state.view = 'my'
    state.error = null
    state.success = null
    render()
    await loadMyAppointments()
  })
  tabs.appendChild(tabBook)
  tabs.appendChild(tabMy)
  main.appendChild(tabs)

  if (state.view === 'my') {
    if (state.error) {
      const err = document.createElement('p')
      err.className = 'shell__error'
      err.textContent = state.error
      main.appendChild(err)
    }
    if (state.success) {
      const ok = document.createElement('p')
      ok.className = 'shell__success'
      ok.textContent = state.success
      main.appendChild(ok)
    }
    const card = document.createElement('section')
    card.className = 'shell__card shell__section'
    const titleRow = document.createElement('div')
    titleRow.className = 'shell__my-header'
    const title = document.createElement('h2')
    title.className = 'shell__section-title'
    title.textContent = 'Мои записи'
    const refreshBtn = document.createElement('button')
    refreshBtn.className = 'shell__pill'
    refreshBtn.type = 'button'
    refreshBtn.textContent = 'Обновить'
    refreshBtn.addEventListener('click', () => loadMyAppointments())
    titleRow.appendChild(title)
    titleRow.appendChild(refreshBtn)
    card.appendChild(titleRow)

    const periodTabs = document.createElement('div')
    periodTabs.className = 'shell__period-tabs'
    const periods: { key: 'day' | 'week' | 'month'; label: string }[] = [
      { key: 'day', label: 'День' },
      { key: 'week', label: 'Неделя' },
      { key: 'month', label: 'Месяц' },
    ]
    for (const p of periods) {
      const btn = document.createElement('button')
      btn.className = 'shell__period-tab' + (state.myPeriod === p.key ? ' shell__period-tab--active' : '')
      btn.type = 'button'
      btn.textContent = p.label
      btn.addEventListener('click', () => {
        state.myPeriod = p.key
        state.myPeriodAnchor = new Date()
        render()
      })
      periodTabs.appendChild(btn)
    }
    card.appendChild(periodTabs)

    const periodNav = document.createElement('div')
    periodNav.className = 'shell__calendar-header'
    const periodLabel = document.createElement('span')
    if (state.myPeriod === 'day') {
      periodLabel.textContent = formatDateLabel(toYYYYMMDD(state.myPeriodAnchor))
    } else if (state.myPeriod === 'week') {
      const ws = getWeekStart(state.myPeriodAnchor)
      periodLabel.textContent = `${ws.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })} – ${addDays(ws, 6).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })}`
    } else {
      periodLabel.textContent = state.myPeriodAnchor.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
    }
    const navDiv = document.createElement('div')
    navDiv.className = 'shell__calendar-nav'
    const prevNav = document.createElement('button')
    prevNav.type = 'button'
    prevNav.setAttribute('aria-label', 'Назад')
    prevNav.textContent = '‹'
    prevNav.addEventListener('click', () => {
      const d = new Date(state.myPeriodAnchor)
      if (state.myPeriod === 'day') d.setDate(d.getDate() - 1)
      else if (state.myPeriod === 'week') d.setDate(d.getDate() - 7)
      else d.setMonth(d.getMonth() - 1)
      state.myPeriodAnchor = d
      render()
    })
    const nextNav = document.createElement('button')
    nextNav.type = 'button'
    nextNav.setAttribute('aria-label', 'Вперёд')
    nextNav.textContent = '›'
    nextNav.addEventListener('click', () => {
      const d = new Date(state.myPeriodAnchor)
      if (state.myPeriod === 'day') d.setDate(d.getDate() + 1)
      else if (state.myPeriod === 'week') d.setDate(d.getDate() + 7)
      else d.setMonth(d.getMonth() + 1)
      state.myPeriodAnchor = d
      render()
    })
    navDiv.appendChild(prevNav)
    navDiv.appendChild(nextNav)
    periodNav.appendChild(periodLabel)
    periodNav.appendChild(navDiv)
    card.appendChild(periodNav)

    if (state.loading) {
      const p = document.createElement('p')
      p.className = 'shell__section-caption'
      p.textContent = 'Загрузка…'
      card.appendChild(p)
    } else if (state.appointments.length === 0) {
      const p = document.createElement('p')
      p.className = 'shell__section-caption'
      p.textContent = 'Нет записей за последние 30 дней.'
      card.appendChild(p)
    } else {
      const groups = groupAppointmentsByPeriod(
        state.appointments,
        state.myPeriod,
        state.myPeriodAnchor
      )
      const list = document.createElement('div')
      list.className = 'shell__appointments-list'
      for (const g of groups) {
        const dayHeader = document.createElement('div')
        dayHeader.className = 'shell__day-header'
        dayHeader.textContent = formatDateLabel(g.dateStr)
        list.appendChild(dayHeader)
        if (g.items.length === 0) {
          const empty = document.createElement('p')
          empty.className = 'shell__section-caption shell__day-empty'
          empty.textContent = 'Нет записей'
          list.appendChild(empty)
        } else {
          for (const a of g.items) {
            const item = document.createElement('div')
            item.className = 'shell__appointment-item'
            const name = document.createElement('div')
            name.className = 'shell__appointment-name'
            name.textContent = a.service_name
            const meta = document.createElement('div')
            meta.className = 'shell__appointment-meta'
            const dt = new Date(a.datetime_start_utc)
            meta.textContent = `${dt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })} · ${statusLabel(a.status)}`
            item.appendChild(name)
            item.appendChild(meta)
            if (a.status === 'confirmed' && new Date(a.datetime_start_utc) > new Date()) {
              const cancelBtn = document.createElement('button')
              cancelBtn.className = 'shell__pill'
              cancelBtn.type = 'button'
              cancelBtn.textContent = 'Отменить'
              cancelBtn.addEventListener('click', async () => {
                try {
                  await apiPost(API.cancelAppointment(a.id))
                  state.success = 'Запись отменена.'
                  await loadMyAppointments()
                  render()
                } catch (e) {
                  state.error = e instanceof Error ? e.message : String(e)
                  render()
                }
              })
              item.appendChild(cancelBtn)
            }
            list.appendChild(item)
          }
        }
      }
      card.appendChild(list)
    }
    main.appendChild(card)
  } else {
    if (state.error) {
      const err = document.createElement('p')
      err.className = 'shell__error'
      err.textContent = state.error
      main.appendChild(err)
    }
    if (state.success) {
      const ok = document.createElement('p')
      ok.className = 'shell__success'
      ok.textContent = state.success
      main.appendChild(ok)
    }

    const layout = document.createElement('section')
    layout.className = 'shell__layout'

    const sectionService = document.createElement('section')
    sectionService.className = 'shell__card shell__section'
    const h2Service = document.createElement('h2')
    h2Service.className = 'shell__section-title'
    h2Service.textContent = 'Услуга'
    const capService = document.createElement('p')
    capService.className = 'shell__section-caption'
    capService.textContent = 'Выберите вид обработки и покрытия.'
    sectionService.appendChild(h2Service)
    sectionService.appendChild(capService)
    const servicesWrap = document.createElement('div')
    servicesWrap.className = 'shell__services-wrap'
    if (state.services.length === 0 && !state.loading) {
      const empty = document.createElement('p')
      empty.className = 'shell__section-caption'
      empty.textContent = 'Загрузка услуг…'
      sectionService.appendChild(empty)
    } else {
      for (const s of state.services) {
        const btn = document.createElement('button')
        btn.className = 'service-card' + (state.selectedServiceId === s.id ? ' service-card--active' : '')
        btn.type = 'button'
        btn.dataset.serviceId = String(s.id)
        const name = document.createElement('div')
        name.className = 'service-card__name'
        name.textContent = s.name
        btn.appendChild(name)
        btn.addEventListener('click', () => {
          state.selectedServiceId = s.id
          state.selectedDate = null
          state.slots = []
          state.selectedSlotUtc = null
          render()
          if (state.selectedServiceId) loadSlots(toYYYYMMDD(new Date()), state.selectedServiceId)
        })
        servicesWrap.appendChild(btn)
      }
    }
    sectionService.appendChild(servicesWrap)
    layout.appendChild(sectionService)

    const sectionSlot = document.createElement('section')
    sectionSlot.className = 'shell__card shell__section'
    const h2Slot = document.createElement('h2')
    h2Slot.className = 'shell__section-title'
    h2Slot.textContent = 'Дата и время'
    const capSlot = document.createElement('p')
    capSlot.className = 'shell__section-caption'
    capSlot.textContent = 'Свободные окошки из расписания мастера.'
    sectionSlot.appendChild(h2Slot)
    sectionSlot.appendChild(capSlot)

    const calendarWrap = document.createElement('div')
    calendarWrap.className = 'shell__calendar-wrap'
    if (!state.selectedServiceId) {
      const hint = document.createElement('p')
      hint.className = 'shell__section-caption'
      hint.textContent = 'Сначала выберите услугу.'
      calendarWrap.appendChild(hint)
    } else {
      const weekStart = getWeekStart(state.weekStart)
      const headerCal = document.createElement('div')
      headerCal.className = 'shell__calendar-header'
      const monthLabel = document.createElement('span')
      monthLabel.textContent = weekStart.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
      const nav = document.createElement('div')
      nav.className = 'shell__calendar-nav'
      const prevBtn = document.createElement('button')
      prevBtn.type = 'button'
      prevBtn.setAttribute('aria-label', 'Предыдущая неделя')
      prevBtn.textContent = '‹'
      prevBtn.addEventListener('click', () => {
        state.weekStart = addDays(weekStart, -7)
        state.selectedDate = null
        state.slots = []
        state.selectedSlotUtc = null
        render()
        if (state.selectedServiceId)
          loadSlots(toYYYYMMDD(getWeekStart(state.weekStart)), state.selectedServiceId)
      })
      const nextBtn = document.createElement('button')
      nextBtn.type = 'button'
      nextBtn.setAttribute('aria-label', 'Следующая неделя')
      nextBtn.textContent = '›'
      nextBtn.addEventListener('click', () => {
        state.weekStart = addDays(weekStart, 7)
        state.selectedDate = null
        state.slots = []
        state.selectedSlotUtc = null
        render()
        if (state.selectedServiceId)
          loadSlots(toYYYYMMDD(getWeekStart(state.weekStart)), state.selectedServiceId)
      })
      nav.appendChild(prevBtn)
      nav.appendChild(nextBtn)
      headerCal.appendChild(monthLabel)
      headerCal.appendChild(nav)
      calendarWrap.appendChild(headerCal)

      const daysRow = document.createElement('div')
      daysRow.className = 'shell__days-row'
      for (let i = 0; i < 7; i++) {
        const dayDate = addDays(weekStart, i)
        const dateStr = toYYYYMMDD(dayDate)
        const dayBtn = document.createElement('button')
        dayBtn.className = 'shell__day' + (state.selectedDate === dateStr ? ' shell__day--active' : '')
        dayBtn.type = 'button'
        dayBtn.dataset.date = dateStr
        dayBtn.innerHTML = `<span class="shell__day-num">${dayDate.getDate()}</span><span class="shell__day-wd">${dayDate.toLocaleDateString('ru-RU', { weekday: 'short' })}</span>`
        dayBtn.addEventListener('click', () => {
          state.selectedDate = dateStr
          state.selectedSlotUtc = null
          render()
          if (state.selectedServiceId) loadSlots(dateStr, state.selectedServiceId)
        })
        daysRow.appendChild(dayBtn)
      }
      calendarWrap.appendChild(daysRow)

      if (state.selectedDate) {
        if (state.loading) {
          const loadHint = document.createElement('p')
          loadHint.className = 'shell__hint'
          loadHint.textContent = 'Загрузка слотов…'
          calendarWrap.appendChild(loadHint)
        } else {
          const slotsRow = document.createElement('div')
          slotsRow.className = 'shell__slots-row'
          if (state.slots.length === 0) {
            const noSlots = document.createElement('p')
            noSlots.className = 'shell__hint'
            noSlots.textContent = 'Нет свободных слотов на эту дату.'
            calendarWrap.appendChild(noSlots)
          } else {
            for (const slot of state.slots) {
              const slotBtn = document.createElement('button')
              slotBtn.className =
                'slot' + (state.selectedSlotUtc === slot.start_utc_iso ? ' slot--active' : '')
              slotBtn.type = 'button'
              slotBtn.textContent = formatSlotTime(slot.start_utc_iso)
              slotBtn.dataset.slot = slot.start_utc_iso
              slotBtn.addEventListener('click', () => {
                state.selectedSlotUtc = slot.start_utc_iso
                render()
              })
              slotsRow.appendChild(slotBtn)
            }
            calendarWrap.appendChild(slotsRow)
          }
        }
      }
    }
    sectionSlot.appendChild(calendarWrap)
    layout.appendChild(sectionSlot)
    main.appendChild(layout)

    const summary = document.createElement('section')
    summary.className = 'shell__card shell__summary'
    const serviceName =
      state.services.find((s) => s.id === state.selectedServiceId)?.name ?? '—'
    const summaryTitle = document.createElement('div')
    summaryTitle.className = 'shell__summary-title'
    summaryTitle.textContent = serviceName
    const summaryMeta = document.createElement('div')
    summaryMeta.className = 'shell__summary-meta'
    if (state.selectedDate && state.selectedSlotUtc) {
      summaryMeta.textContent = `${formatDateLabel(state.selectedDate)} · ${formatSlotTime(state.selectedSlotUtc)}`
    } else {
      summaryMeta.textContent = 'Выберите дату и время'
    }
    const summaryDiv = document.createElement('div')
    summaryDiv.appendChild(summaryTitle)
    summaryDiv.appendChild(summaryMeta)
    summary.appendChild(summaryDiv)
    const confirmBtn = document.createElement('button')
    confirmBtn.className = 'shell__pill shell__pill--primary'
    confirmBtn.type = 'button'
    confirmBtn.textContent = 'Подтвердить запись'
    const canConfirm =
      state.selectedServiceId && state.selectedSlotUtc && !state.loading
    confirmBtn.disabled = !canConfirm
    confirmBtn.addEventListener('click', async () => {
      if (!state.selectedServiceId || !state.selectedSlotUtc) return
      const user = getTelegramUser()
      if (!user) {
        state.error = 'Откройте приложение в Telegram для записи.'
        render()
        return
      }
      state.loading = true
      state.error = null
      render()
      try {
        await apiPost(API.createAppointment, {
          telegram_id: user.id,
          name: user.name,
          phone: null,
          service_id: state.selectedServiceId,
          slot_start_utc: state.selectedSlotUtc,
        })
        state.success = 'Запись создана. Ждём вас!'
        state.selectedSlotUtc = null
        state.slots = []
        state.selectedDate = null
        render()
      } catch (e) {
        state.error = e instanceof Error ? e.message : String(e)
        render()
      } finally {
        state.loading = false
        render()
      }
    })
    summary.appendChild(confirmBtn)
    main.appendChild(summary)
  }

  shell.appendChild(main)
  if (!app) return
  app.innerHTML = ''
  app.appendChild(shell)
}

async function loadServices() {
  try {
    const data = await apiGet<{ services: Service[] }>(API.services)
    state.services = data.services
    if (state.services.length && !state.selectedServiceId)
      state.selectedServiceId = state.services[0].id
  } catch (e) {
    state.error = e instanceof Error ? e.message : String(e)
  }
  render()
}

async function loadSlots(dateStr: string, serviceId: number) {
  state.loading = true
  render()
  try {
    const data = await apiGet<{ date: string; slots: Slot[] }>(API.slots(dateStr, serviceId))
    state.slots = data.slots
  } catch (e) {
    state.slots = []
    state.error = e instanceof Error ? e.message : String(e)
  }
  state.loading = false
  render()
}

async function loadMyAppointments() {
  state.loading = true
  render()
  try {
    const data = await apiGet<{ appointments: Appointment[] }>(API.myAppointments)
    state.appointments = data.appointments
  } catch (e) {
    state.appointments = []
    state.error = e instanceof Error ? e.message : String(e)
  }
  state.loading = false
  render()
}

state.weekStart = getWeekStart(new Date())
render()
loadServices()

/** Точка входа: определение вида (client/master) и рендер оболочки с контентом. */

import './style.css'

import { API, apiGet, appendTelegramIdToUrl, getTelegramIdForRequest, getTelegramUser, setTelegramIdFallback } from './api'
import { state } from './state'
import { renderClient } from './render-client'
import { initMaster, renderMaster } from './render-master'

const app = document.querySelector<HTMLDivElement>('#app')
if (!app) throw new Error('Root element #app not found')

/** Применить цвета темы Telegram к шапке и фону (Design guidelines, Color schemes). */
function applyTelegramTheme(): void {
  const webApp = window.Telegram?.WebApp
  if (!webApp) return
  const theme = webApp.themeParams
  const bg = theme?.bg_color ?? 'bg_color'
  const secondary = theme?.secondary_bg_color ?? 'secondary_bg_color'
  webApp.setHeaderColor?.(bg)
  webApp.setBackgroundColor?.(secondary)
}

/** Даём Telegram время подставить initData/hash, затем вызываем ready и продолжаем. */
function whenWebAppReady(cb: () => void): void {
  if (typeof window === 'undefined') {
    cb()
    return
  }
  const run = (): void => {
    const webApp = window.Telegram?.WebApp
    webApp?.ready?.()
    applyTelegramTheme()
    webApp?.expand?.()
    webApp?.onEvent?.('themeChanged', applyTelegramTheme)
    cb()
  }
  if (window.Telegram?.WebApp) {
    setTimeout(run, 0)
    return
  }
  const deadline = Date.now() + 1500
  const tick = (): void => {
    if (window.Telegram?.WebApp || Date.now() > deadline) {
      run()
      return
    }
    setTimeout(tick, 50)
  }
  setTimeout(tick, 0)
}

function initAppView(): void {
  const params = new URLSearchParams(window.location.search)
  // Опечатка v=2=2 в URL — нормализуем до v=2 и обновляем адресную строку.
  if (params.get('v') === '2=2') {
    params.set('v', '2')
    const newSearch = params.toString()
    const newUrl = window.location.pathname + (newSearch ? '?' + newSearch : '')
    window.history.replaceState(null, '', newUrl)
  }
  state.appView = params.get('view') === 'master' ? 'master' : 'client'
  if (state.appView === 'master') {
    const tid = params.get('telegram_id')
    if (tid) {
      const n = parseInt(tid, 10)
      if (Number.isInteger(n)) state.telegramId = n
    }
    const user = getTelegramUser()
    if (user && !params.get('telegram_id')) {
      params.set('telegram_id', String(user.id))
      const newSearch = params.toString()
      const newUrl = window.location.pathname + (newSearch ? '?' + newSearch : '')
      window.history.replaceState(null, '', newUrl)
    }
  }
}

export async function loadMe(scheduleRender: () => void): Promise<void> {
  try {
    const data = await apiGet<{ telegram_id: number; role: string; is_owner: boolean }>(
      appendTelegramIdToUrl(API.me, getTelegramIdForRequest(state.telegramId))
    )
    state.userRole = data.role
    state.userIsOwner = data.is_owner ?? false
    state.telegramId = data.telegram_id
    setTelegramIdFallback(data.telegram_id)
  } catch {
    state.userRole = null
    state.userIsOwner = false
    state.telegramId = null
    setTelegramIdFallback(null)
  }
  scheduleRender()
}

function switchToMasterView(): void {
  const url = new URL(window.location.href)
  if (url.searchParams.get('v') === '2=2') url.searchParams.set('v', '2')
  url.searchParams.set('view', 'master')
  const user = getTelegramUser()
  if (user) url.searchParams.set('telegram_id', String(user.id))
  window.location.href = url.toString()
}

function switchToClientView(): void {
  const url = new URL(window.location.href)
  if (url.searchParams.get('v') === '2=2') url.searchParams.set('v', '2')
  url.searchParams.delete('view')
  window.location.href = url.toString()
}

function render(): void {
  if (!app) return
  app.innerHTML = ''
  const shell = document.createElement('div')
  shell.className = 'shell'

  const header = document.createElement('header')
  header.className = 'shell__header'
  if (state.appView === 'client') {
    if (state.userRole === 'master' || state.userRole === 'admin') {
      const masterLink = document.createElement('button')
      masterLink.className = 'shell__pill'
      masterLink.type = 'button'
      masterLink.textContent = 'Панель мастера'
      masterLink.addEventListener('click', switchToMasterView)
      header.appendChild(masterLink)
    }
  } else if (state.userIsOwner) {
    const clientLink = document.createElement('button')
    clientLink.className = 'shell__pill'
    clientLink.type = 'button'
    clientLink.textContent = 'Как клиент'
    clientLink.addEventListener('click', switchToClientView)
    header.appendChild(clientLink)
  }
  shell.appendChild(header)

  if (state.appView === 'master') {
    renderMaster(shell, render)
  } else {
    renderClient(shell, render)
  }

  app.appendChild(shell)
}

initAppView()
render()
whenWebAppReady(() => {
  if (state.appView === 'client') {
    loadMe(render)
  } else {
    initMaster(render)
  }
})

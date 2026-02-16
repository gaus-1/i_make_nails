/**
 * Запуск E2E-сервера для Playwright: сборка фронта, копирование в static/, старт web_server с E2E_SERVER=1.
 * Запускать из корня репозитория: node frontend/scripts/start-e2e-server.mjs
 */
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync } from 'fs'
import { execSync, spawn } from 'child_process'
import { join } from 'path'
import { fileURLToPath } from 'url'

const root = join(fileURLToPath(import.meta.url), '..', '..', '..') // scripts -> frontend -> project root
const frontendDir = join(root, 'frontend')
const staticDir = join(root, 'static')

// 0. Удалить старые E2E БД из корня
try {
  for (const name of readdirSync(root)) {
    if (name.startsWith('e2e-') && name.endsWith('.db')) rmSync(join(root, name), { force: true })
  }
} catch (_) {}

// 1. Сборка фронта (npm run build; e2e.db удаляется в web_server при E2E_SERVER=1)
execSync('npm run build', { cwd: frontendDir, stdio: 'inherit', shell: true })

// 2. Копирование dist в static
const distDir = join(frontendDir, 'dist')
if (existsSync(staticDir)) rmSync(staticDir, { recursive: true })
mkdirSync(staticDir, { recursive: true })
cpSync(distDir, staticDir, { recursive: true })

// 3. Запуск Python-сервера (уникальный путь к БД — без блокировки от предыдущих запусков)
const e2eDbName = `e2e-${Date.now()}.db`
const env = {
  ...process.env,
  E2E_SERVER: '1',
  PORT: '8765',
  DATABASE_URL: `sqlite:///${e2eDbName}`,
  TELEGRAM_BOT_TOKEN: 'e2e-placeholder',
  SECRET_KEY: 'e2e-secret',
  MASTER_TELEGRAM_IDS: process.env.E2E_MASTER_TELEGRAM_IDS ?? '111,963126718',
  ADMIN_TELEGRAM_IDS: process.env.E2E_ADMIN_TELEGRAM_IDS ?? '111,963126718',
  OWNER_TELEGRAM_IDS: process.env.E2E_OWNER_TELEGRAM_IDS ?? '963126718',
  WEBHOOK_DOMAIN: 'localhost',
  MINIAPP_AUTH: 'dev',
}

const child = spawn('python', ['web_server.py'], {
  cwd: root,
  env,
  stdio: 'inherit',
})

child.on('error', (err) => {
  console.error(err)
  process.exit(1)
})
child.on('exit', (code) => {
  process.exit(code ?? 0)
})

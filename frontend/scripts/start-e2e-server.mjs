/**
 * Запуск E2E-сервера для Playwright: сборка фронта, копирование в static/, старт web_server с E2E_SERVER=1.
 * Запускать из корня репозитория: node frontend/scripts/start-e2e-server.mjs
 */
import { cpSync, existsSync, mkdirSync, rmSync, unlinkSync } from 'fs'
import { spawn } from 'child_process'
import { join } from 'path'
import { fileURLToPath } from 'url'
import { execSync } from 'child_process'

const root = join(fileURLToPath(import.meta.url), '..', '..', '..')
const frontendDir = join(root, 'frontend')
const distDir = join(frontendDir, 'dist')
const staticDir = join(root, 'static')
const e2eDbPath = join(root, 'e2e.db')

// 1. Сборка фронта
execSync('npm run build', { cwd: frontendDir, stdio: 'inherit' })

// 2. Копирование dist в static
if (existsSync(staticDir)) rmSync(staticDir, { recursive: true })
mkdirSync(staticDir, { recursive: true })
cpSync(distDir, staticDir, { recursive: true })

// Файловая БД для E2E (один инстанс на все соединения)
if (existsSync(e2eDbPath)) {
  try { unlinkSync(e2eDbPath) } catch (_) {}
}

// 3. Запуск Python-сервера с E2E-окружением
const env = {
  ...process.env,
  E2E_SERVER: '1',
  PORT: '8765',
  DATABASE_URL: 'sqlite:///e2e.db',
  TELEGRAM_BOT_TOKEN: 'e2e-placeholder',
  SECRET_KEY: 'e2e-secret',
  MASTER_TELEGRAM_IDS: '111',
  ADMIN_TELEGRAM_IDS: '111',
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

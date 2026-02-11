import { expect } from '@playwright/test'
import { test } from '@playwright/test'

const CLIENT_ID = process.env.E2E_CLIENT_TELEGRAM_ID ?? '555'

test.describe('Клиент', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/?telegram_id=${CLIENT_ID}`)
  })

  test('загрузка: заголовок и вкладка Записаться', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Открыть запись' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Записаться' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Мои записи' })).toBeVisible()
  })

  test('вкладка Мои записи: список или «Нет записей»', async ({ page }) => {
    await page.getByRole('button', { name: 'Мои записи' }).click()
    await expect(page.getByRole('heading', { name: 'Мои записи' })).toBeVisible()
    const noRecords = page.getByText('Нет записей за последние 30 дней.')
    const list = page.locator('.shell__appointments-list')
    await expect(noRecords.or(list)).toBeVisible({ timeout: 5000 })
  })

  test('запись: услуга → календарь → слоты', async ({ page }) => {
    await page.getByRole('button', { name: 'Записаться' }).click()
    await expect(page.getByRole('heading', { name: 'Услуга' })).toBeVisible({ timeout: 5000 })
    const serviceCard = page.locator('.service-card').first()
    await serviceCard.waitFor({ state: 'visible', timeout: 10000 })
    await serviceCard.click()
    await expect(page.getByRole('heading', { name: 'Дата и время' })).toBeVisible()
    const calCell = page.locator('.shell__cal-cell:not(.shell__cal-cell--other)').first()
    await calCell.waitFor({ state: 'visible', timeout: 3000 })
    await calCell.click()
    const slot = page.locator('.slot').first()
    await expect(slot).toBeVisible({ timeout: 5000 })
    await slot.click()
    await expect(page.getByRole('button', { name: 'Подтвердить запись' })).toBeVisible()
  })

  test('кнопка Открыть запись: переход на запись и скролл', async ({ page }) => {
    await page.getByRole('button', { name: 'Мои записи' }).click()
    await expect(page.getByRole('heading', { name: 'Мои записи' })).toBeVisible({ timeout: 5000 })
    await page.getByRole('button', { name: 'Открыть запись' }).click()
    await expect(page.getByRole('button', { name: 'Записаться' })).toHaveClass(/shell__tab--active/)
    await expect(page.getByRole('heading', { name: 'Услуга' })).toBeVisible({ timeout: 3000 })
  })

  test('в Мои записи есть кнопка Обновить', async ({ page }) => {
    await page.getByRole('button', { name: 'Мои записи' }).click()
    await expect(page.getByRole('heading', { name: 'Мои записи' })).toBeVisible({ timeout: 5000 })
    await expect(page.getByRole('button', { name: 'Обновить' })).toBeVisible()
  })

  test('периоды День / Неделя / Месяц отображаются и переключаются', async ({ page }) => {
    await page.getByRole('button', { name: 'Мои записи' }).click()
    await expect(page.getByRole('button', { name: 'День' })).toBeVisible({ timeout: 5000 })
    await expect(page.getByRole('button', { name: 'Неделя' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Месяц' })).toBeVisible()
    await page.getByRole('button', { name: 'Неделя' }).click()
    await expect(page.getByRole('button', { name: 'Неделя' })).toHaveClass(/shell__period-tab--active/)
  })

  test('форма записи: услуга и дата/время без поля телефона', async ({ page }) => {
    await page.getByRole('button', { name: 'Записаться' }).click()
    await expect(page.getByRole('heading', { name: 'Услуга' })).toBeVisible({ timeout: 5000 })
    await expect(page.getByRole('heading', { name: 'Дата и время' })).toBeVisible({ timeout: 3000 })
    await expect(page.locator('input[type="tel"]')).not.toBeVisible()
  })
})

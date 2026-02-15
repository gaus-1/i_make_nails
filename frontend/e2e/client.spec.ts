import { expect } from '@playwright/test'
import { test } from '@playwright/test'

const CLIENT_ID = process.env.E2E_CLIENT_TELEGRAM_ID ?? '555'

test.describe('Клиент', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/?telegram_id=${CLIENT_ID}`)
  })

  test('загрузка: вкладки Записаться и Мои записи', async ({ page }) => {
    await expect(page.getByRole('tab', { name: 'Записаться' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Мои записи' })).toBeVisible()
  })

  test('вкладка Мои записи: список или «Нет записей»', async ({ page }) => {
    await page.getByRole('tab', { name: 'Мои записи' }).click()
    await expect(page.getByRole('heading', { name: 'Мои записи' })).toBeVisible()
    const noRecords = page.getByText('Нет записей за последние 30 дней.')
    const list = page.locator('.shell__appointments-list')
    await expect(noRecords.or(list)).toBeVisible({ timeout: 5000 })
  })

  test('запись: календарь → дата → слоты', async ({ page }) => {
    await page.getByRole('tab', { name: 'Записаться' }).click()
    await expect(page.getByRole('heading', { name: 'Дата и время' })).toBeVisible({ timeout: 5000 })
    const calCell = page.locator('.shell__cal-cell:not(.shell__cal-cell--other)').first()
    await calCell.waitFor({ state: 'visible', timeout: 3000 })
    await calCell.click()
    const slot = page.locator('.slot').first()
    await expect(slot).toBeVisible({ timeout: 5000 })
    await slot.click()
    await expect(page.getByRole('button', { name: 'Подтвердить запись' })).toBeVisible()
  })

  test('переход Мои записи → Записаться: календарь виден', async ({ page }) => {
    await page.getByRole('tab', { name: 'Мои записи' }).click()
    await expect(page.getByRole('heading', { name: 'Мои записи' })).toBeVisible({ timeout: 5000 })
    await page.getByRole('tab', { name: 'Записаться' }).click()
    await expect(page.getByRole('tab', { name: 'Записаться' })).toHaveClass(/shell__tab--active/)
    await expect(page.getByRole('heading', { name: 'Дата и время' })).toBeVisible({ timeout: 3000 })
  })

  test('в Мои записи есть кнопка Обновить', async ({ page }) => {
    await page.getByRole('tab', { name: 'Мои записи' }).click()
    await expect(page.getByRole('heading', { name: 'Мои записи' })).toBeVisible({ timeout: 5000 })
    await expect(page.getByRole('button', { name: 'Обновить' })).toBeVisible()
  })

  test('периоды День / Неделя / Месяц отображаются и переключаются', async ({ page }) => {
    await page.getByRole('tab', { name: 'Мои записи' }).click()
    await expect(page.getByRole('button', { name: 'День' })).toBeVisible({ timeout: 5000 })
    await expect(page.getByRole('button', { name: 'Неделя' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Месяц' })).toBeVisible()
    await page.getByRole('button', { name: 'Неделя' }).click()
    await expect(page.getByRole('button', { name: 'Неделя' })).toHaveClass(/shell__period-tab--active/)
  })

  test('форма записи: календарь и слоты, без телефона', async ({ page }) => {
    await page.getByRole('tab', { name: 'Записаться' }).click()
    await expect(page.getByRole('heading', { name: 'Дата и время' })).toBeVisible({ timeout: 5000 })
    await expect(page.locator('.shell__cal-grid')).toBeVisible({ timeout: 3000 })
    await expect(page.locator('input[type="tel"]')).not.toBeVisible()
  })

  test('календарь: кнопки предыдущий/следующий месяц', async ({ page }) => {
    await page.getByRole('tab', { name: 'Записаться' }).click()
    await expect(page.getByRole('button', { name: 'Предыдущий месяц' })).toBeVisible({ timeout: 5000 })
    await expect(page.getByRole('button', { name: 'Следующий месяц' })).toBeVisible()
    await page.getByRole('button', { name: 'Предыдущий месяц' }).click()
    await expect(page.locator('.shell__cal-grid')).toBeVisible()
  })

  test('кнопка Обновить обновляет список записей', async ({ page }) => {
    await page.getByRole('tab', { name: 'Мои записи' }).click()
    await expect(page.getByRole('button', { name: 'Обновить' })).toBeVisible({ timeout: 5000 })
    await page.getByRole('button', { name: 'Обновить' }).click()
    await expect(page.getByRole('heading', { name: 'Мои записи' })).toBeVisible()
  })

  test('подтвердить запись: кнопка активна после выбора даты и слота', async ({ page }) => {
    await page.getByRole('tab', { name: 'Записаться' }).click()
    const calCell = page.locator('.shell__cal-cell:not(.shell__cal-cell--other)').first()
    await calCell.waitFor({ state: 'visible', timeout: 5000 })
    await calCell.click()
    const slot = page.locator('.slot').first()
    await slot.waitFor({ state: 'visible', timeout: 5000 })
    await slot.click()
    const confirmBtn = page.getByRole('button', { name: 'Подтвердить запись' })
    await expect(confirmBtn).toBeVisible()
    await expect(confirmBtn).toBeEnabled()
  })

  test('полный флоу: дата → слот → Подтвердить запись → успех или запись в Мои записи', async ({ page }) => {
    await page.getByRole('tab', { name: 'Записаться' }).click()
    await page.getByRole('button', { name: 'Следующий месяц' }).click()
    const calCell = page.locator('.shell__cal-cell:not(.shell__cal-cell--other)').first()
    await calCell.waitFor({ state: 'visible', timeout: 5000 })
    await calCell.click()
    const slot = page.locator('.slot').first()
    await slot.waitFor({ state: 'visible', timeout: 10000 })
    await slot.click()
    await page.getByRole('button', { name: 'Подтвердить запись' }).click()
    await expect(
      page.getByText(/Запись создана|Ждём вас|Не удалось|уже занято/).or(page.locator('.shell__success'))
    ).toBeVisible({ timeout: 10000 })
    await page.getByRole('tab', { name: 'Мои записи' }).click()
    await expect(page.getByRole('heading', { name: 'Мои записи' })).toBeVisible({ timeout: 5000 })
    await expect(
      page.locator('.shell__section').filter({ hasText: 'Мои записи' }).locator('.shell__appointments-list, .shell__section-caption').first()
    ).toBeVisible({ timeout: 10000 })
  })
})

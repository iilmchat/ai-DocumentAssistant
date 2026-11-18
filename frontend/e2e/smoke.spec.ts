import { test, expect } from '@playwright/test'

const DOC = {
  id: '11111111-1111-4111-8111-111111111111',
  title: 'Тестовый договор.pdf',
  status: 'completed',
  summary: '# Ключевые тезисы\n\n- Пункт один\n- Пункт два',
  created_at: '2026-11-18T10:00:00Z',
}

test('неавторизованный пользователь видит форму входа', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('С возвращением')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Войти' })).toBeVisible()
})

test('авторизованный пользователь видит конспект и кнопки экспорта', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('ai_document_assistant_token', 'fake-test-token')
  })

  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: '22222222-2222-4222-8222-222222222222',
        email: 'test@example.com',
        created_at: '2026-11-01T00:00:00Z',
      }),
    })
  )

  await page.route('**/api/v1/documents/', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([DOC]) })
  )

  await page.route('**/api/v1/documents/*/versions', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  )

  await page.goto('/')
  await expect(page.getByText('Умный конспект документа')).toBeVisible()
  await expect(page.getByRole('button', { name: 'MD' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'DOCX' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'PDF' })).toBeVisible()
  await expect(page.getByText('Пункт один')).toBeVisible()
})

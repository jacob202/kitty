import { expect, test } from '@playwright/test'

test('browser → real Gateway → temp DB survives reload with fake model boundary', async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('kitty-onboarded', 'true'))
  await page.goto('/')
  await expect(page.locator('main')).toBeVisible({ timeout: 15_000 })

  await page.getByRole('button', { name: /^chat$/i }).first().click()
  const composer = page.locator('textarea').first()
  await expect(composer).toBeVisible()
  await expect(composer).toBeEnabled()

  const userText = `hermetic continuity ${Date.now()}`
  await composer.fill(userText)
  await page.getByRole('button', { name: /send message/i }).click()

  await expect(page.locator('.msg-in').filter({ hasText: userText }).first()).toBeVisible()
  await expect(page.locator('.msg-in').filter({ hasText: /Hermetic Kitty reply persisted/ }).first()).toBeVisible({ timeout: 20_000 })

  const chatId = await page.evaluate(() => window.localStorage.getItem('kitty-active-chat-id'))
  expect(chatId).toBeTruthy()

  await expect.poll(async () => {
    return page.evaluate(async (id) => {
      const response = await fetch(`/proxy/chats/${encodeURIComponent(id!)}/messages`)
      const payload = await response.json()
      return payload.messages?.map((message: { content: string }) => message.content) ?? []
    }, chatId)
  }).toEqual(expect.arrayContaining([userText, expect.stringMatching(/Hermetic Kitty reply persisted/)]))

  await page.reload()
  await expect(page.locator('main')).toBeVisible({ timeout: 15_000 })
  await page.getByRole('button', { name: /^chat$/i }).first().click()
  await expect(page.locator('.msg-in').filter({ hasText: userText }).first()).toBeVisible({ timeout: 15_000 })
  await expect(page.locator('.msg-in').filter({ hasText: /Hermetic Kitty reply persisted/ }).first()).toBeVisible()
})

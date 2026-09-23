import { test, expect, loginEmployee, waitForAiSettled } from './helpers';

test('сотрудник видит профиль, готовность и объяснённые рекомендации', async ({ page }) => {
  await loginEmployee(page, 'E0028');

  const profile = page.locator('.hero .who');
  await expect(profile.getByRole('heading', { level: 1 })).toHaveText('Akmaral Ismailova');
  await expect(profile).toContainText('Backend Engineer');
  await expect(profile).toContainText('Middle');
  await expect(profile).toContainText('Backend Development');
  await expect(profile).toContainText('Стаж: 52 мес.');
  await expect(profile).toContainText('Последняя оценка: 2026-06-24');

  await expect(page.getByRole('heading', { name: 'Готовность по навыкам', exact: true })).toBeVisible();
  const readiness = page.locator('.hero .readiness .num');
  await expect(readiness).toHaveText(/^\d+(?:\.\d+)?\s*%$/);
  const readinessValue = Number.parseFloat((await readiness.innerText()).trim());
  expect(readinessValue).toBeGreaterThanOrEqual(0);
  expect(readinessValue).toBeLessThanOrEqual(100);

  // AI may reorder every card. Inspect the settled cards without fixing an event ID/title.
  await waitForAiSettled(page);
  const aiStatus = page.locator('.ai-status');
  await expect(aiStatus).toBeVisible();
  await expect(aiStatus).toHaveText(
    /Выбор AI проверен сервером|Рекомендация рассчитана по правилам; AI сейчас недоступен/,
  );

  const main = page.locator('article.rec.main');
  const alternatives = page.locator('article.rec.alt');
  await expect(main).toHaveCount(1);
  await expect(main.locator('.kind')).toContainText('Главный шаг');
  await expect(alternatives).toHaveCount(2);

  const cards = page.locator('article.rec');
  for (const card of await cards.all()) {
    await expect(card.locator('.title')).not.toBeEmpty();
    await expect(card.locator('ul.facts > li').first()).toBeVisible();
    const why = card.getByRole('button', { name: 'Почему этот шаг?', exact: true });
    await why.click();
    await expect(why).toHaveAttribute('aria-expanded', 'true');
    await expect(card.locator('.evidence')).toBeVisible();
    const categories = (await card.locator('.evidence .fact .cat').allTextContents())
      .map((text) => text.split('·').slice(1).join('·').trim())
      .filter(Boolean);
    expect(new Set(categories).size, 'Объяснение должно содержать ≥3 разных категорий фактов').toBeGreaterThanOrEqual(3);
    await expect(card.locator('.evidence')).toContainText('Разбор оценки кандидата');
    await why.click();
    await expect(why).toHaveAttribute('aria-expanded', 'false');
  }

  const whyNot = main.getByRole('button', { name: 'Почему не другой?', exact: true });
  await whyNot.click();
  await expect(whyNot).toHaveAttribute('aria-expanded', 'true');
  await expect(main.locator('.evidence')).toBeVisible();
  await expect(main.locator('.evidence')).toContainText('Ранжирование учитывает');
  await expect(main.locator('.evidence > p').first()).toBeVisible();
});

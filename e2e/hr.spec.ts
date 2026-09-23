import { test, expect, loginHr } from './helpers';

test('HR sees dashboard cards and expands catalog constraints', async ({ page }) => {
  await loginHr(page);

  const cardLabels = [
    'Сотрудников',
    'С открытым критическим разрывом',
    'Без исполнимого шага',
    'Требования цели выполнены',
  ];
  await expect(page.locator('.card-stat')).toHaveCount(cardLabels.length);
  for (const label of cardLabels) {
    const card = page.locator('.card-stat').filter({
      has: page.getByText(label, { exact: true }),
    });
    await expect(card).toBeVisible();
    await expect(card.locator('.v')).toHaveText(/^\d+$/);
  }
  const employeeCount = page.locator('.card-stat').filter({
    has: page.getByText('Сотрудников', { exact: true }),
  });
  expect(Number(await employeeCount.locator('.v').innerText())).toBeGreaterThan(0);

  await page.getByRole('button', { name: 'Навыки и ограничения', exact: true }).click();
  await expect(page.getByRole('heading', {
    name: 'Какие навыки проседают и что мешает их развивать',
  })).toBeVisible();
  const intervention = page.getByRole('button', {
    name: 'Что можно изменить в каталоге', exact: true,
  }).first();
  const draft = page.getByText('Черновик для проверки HR.', { exact: false });
  await expect(draft).toHaveCount(0);
  await intervention.click();
  await expect(draft).toBeVisible();

  // The expanded row contains both a concrete intervention and catalog evidence.
  const details = page.getByRole('cell').filter({ has: draft });
  await expect(details.locator('p > b')).not.toBeEmpty();
  await expect(details.locator('.chip').first()).toHaveText(
    /факт каталога|условие допуска|лимит поиска|выбор сотрудника/,
  );
  await intervention.click();
  await expect(draft).toHaveCount(0);
});

test('HR opens the selected employee from the no-step list', async ({ page }) => {
  await loginHr(page);
  await page.getByRole('button', { name: 'Нет шага', exact: true }).click();
  await expect(page.getByRole('heading', {
    name: 'У кого нет рекомендованного шага и почему',
  })).toBeVisible();

  const row = page.getByRole('row').filter({
    has: page.getByRole('link', { name: 'Открыть профиль', exact: true }),
  }).first();
  await expect(row).toBeVisible();
  const employeeName = (await row.locator('b').innerText()).trim();
  const link = row.getByRole('link', { name: 'Открыть профиль', exact: true });
  const href = await link.getAttribute('href');
  expect(href).toMatch(/^\/hr\/employee\/E\d+$/);

  await link.click();
  await expect(page).toHaveURL(new RegExp(`${href}$`));
  await expect(page.getByRole('heading', { name: employeeName, exact: true })).toBeVisible();
  await expect(page.getByText('Сейчас нет исполнимого шага', { exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: '← Назад', exact: true })).toBeVisible();
});

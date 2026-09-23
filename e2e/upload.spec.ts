import { readFileSync } from 'node:fs';
import path from 'node:path';
import { test, expect, loginHr } from './helpers';
import employeesFixture from './fixtures/employees.json';

const fixturePath = (name: string) => path.join(__dirname, 'fixtures', name);
const employeeIds = employeesFixture.employees.map((employee) => employee.employee_id);
const historyCount = readFileSync(fixturePath('activity_history.csv'), 'utf8').trim().split(/\r?\n/).length - 1;

test('HR creates a three-person scenario and rejects an invalid upload', async ({ page }) => {
  await loginHr(page);
  await page.getByRole('button', { name: 'Данные', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Проверочный сценарий', exact: true })).toBeVisible();
  const validate = page.getByRole('button', { name: 'Проверить', exact: true });
  await expect(validate).toBeDisabled();

  // These are unchanged E0001, E0028, E0050 profiles plus every matching source
  // history row from data/dataset; meta keeps the original snapshot date.
  await page.locator('input[type="file"]').setInputFiles([
    fixturePath('employees.json'),
    fixturePath('activity_history.csv'),
  ]);
  const validResponsePromise = page.waitForResponse((response) =>
    response.url().endsWith('/api/py/hr/import/validate') && response.request().method() === 'POST',
  );
  await validate.click();
  const validResponse = await validResponsePromise;
  expect(validResponse.ok()).toBeTruthy();
  const report = await validResponse.json();
  expect(report).toMatchObject({
    ok: true,
    counts: { employees: 3, history: historyCount },
    errors: [],
    employee_ids: employeeIds,
  });
  await expect(page.getByText(`employees: 3, history: ${historyCount}`, { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Ошибки', exact: true })).toHaveCount(0);
  const createScenario = page.getByRole('button', { name: /^Создать сценарий \(/ });
  await expect(createScenario).toBeEnabled();
  for (const id of employeeIds) await expect(createScenario).toContainText(id);
  await createScenario.click();

  const scenarioChip = page.locator('header .chip').filter({ hasText: /^Проверочный сценарий:/ });
  await expect(scenarioChip).toBeVisible();
  await expect(scenarioChip).toContainText('employees.json');
  await expect(scenarioChip).toContainText('activity_history.csv');
  await page.getByRole('button', { name: 'Навыки и ограничения', exact: true }).click();
  const employeeCard = page.locator('.card-stat').filter({
    has: page.getByText('Сотрудников', { exact: true }),
  });
  await expect(employeeCard.locator('.v')).toHaveText('3');
  await expect(page.getByText(/^Выборка: 3 ·/)).toBeVisible();

  // A rejected file must show a useful validation error and leave the existing
  // three-person scenario active, without offering to commit invalid data.
  await page.getByRole('button', { name: 'Данные', exact: true }).click();
  await page.locator('input[type="file"]').setInputFiles(fixturePath('invalid-employees.json'));
  const invalidResponsePromise = page.waitForResponse((response) =>
    response.url().endsWith('/api/py/hr/import/validate') && response.request().method() === 'POST',
  );
  await validate.click();
  const invalidResponse = await invalidResponsePromise;
  expect(invalidResponse.ok()).toBeTruthy();
  const invalidReport = await invalidResponse.json();
  expect(invalidReport.ok).toBe(false);
  expect(invalidReport.errors).toEqual(expect.arrayContaining([
    expect.objectContaining({ path: 'employees[0]', code: 'MISSING_FIELDS' }),
  ]));
  await expect(page.getByRole('heading', { name: 'Ошибки', exact: true })).toBeVisible();
  await expect(page.getByText(/employees\[0\]: MISSING_FIELDS/)).toBeVisible();
  await expect(createScenario).toHaveCount(0);
  await expect(scenarioChip).toBeVisible();
  await page.getByRole('button', { name: 'Навыки и ограничения', exact: true }).click();
  await expect(employeeCard.locator('.v')).toHaveText('3');
  await expect(page.getByText(/^Выборка: 3 ·/)).toBeVisible();
});

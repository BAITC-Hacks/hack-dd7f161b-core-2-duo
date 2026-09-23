import { test, expect, loginEmployee, waitForAiSettled } from './helpers';

test('другая цель меняет источник, сброс восстанавливает исходную цель', async ({ page }) => {
  await loginEmployee(page, 'E0028');
  await waitForAiSettled(page);

  const profile = page.locator('.hero .who');
  const target = profile.locator('.goal-line .to');
  const source = profile.locator(':scope > p');
  await expect(target).not.toBeEmpty();
  await expect(source).toHaveText('Цель не выбрана: рассчитан следующий грейд');
  const originalTarget = await target.innerText();
  const originalSource = await source.innerText();

  await profile.getByRole('button', { name: 'Изменить цель', exact: true }).click();
  const select = profile.getByRole('combobox');
  await expect(select).toBeVisible();
  const originalValue = await select.inputValue();
  const options = await select.locator('option').evaluateAll((elements) =>
    elements.map((element) => (element as HTMLOptionElement).value),
  );
  const anotherTarget = options.find((value) => value !== originalValue);
  expect(anotherTarget, 'Каталог должен предлагать другую цель').toBeTruthy();

  await select.selectOption(anotherTarget!);
  await profile.getByRole('button', { name: 'Сохранить', exact: true }).click();
  await expect(source).toHaveText('Цель выбрана вами');
  await expect(target).toHaveText(anotherTarget!.replace('|', ' '));
  await expect(target).not.toHaveText(originalTarget);
  await expect(profile.getByRole('combobox')).toHaveCount(0);

  await profile.getByRole('button', { name: 'Сбросить цель', exact: true }).click();
  await expect(source).toHaveText(originalSource);
  await expect(target).toHaveText(originalTarget);
  await expect(profile.getByRole('button', { name: 'Сбросить цель', exact: true })).toHaveCount(0);
  await waitForAiSettled(page);
});

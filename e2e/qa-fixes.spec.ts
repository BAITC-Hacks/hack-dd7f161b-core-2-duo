import { readFileSync } from "node:fs";
import path from "node:path";
import type { Page } from "@playwright/test";
import { expect, loginEmployee, loginHr, test, waitForAiSettled } from "./helpers";

test.beforeEach(async ({ page }) => {
  // Exercise the real recommendation engine without depending on an external AI.
  await page.route(/\/api\/py\/employees\/[^/]+\/ai$/, (route) => route.abort());
});

async function expectNoHorizontalScroll(page: Page) {
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
  await expect.poll(() => page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )).toBeLessThanOrEqual(0);
}

async function completionCount(page: Page) {
  return page.evaluate(() => {
    const state = JSON.parse(localStorage.getItem("career-quest:v1") || "{}");
    return (state.overlays?.[state.scenarioKey]?.completions || [])
      .filter((item: { employee_id: string }) => item.employee_id === "E0028").length;
  });
}

test("QA-01: double click records one completion and disables it until snapshot refresh", async ({ page }) => {
  await loginEmployee(page);
  await waitForAiSettled(page);
  const main = page.locator("article.rec.main");
  const title = await main.locator(".title").innerText();
  const done = main.getByRole("button", { name: "Отметить выполненным", exact: true });
  const before = await completionCount(page);
  let snapshotRequests = 0;
  let releaseSnapshot!: () => void;
  const snapshotGate = new Promise<void>((resolve) => { releaseSnapshot = resolve; });
  await page.route(/\/api\/py\/employees\/E0028$/, async (route) => {
    snapshotRequests += 1;
    await snapshotGate;
    await route.continue();
  });

  try {
    // Both pointer clicks are sent as one user gesture; no second action waits
    // for the button to become enabled after the refresh.
    await done.dblclick({ delay: 30 });
    await expect.poll(() => snapshotRequests).toBe(1);
    await expect(done).toBeDisabled();
    await expect.poll(() => completionCount(page)).toBe(before + 1);
    await expect(main.locator(".title")).toHaveText(title);
  } finally {
    releaseSnapshot();
  }

  await expect(main.locator(".title")).not.toHaveText(title);
  await expect(done).toBeEnabled();
  expect(await completionCount(page)).toBe(before + 1);
});

test("QA-04: forecast traps focus, closes with Escape and restores its trigger", async ({ page }) => {
  await loginEmployee(page, "E0001");
  await waitForAiSettled(page);
  const trigger = page.locator("article.rec.main").getByRole("button", { name: "Что изменится?", exact: true });
  await expect(trigger).toBeEnabled();
  await trigger.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Что изменится?", exact: true });
  const close = dialog.getByRole("button", { name: "Закрыть", exact: true });
  await expect(dialog).toBeVisible();
  await expect(close).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(close).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(close).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(trigger).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(close).toBeFocused();
  await close.click();
  await expect(trigger).toBeFocused();
});

test("QA-11 / QA-13: login fits 360 px and updates document language in RU, KK and EN", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await expect(page.locator(".person").first()).toBeVisible();
  for (const language of ["RU", "KK", "EN"]) {
    await page.getByRole("group", { name: "language" }).getByRole("button", { name: language, exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("lang", language.toLowerCase());
    await expectNoHorizontalScroll(page);
  }
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator(".person").first()).toBeVisible();
  // The new password step must fit the same employee picker at this width.
  await page.locator(".person").first().click();
  await expect(page.locator("#login-password-form")).toBeVisible();
  await expectNoHorizontalScroll(page);
});

test("QA-18: imported scenario with long filenames stays within a 360 px header", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await loginHr(page);
  await page.getByRole("button", { name: "Данные", exact: true }).click();
  const employeesName = "employees-pair-with-a-very-long-scenario-name.json";
  await page.locator('input[type="file"]').setInputFiles([
    { name: employeesName, mimeType: "application/json", buffer: readFileSync(path.join(__dirname, "fixtures/employees.json")) },
    { name: "activity_history.csv", mimeType: "text/csv", buffer: readFileSync(path.join(__dirname, "fixtures/activity_history.csv")) },
  ]);
  await page.getByRole("button", { name: "Проверить", exact: true }).click();
  await page.getByRole("button", { name: /^Создать сценарий \(/ }).click();
  const chip = page.locator("header .chip").filter({ hasText: employeesName });
  await expect(chip).toBeVisible();
  await expect(chip).toContainText("activity_history.csv");
  // Check a normal dashboard after import so upload controls do not obscure
  // whether the global scenario chip itself widens the document.
  await page.getByRole("button", { name: "Навыки и ограничения", exact: true }).click();
  await expectNoHorizontalScroll(page);
  const bounds = await chip.boundingBox();
  expect(bounds).not.toBeNull();
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(360);
});

test("QA-17 / QA-16 / QA-12: fallback, score labels and skill sources are localized", async ({ page }) => {
  await loginEmployee(page, "E0001");
  for (const { language, reason, why, source, labels } of [
    {
      language: "RU", reason: "сервис AI недоступен", why: "Почему этот шаг?", source: "Источник расчёта",
      labels: ["Закрытие разрыва цели", "Закрытие критического разрыва", "Вклад в маршрут", "Соответствие истории участия", "Обратная связь", "Соответствие формату работы", "Продолжение начатого", "Затраты времени", "Ожидание сессии"],
    },
    {
      language: "KK", reason: "AI қызметі қолжетімсіз", why: "Неліктен бұл қадам?", source: "Есептеу көзі",
      labels: ["Мақсат алшақтығын жабу", "Сыни алшақтықты жабу", "Маршрутқа үлесі", "Қатысу тарихына сәйкестік", "Кері байланыс", "Жұмыс форматына сәйкестік", "Басталған әрекетті жалғастыру", "Уақыт шығыны", "Сессияны күту"],
    },
    {
      language: "EN", reason: "AI service unavailable", why: "Why this step?", source: "Calculation source",
      labels: ["Goal gap closure", "Critical gap closure", "Contribution to the route", "Participation history fit", "Feedback", "Work format fit", "Continuing an activity", "Time cost", "Session wait"],
    },
  ]) {
    await page.getByRole("group", { name: "language" }).getByRole("button", { name: language, exact: true }).click();
    await expect(page.locator(".ai-status.fallback")).toContainText(`(${reason})`);
    await expect(page.locator(".ai-status")).not.toContainText("fallback_unavailable");
    const main = page.locator("article.rec.main");
    const whyButton = main.getByRole("button", { name: why, exact: true });
    await whyButton.click();
    await expect(whyButton).toHaveAttribute("aria-expanded", "true");
    await expect(main.locator(".breakdown > span")).toHaveText(labels);
    await expect(main.locator(".breakdown")).not.toContainText(/score_|gap_closure|critical_closure|history_fit|effort_penalty/);
    await whyButton.click();

    const skillSource = page.getByRole("button", { name: new RegExp(`^${source}: .+`) }).first();
    await expect(skillSource).toHaveAttribute("aria-expanded", "false");
    await skillSource.click();
    await expect(skillSource).toHaveAttribute("aria-expanded", "true");
    const sourceId = await skillSource.getAttribute("aria-controls");
    expect(sourceId).toBeTruthy();
    await expect(page.locator(`[id="${sourceId}"]`)).toBeVisible();
    await skillSource.click();
    await expect(skillSource).toHaveAttribute("aria-expanded", "false");
  }
});

test("QA-07: reopening goal editor after reset selects the restored target", async ({ page }) => {
  await loginEmployee(page);
  const profile = page.locator(".hero .who");
  const target = profile.locator(".goal-line .to");
  const originalTarget = await target.innerText();
  await profile.getByRole("button", { name: "Изменить цель", exact: true }).click();
  const select = profile.getByRole("combobox", { name: "Цель", exact: true });
  const originalValue = await select.inputValue();
  const options = await select.locator("option").evaluateAll((elements) =>
    elements.map((element) => (element as HTMLOptionElement).value),
  );
  const anotherTarget = options.find((value) => value !== originalValue);
  expect(anotherTarget).toBeTruthy();
  await select.selectOption(anotherTarget!);
  await profile.getByRole("button", { name: "Сохранить", exact: true }).click();
  await expect(target).toHaveText(anotherTarget!.replace("|", " "));
  await profile.getByRole("button", { name: "Сбросить цель", exact: true }).click();
  await expect(target).toHaveText(originalTarget);
  await profile.getByRole("button", { name: "Изменить цель", exact: true }).click();
  await expect(select).toHaveValue(originalValue);
  await profile.getByRole("button", { name: "Сохранить", exact: true }).click();
  await expect(target).toHaveText(originalTarget);
});

test("QA-05: failed snapshot marks data stale, blocks completion and recovers on retry", async ({ page }) => {
  await loginEmployee(page);
  await waitForAiSettled(page);
  const main = page.locator("article.rec.main");
  const title = await main.locator(".title").innerText();
  const done = main.getByRole("button", { name: "Отметить выполненным", exact: true });
  let failSnapshot = true;
  await page.route(/\/api\/py\/employees\/E0028$/, (route) =>
    failSnapshot
      ? route.fulfill({ status: 503, contentType: "application/json", body: '{"detail":"temporary failure"}' })
      : route.continue(),
  );
  await done.click();
  const alert = page.getByRole("alert").filter({ hasText: "Не удалось обновить данные." });
  await expect(alert).toContainText("Не удалось обновить данные.");
  await expect(alert).toContainText("Данные устарели. Выполнение шагов недоступно до пересчёта.");
  await expect(main.locator(".title")).toHaveText(title);
  await expect(done).toBeDisabled();
  expect(await completionCount(page)).toBe(1);

  failSnapshot = false;
  await page.getByRole("button", { name: "Повторить", exact: true }).click();
  await expect(main.locator(".title")).not.toHaveText(title);
  await expect(done).toBeEnabled();
  await expect(alert).not.toBeVisible();
  expect(await completionCount(page)).toBe(1);
});

test("QA-06: failed forecast offers retry and then renders the recovered prediction", async ({ page }) => {
  await loginEmployee(page);
  await waitForAiSettled(page);
  let failSimulation = true;
  await page.route(/\/api\/py\/employees\/E0028\/simulate$/, (route) =>
    failSimulation
      ? route.fulfill({ status: 503, contentType: "application/json", body: '{"detail":"temporary failure"}' })
      : route.continue(),
  );
  await page.locator("article.rec.main").getByRole("button", { name: "Что изменится?", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Не удалось рассчитать прогноз.", { exact: true })).toBeVisible();
  await expect(dialog.getByText("Загрузка…", { exact: true })).not.toBeVisible();
  const retry = dialog.getByRole("button", { name: "Повторить", exact: true });
  await expect(retry).toBeEnabled();
  const close = dialog.getByRole("button", { name: "Закрыть", exact: true });
  await expect(close).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(retry).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(close).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(retry).toBeFocused();
  failSimulation = false;
  await page.keyboard.press("Enter");
  await expect(dialog.locator(".readiness .num")).toHaveText(/^\d+(?:\.\d+)?→\d+(?:\.\d+)?%$/);
  await expect(dialog.getByText("Не удалось рассчитать прогноз.", { exact: true })).not.toBeVisible();
  await expect(close).toBeFocused();
});

import { test as base, expect, type Page, type Request } from "@playwright/test";

const pendingAi = new WeakMap<Page, Set<Request>>();

export const test = base.extend({
  page: async ({ page }, use, testInfo) => {
    const errors: string[] = [];
    const requests = new Set<Request>();
    pendingAi.set(page, requests);
    page.on("pageerror", (error) => errors.push(error.stack || error.message));
    page.on("request", (request) => {
      if (/\/api\/py\/employees\/[^/]+\/ai$/.test(new URL(request.url()).pathname)) {
        requests.add(request);
      }
    });
    page.on("requestfinished", (request) => requests.delete(request));
    page.on("requestfailed", (request) => requests.delete(request));

    try {
      // Playwright already creates a fresh context per test. Clear explicitly once,
      // then reload to reset the app's in-memory store too. Never clear on reloads
      // inside a test: they must exercise real persisted sessions and completions.
      await page.goto("/");
      await page.evaluate(() => window.localStorage.clear());
      await page.reload();
      await use(page);
    } finally {
      if (errors.length) {
        await testInfo.attach("pageerrors", {
          body: errors.join("\n\n"),
          contentType: "text/plain",
        });
      }
      expect(errors, "Необработанные ошибки браузера за весь тест").toEqual([]);
    }
  },
});

export { expect };

export async function loginEmployee(page: Page, employeeId = "E0028") {
  await page.goto("/");
  await page.getByPlaceholder("Имя, ID или роль").fill(employeeId);
  const person = page.getByRole("button").filter({ hasText: employeeId });
  await expect(person).toHaveCount(1);
  await person.click();
  // the password field is prefilled with the demo password; the server verifies it
  await page.locator("#login-password-form").getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page).toHaveURL(/\/me$/);
  // Some profiles prefer KK/EN; the common test vocabulary is Russian.
  await page.getByRole("group", { name: "language" }).getByRole("button", { name: "RU", exact: true }).click();
  await expect(page.locator(".hero h1")).toBeVisible();
  await expect(page.locator("header")).toContainText(employeeId);
  await expect(page.locator(".hero .readiness .num")).toHaveText(/^\d+(?:\.\d+)?%$/);
}

export async function loginHr(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Войти как HR", exact: true }).click();
  await page.locator("#login-password-form").getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page).toHaveURL(/\/hr$/);
  await expect(page.locator(".card-stat")).toHaveCount(4);
}

export async function waitForAiSettled(page: Page) {
  const status = page.locator(".ai-status");
  await expect(status).toHaveClass(/\b(live|fallback)\b/, { timeout: 25_000 });
  await expect.poll(() => pendingAi.get(page)?.size ?? 0, {
    message: "AI-запрос завершён; карточки больше не переставляются",
    timeout: 25_000,
  }).toBe(0);
  await expect(status).toHaveClass(/\b(live|fallback)\b/);
  test.info().annotations.push({ type: "AI status", description: await status.innerText() });
}

export async function completePredictedStep(page: Page) {
  await waitForAiSettled(page);
  const readiness = page.locator(".hero .readiness .num");
  const beforeText = (await readiness.innerText()).replace(/\s/g, "");
  const main = page.locator("article.rec.main");
  const title = await main.locator(".title").innerText();
  await main.getByRole("button", { name: "Что изменится?", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("Прогноз, данные не меняются", { exact: true })).toBeVisible();
  const prediction = dialog.locator(".readiness .num");
  await expect(prediction).toHaveText(/^\d+(?:\.\d+)?→\d+(?:\.\d+)?%$/);
  const match = (await prediction.innerText()).replace(/\s/g, "").match(/^(\d+(?:\.\d+)?)→(\d+(?:\.\d+)?)%$/);
  expect(match, "Модальное окно содержит готовность до и после шага").not.toBeNull();
  const [, before, after] = match!;
  expect(`${before}%`).toBe(beforeText);
  expect(Number(after), "Для выбранного шага прогнозируется рост готовности").toBeGreaterThan(Number(before));
  await expect(dialog.locator(".step-title")).toHaveText(title);
  await expect(readiness).toHaveText(beforeText);
  await dialog.getByRole("button", { name: "Закрыть", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(main.locator(".title")).toHaveText(title);

  const updatedSnapshot = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/py/employees/E0028" && response.request().method() === "POST",
  );
  // Register before the click: this must be a new AI response for the completion,
  // not the already settled status of the previous recommendation.
  const updatedAi = page.waitForResponse((response) =>
    new URL(response.url()).pathname === "/api/py/employees/E0028/ai" && response.request().method() === "POST",
  );
  await main.getByRole("button", { name: "Отметить выполненным", exact: true }).click();
  expect((await updatedSnapshot).status()).toBe(200);
  await expect(readiness).toHaveText(`${after}%`);
  const toast = page.getByRole("status");
  await expect(toast).toBeVisible();
  await expect(toast).toContainText(`${before}% → ${after}%`);
  const aiResponse = await updatedAi;
  expect(aiResponse.status()).toBe(200);
  const ai = await aiResponse.json();
  test.info().annotations.push({
    type: "AI after completion",
    description: `${ai.ai_status}; model=${ai.model || "none"}; cached=${!!ai.cached}`,
  });
  await waitForAiSettled(page);
  await expect(page.locator("article.rec.main .title")).not.toHaveText(title);
  test.info().annotations.push({ type: "Readiness", description: `${title}: ${before}% → ${after}%` });
  return { before, after, title };
}

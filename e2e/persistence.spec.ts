import { test, expect, loginEmployee, completePredictedStep, waitForAiSettled } from "./helpers";

test("reload /me сохраняет вход и готовность после выполнения шага", async ({ page }) => {
  await loginEmployee(page);
  const name = await page.locator(".hero h1").innerText();
  const { after, title } = await completePredictedStep(page);

  await page.reload();
  await expect(page).toHaveURL(/\/me$/);
  await expect(page.locator(".hero h1")).toHaveText(name);
  await expect(page.locator("header")).toContainText("E0028");
  await expect(page.getByRole("button", { name: "Выйти", exact: true })).toBeVisible();
  await expect(page.locator(".hero .readiness .num")).toHaveText(`${after}%`);
  await waitForAiSettled(page);
  await expect(page.locator("article.rec.main .title")).not.toHaveText(title);

  await page.getByRole("navigation").getByRole("button", { name: "История", exact: true }).click();
  const completion = page.getByRole("row").filter({ hasText: title }).filter({ hasText: "отмечено в приложении" });
  await expect(completion).toHaveCount(1);
  await expect(completion).toContainText("завершено");
});

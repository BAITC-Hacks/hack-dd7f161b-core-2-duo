import { test, expect, loginEmployee, completePredictedStep } from "./helpers";

test("what-if прогноз совпадает с выполнением; toast и обновлённый AI не вызывают pageerror", async ({ page }) => {
  await loginEmployee(page);
  const { after } = await completePredictedStep(page);
  await expect(page.locator(".hero .readiness .num")).toHaveText(`${after}%`);
  await expect(page.locator("article.rec.main")).toBeVisible();
});

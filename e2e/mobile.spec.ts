import type { Page } from "@playwright/test";
import { expect, loginEmployee, loginHr, test, waitForAiSettled } from "./helpers";

test.use({ viewport: { width: 360, height: 780 } });

async function expectNoHorizontalScroll(page: Page) {
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
  await expect
    .poll(
      () =>
        page.evaluate(() => {
          const root = document.documentElement;
          return root.scrollWidth - root.clientWidth;
        }),
      { message: "Document scrollWidth must not exceed clientWidth at 360 × 780" },
    )
    .toBeLessThanOrEqual(0);
}

test("employee path fits a 360 × 780 viewport", async ({ page }) => {
  await loginEmployee(page);
  await expect(page).toHaveURL(/\/me$/);
  await expect(page.getByRole("heading", { name: "Готовность по навыкам", exact: true })).toBeVisible();
  await waitForAiSettled(page);
  await expectNoHorizontalScroll(page);
});

test("HR dashboard fits a 360 × 780 viewport", async ({ page }) => {
  await loginHr(page);
  await expect(page).toHaveURL(/\/hr$/);
  await expect(
    page.getByRole("heading", { name: "Какие навыки проседают и что мешает их развивать", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  await expectNoHorizontalScroll(page);
});

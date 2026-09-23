import { expect, loginEmployee, test } from "./helpers";

test("employee cannot view another employee through an HR profile URL", async ({ page }) => {
  await loginEmployee(page, "E0028");

  const forbiddenResponse = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/py/employees/E0001" &&
      response.request().method() === "POST",
  );
  await page.goto("/hr/employee/E0001");
  const response = await forbiddenResponse;

  expect(response.status()).toBe(403);
  expect(response.request().headers()["x-role"]).toBe("employee");
  expect(response.request().headers()["x-actor"]).toBe("E0028");
  await expect(page.getByText("Нет доступа к этому профилю", { exact: true })).toBeVisible();

  // The denied route must show neither the other employee's profile nor their development data.
  const main = page.getByRole("main");
  await expect(main.getByRole("heading", { level: 1 })).toHaveCount(0);
  await expect(main.getByRole("heading", { name: "Готовность по навыкам", exact: true })).toHaveCount(0);
  await expect(main.getByRole("button", { name: "Изменить цель", exact: true })).toHaveCount(0);
  await expect(main.getByRole("button", { name: "Отметить выполненным", exact: true })).toHaveCount(0);
});

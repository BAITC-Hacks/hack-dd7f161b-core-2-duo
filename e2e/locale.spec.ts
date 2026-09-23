import { expect, loginEmployee, test, waitForAiSettled } from "./helpers";

test("employee can switch navigation from Russian to Kazakh and English", async ({ page }) => {
  await loginEmployee(page);
  await waitForAiSettled(page);
  const languages = page.getByRole("group", { name: "language", exact: true });
  const navigation = page.getByRole("navigation");

  await expect(languages.getByRole("button", { name: "RU", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(navigation.getByRole("button", { name: "Мой путь", exact: true })).toHaveAttribute("aria-current", "page");

  await languages.getByRole("button", { name: "KK", exact: true }).click();
  await expect(languages.getByRole("button", { name: "KK", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(navigation.getByRole("button", { name: "Менің жолым", exact: true })).toBeVisible();
  await expect(navigation.getByRole("button", { name: "Менің жолым", exact: true })).toHaveAttribute("aria-current", "page");
  await expect(navigation.getByRole("button", { name: "Мой путь", exact: true })).toHaveCount(0);
  await waitForAiSettled(page);

  await languages.getByRole("button", { name: "EN", exact: true }).click();
  await expect(languages.getByRole("button", { name: "EN", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(navigation.getByRole("button", { name: "My path", exact: true })).toBeVisible();
  await expect(navigation.getByRole("button", { name: "My path", exact: true })).toHaveAttribute("aria-current", "page");
  await expect(navigation.getByRole("button", { name: "Менің жолым", exact: true })).toHaveCount(0);
  await waitForAiSettled(page);
});

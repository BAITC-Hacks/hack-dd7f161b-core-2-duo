import { expect, test } from "./helpers";

test("theme switch changes the page background and persists the choice", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  const themeSwitch = page.getByRole("group", { name: "Тема оформления", exact: true });
  const background = () => page.locator("body").evaluate((body) => getComputedStyle(body).backgroundColor);
  await themeSwitch.getByRole("button", { name: "Светлая", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  const lightBackground = await background();

  await themeSwitch.getByRole("button", { name: "Тёмная", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect.poll(background).not.toBe(lightBackground);
  const darkBackground = await background();
  expect(await page.evaluate(() => localStorage.getItem("career-quest:theme"))).toBe("dark");

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(themeSwitch.getByRole("button", { name: "Тёмная", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect.poll(background).toBe(darkBackground);

});

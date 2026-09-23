import { chromium } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const baseURL = process.env.THEME_BASE_URL || "http://localhost:3200";
const output = path.resolve("docs/evidence/theme");
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const results = [];

async function audit(page) {
  return page.evaluate(() => {
    const rgb = (value) => {
      const channels = value.match(/[\d.]+/g)?.map(Number);
      return channels && channels.length >= 3 ? [...channels.slice(0, 3), channels[3] ?? 1] : [0, 0, 0, 0];
    };
    const composite = (front, back) => {
      const alpha = front[3] + back[3] * (1 - front[3]);
      return [...front.slice(0, 3).map((v, i) => (v * front[3] + back[i] * back[3] * (1 - front[3])) / (alpha || 1)), alpha];
    };
    const luminance = (color) => color.slice(0, 3).map((v) => v / 255).map((v) => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4).reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
    const ratio = (a, b) => {
      const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
      return (hi + 0.05) / (lo + 0.05);
    };
    const failures = [];
    let checked = 0;
    let minimum = Infinity;
    for (const element of document.querySelectorAll("body *")) {
      if (element.closest("nextjs-portal") || ["OPTION", "SCRIPT", "STYLE", "NOSCRIPT"].includes(element.tagName)) continue;
      const ownText = [...element.childNodes].filter((n) => n.nodeType === Node.TEXT_NODE).map((n) => n.textContent).join(" ").trim();
      if (!ownText) continue;
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      if (style.visibility !== "visible" || !rect.width || !rect.height) continue;
      let background = [0, 0, 0, 0];
      let opacity = 1;
      for (let current = element; current; current = current.parentElement) {
        const css = getComputedStyle(current);
        background = composite(background, rgb(css.backgroundColor));
        opacity *= Number(css.opacity);
      }
      background = composite(background, [255, 255, 255, 1]);
      let foreground = rgb(style.color);
      if (element instanceof SVGElement) {
        foreground = rgb(style.fill);
        const nodeRect = element.closest(".graph-node")?.querySelector("rect");
        if (nodeRect) background = composite(rgb(getComputedStyle(nodeRect).fill), background);
      }
      foreground[3] *= opacity;
      const contrast = ratio(composite(foreground, background), background);
      checked++;
      minimum = Math.min(minimum, contrast);
      if (contrast < 4.5) failures.push({ text: ownText.slice(0, 100), selector: `${element.tagName.toLowerCase()}.${String(element.getAttribute("class") || "").replaceAll(" ", ".")}`, foreground: style.color, background: background.slice(0, 3).map(Math.round), contrast: Number(contrast.toFixed(2)) });
    }
    return { checked, minimum: Number(minimum.toFixed(2)), failures, viewport: innerWidth, documentWidth: document.documentElement.scrollWidth };
  });
}

async function capture(page, name, theme, width, fullPage = true) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(100);
  const filename = `${theme}-${width}-${name}.png`;
  await page.screenshot({ path: path.join(output, filename), fullPage, animations: "disabled" });
  const result = { screenshot: filename, theme, width, ...(await audit(page)) };
  results.push(result);
  console.log(`${filename}: ${result.checked} text samples, min ${result.minimum}, failures ${result.failures.length}, width ${result.documentWidth}`);
}

async function loginEmployee(page, theme, width) {
  await page.getByPlaceholder("Имя, ID или роль").fill("E0028");
  await page.getByRole("button").filter({ hasText: "E0028" }).click();
  await capture(page, "login-selected", theme, width);
  await page.locator("#login-password-form").getByRole("button", { name: "Войти", exact: true }).click();
  await page.waitForURL("**/me");
  await page.getByRole("group", { name: "language" }).getByRole("button", { name: "RU", exact: true }).click();
  await page.locator(".hero .readiness .num").waitFor();
  await page.locator(".ai-status.fallback, .ai-status.live").waitFor({ timeout: 40000 });
}

try {
  for (const width of [1440, 360]) {
    for (const theme of ["light", "dark"]) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, locale: "ru-RU", colorScheme: theme });
      await context.addInitScript((value) => localStorage.setItem("career-quest:theme", value), theme);
      const page = await context.newPage();
      page.setDefaultTimeout(30000);
      await page.goto(baseURL);
      await page.locator(".person").first().waitFor();
      await capture(page, "login", theme, width);
      await loginEmployee(page, theme, width);
      await capture(page, "me-path", theme, width);
      const main = page.locator("article.rec.main");
      await main.getByRole("button", { name: "Почему этот шаг?", exact: true }).click();
      await main.locator(".evidence").waitFor();
      await capture(page, "me-why", theme, width);
      await main.getByRole("button", { name: "Почему этот шаг?", exact: true }).click();
      await main.getByRole("button", { name: "Почему не другой?", exact: true }).click();
      await capture(page, "me-why-not", theme, width);
      await main.getByRole("button", { name: "Почему не другой?", exact: true }).click();
      await main.getByRole("button", { name: "Что изменится?", exact: true }).click();
      await page.locator(".modal .readiness .num").waitFor();
      await capture(page, "me-what-if", theme, width, false);
      await page.locator(".modal").getByRole("button", { name: "Закрыть", exact: true }).click();
      await page.locator(".career-graph").evaluate((element) => element.scrollIntoView({ block: "start" }));
      await capture(page, "career-graph", theme, width, false);
      if (width === 360) {
        await page.locator(".graph-toggle").click();
        await page.locator(".graph-viewport").scrollIntoViewIfNeeded();
        await capture(page, "career-graph-svg", theme, width, false);
      }
      await page.locator(".chat-launcher").click();
      await page.locator(".chat-panel").waitFor();
      await page.locator(".chat-suggestions button").first().click();
      await page.locator(".chat-form button[type=submit]").click();
      await page.locator(".chat-message.assistant").waitFor();
      await capture(page, "chat", theme, width, false);
      await page.getByRole("button", { name: "Закрыть чат", exact: true }).click();
      for (const [label, slug] of [["Активности", "activities"], ["История", "history"], ["Настройки", "settings"]]) {
        await page.locator(".sidenav").getByRole("button", { name: label, exact: true }).click();
        await page.evaluate(() => scrollTo(0, 0));
        await capture(page, `me-${slug}`, theme, width);
      }
      await page.getByRole("button", { name: "Выйти", exact: true }).click();
      await page.waitForURL(baseURL + "/");
      await page.getByRole("button", { name: "Войти как HR", exact: true }).click();
      await page.locator("#login-password-form").getByRole("button", { name: "Войти", exact: true }).click();
      await page.waitForURL("**/hr");
      await page.locator(".card-stat").first().waitFor();
      for (const [label, slug] of [["Навыки и ограничения", "skills"], ["Нет шага", "team"], ["Участие", "participation"], ["Данные", "data"]]) {
        await page.locator(".sidenav").getByRole("button", { name: label, exact: true }).click();
        await page.evaluate(() => scrollTo(0, 0));
        await capture(page, `hr-${slug}`, theme, width);
        if (slug === "team") {
          await page.getByRole("link", { name: "Открыть профиль", exact: true }).first().click();
          await page.locator(".hero .readiness .num").waitFor();
          await capture(page, "hr-employee", theme, width);
          await page.getByRole("link", { name: "← Назад", exact: true }).click();
          await page.locator(".card-stat").first().waitFor();
        }
      }
      await context.close();
    }
  }
} finally {
  await writeFile(path.join(output, "contrast-audit.json"), JSON.stringify({ capturedAt: new Date().toISOString(), baseURL, note: "Computed text/background samples including disabled controls and SVG text. Gradients, overlap and antialiasing still require visual inspection.", results }, null, 2) + "\n");
  const states = [...new Set(results.map((result) => result.screenshot.replace(/^(light|dark)-\d+-/, "").replace(/\.png$/, "")))];
  const links = states.map((state) => `| ${state} | ${[1440, 360].flatMap((width) => ["light", "dark"].map((theme) => {
    const filename = `${theme}-${width}-${state}.png`;
    return results.some((result) => result.screenshot === filename) ? `[PNG](${filename})` : "Неприменимо";
  })).join(" | ")} |`);
  await writeFile(path.join(output, "README.md"), [
    "# Скриншоты светлой и тёмной темы",
    "",
    `Снято состояний: ${results.length}. Проверено текстовых образцов: ${results.reduce((total, result) => total + result.checked, 0)}. Результатов контраста ниже 4.5:1: ${results.flatMap((result) => result.failures).length}.`,
    "",
    "Размер окна: 1440 x 900 или 360 x 900. Полные страницы сохранены целиком; модальное окно, граф и чат сняты в пределах окна. Горизонтальные таблицы и SVG на телефоне прокручиваются внутри контейнера. Чат использует реальный ответ без OPENAI_API_KEY.",
    "",
    "Повтор: `THEME_BASE_URL=http://localhost:3200 node scripts/capture-theme.mjs` при запущенных Next.js и API.",
    "",
    "Контраст вычислен по getComputedStyle с альфа-композицией фона, включая disabled и SVG. Градиенты, перекрытия и сглаживание дополнительно проверяются визуально. Подробности: [contrast-audit.json](contrast-audit.json).",
    "",
    "| Экран | Светлая 1440 | Тёмная 1440 | Светлая 360 | Тёмная 360 |",
    "| --- | --- | --- | --- | --- |",
    ...links,
    "",
  ].join("\n"));
  await browser.close();
  const failures = results.reduce((total, result) => total + result.failures.length, 0);
  const overflow = results.filter((result) => result.documentWidth > result.width).length;
  if (results.length !== 66 || failures || overflow) {
    console.error(`Theme evidence failed: ${results.length}/66 screenshots, ${failures} contrast failures, ${overflow} overflowing pages.`);
    process.exitCode = 1;
  }
}

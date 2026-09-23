# Источники чисел и воспроизведение

Все результаты относятся к синтетическим данным. Дата среза набора не равна дате измерения. Новые запуски выполнялись из текущего worktree на `2e3cdf8143a303eaef3f6c1a48934e02d170c4e3`; revision production из этого не выводится. Реальные UTC-времена, команды и исходные ответы находятся внутри артефактов.

| Артефакт | Что подтверждает |
|---|---|
| [local_measurements.json](local_measurements.json) | Новый полный локальный обход, выбор профилей, исходные и конечные навыки, what-if, HR |
| [production_measurements.json](production_measurements.json) | Новая базовая серия API, Bearer-вход, допуск ролей, дубли отметок, импорт базового поднабора и открытых ловушек |
| [production_demo_measurements.json](production_demo_measurements.json) | Новые API-снимки выбранных профилей, прогноз главного шага и всей цепочки, выполнение и AI |
| [summary.json](summary.json) | Сводка обеих API-серий с исключением кэша и `not_needed` из новых вызовов, проверки и хеши источников |
| [regressions.json](regressions.json) | Новый локальный запуск без ключа, изменения fingerprint, остаточная нагрузка, ошибки дат и оценок |
| [pytest.txt](pytest.txt) | Реальный результат существующего набора Python-тестов |
| [e2e-results.json](e2e-results.json), [e2e.txt](e2e.txt) | Реальный прогон существующих браузерных тестов на production |
| [ruff.txt](ruff.txt) | Проверка Python-скриптов в docs после форматирования |
| [model_selection.md](model_selection.md) | Изложение прежнего сравнительного эксперимента, с источником и его хешем; новый сравнительный прогон не выполнялся |
| [evaluation_branch.md](evaluation_branch.md), [evaluation_branch.json](evaluation_branch.json) | Сохранённый запуск другой ветки; исходники ядра совпали по SHA-256, повторный запуск здесь не выполнялся |

Последовательные production-серии завершены до запуска Playwright, чтобы браузерный прогон не добавлял нашу параллельную нагрузку к этим измерениям. Другие посетители и нагрузка платформы не контролировались. `elapsed_ms` кэшированного ответа относится к исходной генерации; повторные контрольные `repeat_ai` не входят в сводку задержки. HTTP-снимок содержит отображаемые навыки, а simulate — полный вектор: production-сравнение ограничено отображаемыми навыками. Полный вектор отдельно проверен локально.

Токены входа и ключ OpenAI не сохранялись в JSON и логах. Трассы Playwright отключены, поскольку могут включать заголовок авторизации. Сравнение моделей — историческое свидетельство; `live_validated` означает только прохождение реализованного серверного валидатора.

## Команды

Из корня проекта, Python с зависимостями проекта:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 docs/measure_demo.py
PYTHONDONTWRITEBYTECODE=1 python3 docs/measure_production.py
PYTHONDONTWRITEBYTECODE=1 python3 docs/measure_production.py --output docs/evidence/production_demo_measurements.json --skip-import E0143 E0176 E0041 E0004
PYTHONDONTWRITEBYTECODE=1 python docs/measure_regressions.py
PYTHONDONTWRITEBYTECODE=1 python3 docs/measure_summary.py
```

`measure_production.py` заново входит через `POST /api/py/auth/login`, передаёт токен через stdin curl и сохраняет ответ входа без токена. TLS проверяется; повторных попыток и принудительного обхода AI-кэша нет. Запуск перезаписывает соответствующую серию, поэтому при новом измерении следует обновить числа в документах.

Для этой работы использовались уже существующие зависимости из соседнего scratch-окружения; в корне worktree зависимости не устанавливались. Фактическая команда pytest:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/assylkhan/Desktop/hackalem/project-tz/codex/runtime/venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=docs/evidence/pytest-temp
```

Этим же Python выполнен `docs/measure_regressions.py`. Фактический браузерный запуск:

```bash
mkdir -p docs/evidence/runtime
NODE_PATH=/Users/assylkhan/Desktop/hackalem/project-tz/codex/runtime/audit-66c3e3c/node_modules \
PLAYWRIGHT_BROWSERS_PATH=/Users/assylkhan/Desktop/hackalem/project-tz/codex/runtime/browsers \
PWTEST_CACHE_DIR="$PWD/docs/evidence/runtime/playwright-cache" \
TMPDIR="$PWD/docs/evidence/runtime" \
E2E_BASE_URL=https://career-quest-bay.vercel.app \
node /Users/assylkhan/Desktop/hackalem/project-tz/codex/runtime/audit-66c3e3c/node_modules/@playwright/test/cli.js test --config=docs/playwright.production.config.ts
```

Конфигурация запускает **текущие файлы `e2e/` этого worktree**, не тесты scratch-копии. При уже установленных зависимостях проекта та же конфигурация доступна через `npm run e2e -- --config=docs/playwright.production.config.ts`. Технические времена прохождения тестов не являются latency отдельного UI-действия. Временные кеши не включены в пакет доказательств.

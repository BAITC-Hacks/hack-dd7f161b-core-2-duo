import type { Locale } from "./store";

type Dict = Record<string, string>;

const ru: Dict = {
  product: "Career Quest",
  synthetic: "Синтетические данные",
  asOf: "Дата среза",
  scenarioBase: "Исходный набор",
  scenarioCheck: "Проверочный сценарий",
  logout: "Выйти",
  loginTitle: "Куда вы идёте дальше — и почему именно этот шаг",
  loginLead:
    "Навигатор развития: смотрит на ваш грейд, требования следующего уровня, реальные разрывы в навыках и историю участия — и предлагает 1–3 шага с объяснением.",
  asEmployee: "Войти как сотрудник",
  asHr: "Войти как HR",
  searchEmployee: "Имя, ID или роль",
  open: "Открыть",
  navPath: "Мой путь",
  navActivities: "Активности",
  navHistory: "История",
  navSettings: "Настройки",
  navTeam: "Нет шага",
  navSkills: "Навыки и ограничения",
  navParticipation: "Участие",
  navData: "Данные",
  tenure: "Стаж",
  months: "мес.",
  lastReview: "Последняя оценка",
  target: "Цель",
  src_profile: "Цель из профиля",
  src_user: "Цель выбрана вами",
  src_provisional_next_grade: "Цель не выбрана — рассчитан следующий грейд",
  src_current_role_maintenance: "Цель не выбрана — соответствие текущей роли",
  readiness: "Готовность по навыкам",
  readinessHint:
    "Взвешенное покрытие требований цели: критические навыки ×2. Это не вероятность повышения и не оценка работы.",
  critical: "Критические",
  criticalMet: "Критические требования закрыты",
  criticalOpen: "Критические требования не закрыты",
  changeGoal: "Изменить цель",
  resetGoal: "Сбросить цель",
  save: "Сохранить",
  nextStep: "Следующий шаг",
  mainStep: "Главный шаг",
  alternative: "Альтернатива",
  aiChecking: "AI проверяет выбор…",
  aiLive: "Выбор AI проверен сервером",
  aiFallback: "Рекомендация рассчитана по правилам; AI сейчас недоступен",
  ai_fallback_disabled: "ключ OpenAI не настроен",
  ai_fallback_timeout: "AI не ответил за 9 секунд",
  ai_fallback_unavailable: "сервис AI недоступен",
  ai_fallback_invalid_output: "ответ AI не прошёл проверку",
  why: "Почему этот шаг?",
  whyNot: "Почему не другой?",
  whatIf: "Что изменится?",
  markDone: "Отметить выполненным",
  snooze: "Не сейчас",
  unsnooze: "Вернуть",
  continue: "Продолжить",
  session: "Ближайшая сессия",
  selfPaced: "В своём темпе",
  hours: "ч",
  tier0: "Закрывает критический разрыв",
  tier1: "Закрывает разрыв цели",
  tier2: "Подготовительный шаг",
  noStep: "Сейчас нет исполнимого шага",
  route: "Маршрут до цели",
  routeHint: "Оценка последовательности, не бронирование. Self-paced — 4 ч/день, очные — ceil(ч/8) дней.",
  routeNone: "В пределах четырёх шагов и 120 дней маршрут не найден",
  plan_target_reached_in_plan: "Маршрут закрывает все требования цели",
  plan_partial_progress: "Маршрут даёт частичный прогресс",
  plan_no_path_found: "Маршрут не найден",
  plan_search_limited: "Поиск остановлен по лимиту",
  plan_not_run: "Требования цели уже выполнены",
  skills: "Навыки",
  allSkills: "Все навыки",
  targetSkills: "Навыки цели",
  assessed: "оценка",
  calculated: "расчёт",
  required: "нужно",
  gap: "разрыв",
  fromHistory: "по истории",
  proxyDate: "proxy-дата",
  achievements: "Личные достижения",
  gameLevel: "Игровой уровень",
  scoreBreakdown: "Разбор оценки кандидата",
  simTitle: "Прогноз, данные не меняются",
  readinessDelta: "Готовность",
  unlocks: "Откроется",
  close: "Закрыть",
  catalog: "Каталог активностей",
  eligible: "Доступно",
  blocked: "Недоступно",
  history: "История участия",
  status_completed: "завершено",
  status_in_progress: "в процессе",
  status_dropped: "брошено",
  status_no_show: "неявка",
  status_declined: "отказ",
  status_overdue: "просрочено",
  mandatory: "обязательное",
  voluntary: "добровольное",
  appRecord: "отмечено в приложении",
  settingsHistory: "Учитывать мою историю при подборе",
  settingsGaming: "Включить личные достижения (XP и бейджи)",
  settingsGamingHint: "Добровольно. Не влияет на навыки, готовность и рекомендации. Никто, кроме вас, не видит.",
  settingsLang: "Язык интерфейса",
  settingsReset: "Сбросить мои отметки в этом браузере",
  health: "Состояние истории развития",
  hr_employees: "Сотрудников",
  hr_open_critical: "С открытым критическим разрывом",
  hr_no_step: "Без исполнимого шага",
  hr_target_met: "Требования цели выполнены",
  hrSkillsTitle: "Какие навыки проседают и что мешает их развивать",
  hrNoStepTitle: "У кого нет рекомендованного шага и почему",
  hrPartTitle: "Участие по активностям",
  belowTarget: "ниже требования",
  criticalGapCount: "критических",
  providers: "активностей в каталоге",
  actionable: "есть шаг",
  bridgeCnt: "через подготовку",
  uncovered: "нет шага",
  intervention: "Что можно изменить в каталоге",
  completionShare: "Завершаемость",
  attendance: "Явка (proxy)",
  feedback: "Отзыв",
  observations: "наблюдений",
  uniqueEmployees: "сотрудников",
  uploadTitle: "Проверочный сценарий",
  uploadLead:
    "Загрузите employees.json и activity_history.csv в формате датасета. Будет создан изолированный сценарий: каталог и требования берутся из исходного набора, сотрудники и история — только из файлов.",
  chooseFiles: "Выбрать файлы",
  validate: "Проверить",
  commit: "Создать сценарий",
  switchBase: "Вернуться к исходному набору",
  switchCheck: "Открыть проверочный сценарий",
  errors: "Ошибки",
  warnings: "Предупреждения",
  openEmployee: "Открыть профиль",
  proof_catalog_fact: "факт каталога",
  proof_eligibility_fact: "условие допуска",
  proof_search_limit: "лимит поиска",
  proof_user_choice: "выбор сотрудника",
  loading: "Загрузка…",
  forbidden: "Нет доступа к этому профилю",
  back: "Назад",
  population: "Выборка",
};

const en: Dict = {
  ...ru,
  synthetic: "Synthetic data",
  asOf: "Snapshot date",
  scenarioBase: "Original dataset",
  scenarioCheck: "Check scenario",
  logout: "Sign out",
  loginTitle: "Where you go next, and why this step",
  loginLead:
    "A development navigator: it weighs your grade, the next level's requirements, real skill gaps and your participation history, and suggests 1–3 steps with reasons.",
  asEmployee: "Sign in as employee",
  asHr: "Sign in as HR",
  searchEmployee: "Name, ID or role",
  open: "Open",
  navPath: "My path",
  navActivities: "Activities",
  navHistory: "History",
  navSettings: "Settings",
  navTeam: "No next step",
  navSkills: "Skills & constraints",
  navParticipation: "Participation",
  navData: "Data",
  tenure: "Tenure",
  months: "mo",
  lastReview: "Last review",
  target: "Goal",
  src_profile: "Goal from profile",
  src_user: "Goal chosen by you",
  src_provisional_next_grade: "No goal set — next grade calculated",
  src_current_role_maintenance: "No goal set — current role fit",
  readiness: "Skill readiness",
  readinessHint: "Weighted coverage of goal requirements, critical skills ×2. Not a promotion probability.",
  critical: "Critical",
  criticalMet: "Critical requirements met",
  criticalOpen: "Critical requirements open",
  changeGoal: "Change goal",
  resetGoal: "Reset goal",
  save: "Save",
  nextStep: "Next step",
  mainStep: "Main step",
  alternative: "Alternative",
  aiChecking: "AI is checking the choice…",
  aiLive: "AI choice verified by the server",
  aiFallback: "Recommendation calculated by rules; AI is unavailable",
  ai_fallback_disabled: "OpenAI key is not configured",
  ai_fallback_timeout: "AI did not answer within 9 s",
  ai_fallback_unavailable: "AI service unavailable",
  ai_fallback_invalid_output: "AI answer failed validation",
  why: "Why this step?",
  whyNot: "Why not another?",
  whatIf: "What changes?",
  markDone: "Mark as done",
  snooze: "Not now",
  unsnooze: "Restore",
  continue: "Continue",
  session: "Next session",
  selfPaced: "Self-paced",
  hours: "h",
  tier0: "Closes a critical gap",
  tier1: "Closes a goal gap",
  tier2: "Preparatory step",
  noStep: "No executable step right now",
  route: "Route to goal",
  routeHint: "Sequence estimate, not a booking. Self-paced 4 h/day, scheduled ceil(h/8) days.",
  routeNone: "No route found within four steps and 120 days",
  plan_target_reached_in_plan: "Route meets every goal requirement",
  plan_partial_progress: "Route gives partial progress",
  plan_no_path_found: "No route found",
  plan_search_limited: "Search stopped at limit",
  plan_not_run: "Goal requirements already met",
  skills: "Skills",
  allSkills: "All skills",
  targetSkills: "Goal skills",
  assessed: "assessed",
  calculated: "calculated",
  required: "required",
  gap: "gap",
  fromHistory: "from history",
  proxyDate: "proxy date",
  achievements: "Personal achievements",
  gameLevel: "Game level",
  scoreBreakdown: "Candidate score breakdown",
  simTitle: "Projection, nothing is saved",
  readinessDelta: "Readiness",
  unlocks: "Unlocks",
  close: "Close",
  catalog: "Activity catalog",
  eligible: "Available",
  blocked: "Unavailable",
  history: "Participation history",
  status_completed: "completed",
  status_in_progress: "in progress",
  status_dropped: "dropped",
  status_no_show: "no-show",
  status_declined: "declined",
  status_overdue: "overdue",
  mandatory: "mandatory",
  voluntary: "voluntary",
  appRecord: "marked in app",
  settingsHistory: "Use my history when choosing steps",
  settingsGaming: "Turn on personal achievements (XP and badges)",
  settingsGamingHint: "Optional. Does not affect skills, readiness or recommendations. Only you see it.",
  settingsLang: "Interface language",
  settingsReset: "Reset my marks in this browser",
  health: "Development history status",
  hr_employees: "Employees",
  hr_open_critical: "With an open critical gap",
  hr_no_step: "Without an executable step",
  hr_target_met: "Goal requirements met",
  hrSkillsTitle: "Which skills fall short and what blocks their development",
  hrNoStepTitle: "Who has no recommended step and why",
  hrPartTitle: "Participation by activity",
  belowTarget: "below requirement",
  criticalGapCount: "critical",
  providers: "catalog activities",
  actionable: "have a step",
  bridgeCnt: "via preparation",
  uncovered: "no step",
  intervention: "What to change in the catalog",
  completionShare: "Completion",
  attendance: "Attendance (proxy)",
  feedback: "Feedback",
  observations: "observations",
  uniqueEmployees: "employees",
  uploadTitle: "Check scenario",
  uploadLead:
    "Upload employees.json and activity_history.csv in dataset format. An isolated scenario is created: catalog and requirements come from the original set, employees and history only from the files.",
  chooseFiles: "Choose files",
  validate: "Validate",
  commit: "Create scenario",
  switchBase: "Back to original dataset",
  switchCheck: "Open check scenario",
  errors: "Errors",
  warnings: "Warnings",
  openEmployee: "Open profile",
  proof_catalog_fact: "catalog fact",
  proof_eligibility_fact: "eligibility rule",
  proof_search_limit: "search limit",
  proof_user_choice: "employee choice",
  loading: "Loading…",
  forbidden: "No access to this profile",
  back: "Back",
  population: "Population",
};

const kk: Dict = {
  ...ru,
  synthetic: "Синтетикалық деректер",
  asOf: "Есеп күні",
  logout: "Шығу",
  loginTitle: "Келесі қадамыңыз қандай және неліктен дәл осы",
  loginLead:
    "Даму навигаторы: грейдіңізді, келесі деңгей талаптарын, дағдылардағы нақты алшақтықтарды және қатысу тарихын ескеріп, түсіндірмесімен 1–3 қадам ұсынады.",
  asEmployee: "Қызметкер ретінде кіру",
  asHr: "HR ретінде кіру",
  searchEmployee: "Аты, ID немесе рөл",
  open: "Ашу",
  navPath: "Менің жолым",
  navActivities: "Белсенділіктер",
  navHistory: "Тарих",
  navSettings: "Баптаулар",
  tenure: "Еңбек өтілі",
  months: "ай",
  lastReview: "Соңғы бағалау",
  target: "Мақсат",
  readiness: "Дағдылар бойынша дайындық",
  nextStep: "Келесі қадам",
  mainStep: "Негізгі қадам",
  alternative: "Балама",
  why: "Неліктен бұл қадам?",
  whyNot: "Неліктен басқасы емес?",
  whatIf: "Не өзгереді?",
  markDone: "Орындалды деп белгілеу",
  snooze: "Қазір емес",
  continue: "Жалғастыру",
  session: "Жақын сессия",
  selfPaced: "Өз қарқынымен",
  route: "Мақсатқа жол",
  skills: "Дағдылар",
  allSkills: "Барлық дағдылар",
  assessed: "бағалау",
  calculated: "есеп",
  required: "қажет",
  gap: "алшақтық",
  history: "Қатысу тарихы",
  settingsLang: "Интерфейс тілі",
  close: "Жабу",
  loading: "Жүктелуде…",
  back: "Артқа",
  aiLive: "AI таңдауы сервермен тексерілді",
  aiFallback: "Ұсыныс ережелер бойынша есептелді; AI қазір қолжетімсіз",
};

const dicts: Record<Locale, Dict> = { ru, en, kk };

export function translator(locale: Locale) {
  const d = dicts[locale] ?? ru;
  return (key: string) => d[key] ?? ru[key] ?? key;
}

export type T = ReturnType<typeof translator>;

type Fact = { id: string; category: string; code: string; values: Record<string, any> };

const GROUP: Record<Locale, Record<string, string>> = {
  ru: { format: "формат", type: "тип", skills: "похожие навыки" },
  en: { format: "format", type: "type", skills: "similar skills" },
  kk: { format: "формат", type: "түрі", skills: "ұқсас дағдылар" },
};

// server supplies codes and numbers; the text is rendered here from fixed templates
export function renderFact(f: Fact, locale: Locale, skill: (id: string) => string, event: (id: string) => string, t: T): string {
  const v = f.values;
  const L = locale === "en";
  switch (f.code) {
    case "PROFILE_CONTEXT":
      return L
        ? `You are ${v.role}, grade ${v.grade}, ${v.tenure_months} months in the company.`
        : `Вы ${v.role}, грейд ${v.grade}, стаж ${v.tenure_months} мес.`;
    case "TARGET_CONTEXT":
      return `${t("target")}: ${v.target_role} ${v.target_grade} — ${t("src_" + v.source).toLowerCase()}.`;
    case "REQUIREMENT":
      return L
        ? `${v.target_grade ?? "Goal"} requires ${skill(v.skill_id)} ≥ ${v.required}${v.critical ? " (critical)" : ""}.`
        : `Цель требует ${skill(v.skill_id)} не ниже ${v.required}${v.critical ? " — критический навык" : ""}.`;
    case "SKILL_GAP":
      return L
        ? `${skill(v.skill_id)}: now ${v.current} of ${v.required}, gap ${v.gap}.`
        : `${skill(v.skill_id)}: сейчас ${v.current} из ${v.required}, разрыв ${v.gap}.`;
    case "EVENT_EFFECT":
      return L
        ? `Completion gives ${skill(v.skill_id)} ${v.before}→${v.after} (gain ${v.gain}, cap ${v.cap})${v.gap_after != null ? `, gap after: ${v.gap_after}` : ""}.`
        : `Даст ${skill(v.skill_id)} ${v.before}→${v.after} (gain ${v.gain}, потолок ${v.cap})${v.gap_after != null ? `, разрыв после: ${v.gap_after}` : ""}.`;
    case "HISTORY_INSUFFICIENT":
      return L
        ? `Not enough similar history yet (${v.observations} voluntary records); history did not affect this choice.`
        : `Данных о похожих активностях пока недостаточно (${v.observations} добровольных записей) — история не повлияла на выбор.`;
    case "HISTORY_GROUP": {
      const g = GROUP[locale][v.group] ?? v.group;
      const neg = v.no_show + v.dropped + v.declined;
      return L
        ? `History, same ${g}: ${v.completed} completed, ${neg} missed/dropped/declined of ${v.n}; fit ${v.affinity}.`
        : `История (${g}): завершено ${v.completed}, пропущено/брошено/отказов ${neg} из ${v.n}; соответствие ${v.affinity}.`;
    }
    case "ELIGIBLE": {
      const pre = Object.entries(v.prerequisites || {})
        .map(([s, l]) => `${skill(s)} ≥ ${l}`)
        .join(", ");
      const when = v.session ? `${t("session")}: ${v.session}` : t("selfPaced");
      if (v.action_kind === "continue") return L ? `Already started — continue without re-enrolling.` : `Уже начато — можно продолжить без новой записи.`;
      return L
        ? `Open to your role and grade${pre ? `, prerequisites met (${pre})` : ""}. ${when}.`
        : `Доступно вашей роли и грейду${pre ? `, условия выполнены (${pre})` : ""}. ${when}.`;
    }
    case "UNLOCKS":
      return L
        ? `Unlocks next: ${v.event_ids.map(event).join(", ")}.`
        : `Откроет следующие шаги: ${v.event_ids.map(event).join(", ")}.`;
    case "CRITICAL_REMAINING":
      return (
        (L ? "Still open after this step: " : "После шага останется: ") +
        v.skills.map((s: any) => `${skill(s.skill_id)} ${s.after}/${s.required}`).join(", ")
      );
    default:
      return f.code;
  }
}

export const REASON_TEXT: Record<string, { ru: string; en: string }> = {
  TARGET_REQUIREMENTS_MET: { ru: "Все требования цели выполнены — выберите следующую цель", en: "All goal requirements are met — pick the next goal" },
  NO_RELEVANT_CATALOG_EVENT: { ru: "В каталоге нет активности, развивающей навык", en: "No catalog activity develops this skill" },
  SKILL_CAP_CEILING: { ru: "Текущие активности не дают прироста на этом уровне", en: "Current activities give no growth at this level" },
  AUDIENCE_MISMATCH: { ru: "Полезные активности закрыты для текущей роли/грейда", en: "Useful activities are not open to the current role/grade" },
  PREREQUISITES_UNMET: { ru: "Сначала нужен подготовительный уровень", en: "A preparatory level is needed first" },
  NO_UPCOMING_SESSION: { ru: "Нет будущих сессий", en: "No upcoming sessions" },
  ONLY_ALREADY_COMPLETED_EVENTS: { ru: "Все подходящие активности уже пройдены", en: "All suitable activities are already completed" },
  ALL_RELEVANT_ACTIONS_SNOOZED: { ru: "Сотрудник отложил подходящие шаги", en: "The employee snoozed the suitable steps" },
  ACTIVE_ACTIVITY_ALREADY_SELECTED: { ru: "Уже идёт подходящая активность", en: "A suitable activity is already in progress" },
  NO_PATH_WITHIN_HORIZON: { ru: "Маршрут не найден в пределах поиска", en: "No route within search limits" },
  NO_SKILL_PROVIDER: { ru: "В каталоге нет активности для навыка", en: "No catalog activity for the skill" },
  CAP_INSUFFICIENT: { ru: "Потолок активностей ниже требования", en: "Activity caps are below the requirement" },
  AUDIENCE_RESTRICTED: { ru: "Нужно согласовать доступ или расширить аудиторию", en: "Access or wider audience is needed" },
  SCHEDULE_UNAVAILABLE: { ru: "Нужна новая сессия", en: "A new session is needed" },
  PREREQUISITE_BLOCKED: { ru: "Нужен подготовительный модуль", en: "A preparatory module is needed" },
  CATALOG_EXHAUSTED: { ru: "Нужна следующая ступень обучения", en: "The next learning level is needed" },
  USER_DEFERRED: { ru: "Отложено сотрудником", en: "Deferred by employee" },
  MANDATORY: { ru: "Обязательное — назначает HR, не рекомендуется", en: "Mandatory — assigned by HR, not recommended" },
  ALREADY_COMPLETED: { ru: "Уже пройдено", en: "Already completed" },
  SNOOZED: { ru: "Отложено до следующего раза", en: "Snoozed" },
};

export function reasonText(code: string, locale: Locale) {
  const r = REASON_TEXT[code];
  if (!r) return code;
  return locale === "en" ? r.en : r.ru;
}

export const INTERVENTION_TEXT: Record<string, { ru: string; en: string }> = {
  create_learning_activity: { ru: "Создать учебную активность для навыка", en: "Create a learning activity for the skill" },
  add_advanced_level: { ru: "Добавить продвинутый уровень с более высоким потолком", en: "Add an advanced level with a higher cap" },
  agree_access_or_widen_audience: { ru: "Согласовать доступ или расширить аудиторию", en: "Agree access or widen the audience" },
  schedule_session: { ru: "Запланировать новую сессию", en: "Schedule a new session" },
  add_preparatory_module: { ru: "Добавить подготовительный модуль", en: "Add a preparatory module" },
  add_next_level_activity: { ru: "Добавить следующую ступень обучения", en: "Add the next learning level" },
  none_user_choice: { ru: "Действий не нужно — выбор сотрудника", en: "No action — employee's choice" },
};

export const HEALTH_TEXT: Record<string, { ru: string; en: string }> = {
  INSUFFICIENT_HISTORY: { ru: "Недостаточно данных для вывода о привычном формате", en: "Not enough data to infer a preferred format" },
  IN_PROGRESS: { ru: "Есть добровольная активность в процессе", en: "A voluntary activity is in progress" },
  RECENT_ACTIVITY: { ru: "Есть завершённая добровольная активность за последние 90 дней", en: "A voluntary activity was completed in the last 90 days" },
  FORMAT_REVIEW_SUGGESTED: { ru: "Несколько пропусков за 180 дней — стоит пересмотреть формат или нагрузку, а не мотивацию", en: "Several misses in 180 days — review format or load, not motivation" },
  NO_RECENT_COMPLETION_OBSERVED: { ru: "В загруженной истории не найдено завершений за 180 дней", en: "No completions found in the loaded history for 180 days" },
  OBSERVED_HISTORY_AVAILABLE: { ru: "История участия доступна", en: "Participation history available" },
};

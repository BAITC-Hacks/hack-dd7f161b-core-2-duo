export type GraphStatus = "available" | "in_progress" | "after_previous" | "blocked" | "completed" | "met" | "gap" | "support";
type BaseNode = { id: string; label: string; status: GraphStatus };
export type GraphEffect = { skill_id: string; before: number; after: number; actual: number; gain: number; cap: number };
export type ActivityNode = BaseNode & {
  kind: "activity";
  event_id: string;
  step: number | null;
  reasons: { code: string }[];
  prerequisites: { skill_id: string; current: number; required: number; met: boolean }[];
  effects: GraphEffect[];
  plan_step: { estimated_start: string; estimated_finish: string; changes: GraphEffect[] } | null;
  session: string | null;
  duration_hours: number;
  format: string;
};
export type SkillNode = BaseNode & {
  kind: "skill";
  skill_id: string;
  current: number;
  required: number | null;
  planned: number;
  critical: boolean;
};
export type GoalNode = BaseNode & { kind: "goal"; source: string };
export type GraphNode = ActivityNode | SkillNode | GoalNode;
export type GraphEdge = { id: string; source: string; target: string; kind: "requires" | "develops" | "prerequisite"; level?: number; gain?: number; cap?: number };
export type CareerGraphData = { nodes: GraphNode[]; edges: GraphEdge[] };

export const GRAPH_COPY = {
  ru: {
    title: "Career Graph", graph: "Граф зависимостей", list: "Маршрут и условия", scope: "Показать",
    route: "Шаги маршрута", catalog: "Связанный каталог", activity: "Активности", skill: "Навыки", goal: "Цель",
    hint: "Выберите узел — увидите его связи и условия. Tab — переход, Enter или пробел — выбор.",
    current: "Текущее состояние", forecast: "Прогноз маршрута", forecastHint: "Прогноз не меняет текущие навыки. Проверить его можно кнопкой «Что изменится?».",
    selected: "Выбранный узел", conditions: "Условия доступа", effects: "Эффект на текущем уровне", noConditions: "Предварительных требований нет",
    noRoute: "Маршрут не найден. Показаны требования цели и связанные активности с причинами ограничений.",
    noActivity: "В каталоге нет связанных добровольных активностей", noProvider: "В каталоге нет добровольной активности, развивающей этот навык",
    relation: "Связь", requires: "цель требует навык", develops: "активность развивает навык", prerequisite: "навык нужен для доступа",
    cap: "потолок", step: "Шаг", now: "Сейчас", after: "После маршрута", level: "Нужен уровень", remaining: "Остаётся после маршрута",
    available: "Доступно", in_progress: "В процессе", after_previous: "После предыдущих шагов", blocked: "Заблокировано",
    completed: "Уже завершено", met: "Условия выполнены", gap: "Есть невыполненные условия", support: "Дополнительный навык",
  },
  en: {
    title: "Career Graph", graph: "Dependency graph", list: "Route & conditions", scope: "Show",
    route: "Route steps", catalog: "Related catalog", activity: "Activities", skill: "Skills", goal: "Goal",
    hint: "Select a node to inspect its links and conditions. Tab to navigate; Enter or Space to select.",
    current: "Current state", forecast: "Route projection", forecastHint: "A projection does not change current skills. Use “What changes?” to simulate it.",
    selected: "Selected node", conditions: "Prerequisites", effects: "Effect at current level", noConditions: "No prerequisites",
    noRoute: "No route found. Goal requirements and related activities are shown with their constraints.",
    noActivity: "No related voluntary activities in the catalog", noProvider: "No voluntary catalog activity develops this skill",
    relation: "Relation", requires: "goal requires skill", develops: "activity develops skill", prerequisite: "skill needed for access",
    cap: "cap", step: "Step", now: "Now", after: "After route", level: "Required level", remaining: "Still open after route",
    available: "Available", in_progress: "In progress", after_previous: "After earlier steps", blocked: "Blocked",
    completed: "Already completed", met: "Requirements met", gap: "Open requirements", support: "Additional skill",
  },
  kk: {
    title: "Career Graph", graph: "Тәуелділіктер графы", list: "Маршрут пен шарттар", scope: "Көрсету",
    route: "Маршрут қадамдары", catalog: "Қатысты каталог", activity: "Белсенділіктер", skill: "Дағдылар", goal: "Мақсат",
    hint: "Байланыстар мен шарттарды көру үшін түйінді таңдаңыз. Tab — ауысу, Enter немесе бос орын — таңдау.",
    current: "Ағымдағы күй", forecast: "Маршрут болжамы", forecastHint: "Болжам ағымдағы дағдыларды өзгертпейді. «Не өзгереді?» арқылы тексеріңіз.",
    selected: "Таңдалған түйін", conditions: "Қолжетімділік шарттары", effects: "Ағымдағы деңгейдегі әсер", noConditions: "Алдын ала талаптар жоқ",
    noRoute: "Маршрут табылмады. Мақсат талаптары мен қатысты белсенділіктер шектеулерімен көрсетілген.",
    noActivity: "Каталогта қатысты ерікті белсенділіктер жоқ", noProvider: "Каталогта бұл дағдыны дамытатын ерікті белсенділік жоқ",
    relation: "Байланыс", requires: "мақсат дағдыны талап етеді", develops: "белсенділік дағдыны дамытады", prerequisite: "қолжетімділікке қажетті дағды",
    cap: "шегі", step: "Қадам", now: "Қазір", after: "Маршруттан кейін", level: "Қажетті деңгей", remaining: "Маршруттан кейін қалады",
    available: "Қолжетімді", in_progress: "Орындалуда", after_previous: "Алдыңғы қадамдардан кейін", blocked: "Бұғатталған",
    completed: "Аяқталған", met: "Шарттар орындалды", gap: "Орындалмаған шарттар бар", support: "Қосымша дағды",
  },
};

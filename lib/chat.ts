import type { SimulationData } from "@/components/SimulationResult";

export type ChatResponse = {
  intent: "simulate" | "explain" | "refuse";
  reply_text: string;
  simulation: SimulationData | null;
  ai_status: string;
};

export const CHAT_COPY = {
  ru: {
    title: "Спроси о развитии", subtitle: "Прогноз шага или объяснение термина",
    intro: "Могу показать, что изменится после одной доступной активности, или объяснить термин платформы. Это прогноз - отметки о выполнении не меняются.",
    placeholder: "Что такое readiness? Или: а если я пройду…",
    label: "Ваш вопрос о развитии", send: "Отправить", close: "Закрыть чат", clear: "Очистить",
    glossary: "Что такое readiness?", scenario: "А что если я пройду {title}?", scenarioButton: "Прогноз: {title}",
    thinking: "Разбираю вопрос…", you: "Вы", bot: "Career Quest", log: "Сообщения чата",
    privacy: "История хранится в памяти этой вкладки. Для ответа AI получает вопрос, последние сообщения и краткий контекст без имени.",
    unavailable: "AI сейчас недоступен, попробуйте позже. Можно воспользоваться кнопкой «Что изменится?» на карточке активности.",
    stale: "Состояние профиля изменилось. Повторите запрос, чтобы получить актуальный прогноз.",
  },
  en: {
    title: "Ask about development", subtitle: "Project a step or understand a term",
    intro: "I can project the effect of one available activity or explain a platform term. Projections do not mark activities complete.",
    placeholder: "What is readiness? Or: what if I complete…",
    label: "Your development question", send: "Send", close: "Close chat", clear: "Clear",
    glossary: "What is readiness?", scenario: "What if I complete {title}?", scenarioButton: "Project: {title}",
    thinking: "Reading your question…", you: "You", bot: "Career Quest", log: "Chat messages",
    privacy: "History stays in this tab's memory. AI receives your question, recent messages and a short context without your name.",
    unavailable: "AI is unavailable right now. Please try later, or use What will change? on an activity card.",
    stale: "Your profile state has changed. Ask again for an up-to-date projection.",
  },
  kk: {
    title: "Даму туралы сұра", subtitle: "Қадам болжамы немесе термин түсіндірмесі",
    intro: "Бір қолжетімді белсенділіктен кейін не өзгеретінін көрсете аламын немесе платформа терминін түсіндіремін. Болжам аяқталу белгілерін өзгертпейді.",
    placeholder: "Readiness деген не? Немесе: егер мен…",
    label: "Даму туралы сұрағыңыз", send: "Жіберу", close: "Чатты жабу", clear: "Тазарту",
    glossary: "Readiness деген не?", scenario: "Егер мен {title} аяқтасам не өзгереді?", scenarioButton: "Болжам: {title}",
    thinking: "Сұрақты талдап жатырмын…", you: "Сіз", bot: "Career Quest", log: "Чат хабарламалары",
    privacy: "Тарих осы қойынды жадында сақталады. AI сұрақты, соңғы хабарламаларды және аты-жөнсіз қысқа контексті алады.",
    unavailable: "AI қазір қолжетімсіз, кейінірек қайталап көріңіз. Белсенділік карточкасындағы «Не өзгереді?» батырмасын қолдануға болады.",
    stale: "Профиль күйі өзгерді. Жаңартылған болжам үшін сұрақты қайталаңыз.",
  },
};

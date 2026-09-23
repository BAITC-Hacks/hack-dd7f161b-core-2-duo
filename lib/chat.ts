import type { SimulationData } from "@/components/SimulationResult";

export type ChatResponse = {
  intent: "simulate" | "explain" | "status" | "refuse";
  reply_text: string;
  simulation: SimulationData | null;
  ai_status: string;
  suggestions?: { event_id: string; title: string }[];
  locale?: "ru" | "kk" | "en";
};

export const CHAT_COPY = {
  ru: {
    title: "Спроси о развитии", subtitle: "Прогноз шага или объяснение термина",
    intro: "Спросите, проходили ли вы курс, что изменится после обучения или что означает термин. Можно писать своими словами и выбирать предложенные варианты.",
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
    intro: "Ask whether you completed a course, what would change after learning, or what a platform term means. Use your own words or select a suggested option.",
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
    intro: "Курсты аяқтағаныңызды, оқудан кейін не өзгеретінін немесе термин мағынасын сұраңыз. Өз сөзіңізбен жазыңыз немесе ұсынылған нұсқаны таңдаңыз.",
    placeholder: "Readiness деген не? Немесе: егер мен…",
    label: "Даму туралы сұрағыңыз", send: "Жіберу", close: "Чатты жабу", clear: "Тазарту",
    glossary: "Readiness деген не?", scenario: "Егер мен {title} аяқтасам не өзгереді?", scenarioButton: "Болжам: {title}",
    thinking: "Сұрақты талдап жатырмын…", you: "Сіз", bot: "Career Quest", log: "Чат хабарламалары",
    privacy: "Тарих осы қойынды жадында сақталады. AI сұрақты, соңғы хабарламаларды және аты-жөнсіз қысқа контексті алады.",
    unavailable: "AI қазір қолжетімсіз, кейінірек қайталап көріңіз. Белсенділік карточкасындағы «Не өзгереді?» батырмасын қолдануға болады.",
    stale: "Профиль күйі өзгерді. Жаңартылған болжам үшін сұрақты қайталаңыз.",
  },
};

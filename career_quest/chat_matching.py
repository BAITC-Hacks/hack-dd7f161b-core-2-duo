"""Small catalog lookup, including informal names. Never calculates development effects."""

import re
from difflib import SequenceMatcher

ALIASES = {
    r"систем\w*\s*дизайн\w*|проектировани\w*\s+систем\w*|жүйел\w*\s*дизайн\w*|жүйе\w*\s+жобалау": "system design",
    r"хай\s*ло[ау]д\w*|высоконагруженн\w*|жоғары\s+жүктем\w*|highload": "high load",
    r"кубер\w*|k8s": "kubernetes",
    r"питон\w*|пайтон\w*": "python",
    r"тайпскрипт\w*|тайп\s*скрипт\w*": "typescript",
    r"реакт\w*": "react",
    r"ск[ью]л|эс\s*кью\s*эл": "sql",
    r"публичн\w*\s+выступлен\w*|ораторск\w*|көпшілік\s+алдында\s+сөйле\w*|шешендік": "public speaking",
    r"лидерств\w*|көшбасш\w*": "leadership",
    r"ментор\w*|наставнич\w*|тәлімгер\w*": "mentor",
    r"переговор\w*|келіссөз\w*": "negotiation",
    r"тайм\s*менеджмент\w*|управлени\w*\s+времен\w*|уақыт\w*\s+басқар\w*": "time priority management",
    r"автоматизаци\w*\s+тест\w*|автотест\w*|тестілеу\w*\s+автоматтандыр\w*": "test automation",
    r"нагрузочн\w*\s+тест\w*": "performance testing",
    r"машинн\w*\s+обучен\w*|машиналық\s+оқыту": "machine learning",
    r"облачн\w*|облак\w*|бұлт\w*": "cloud",
    r"статистик\w*": "statistics",
    r"документаци\w*|делов\w*\s+письм\w*": "documentation",
    r"визуализаци\w*": "visualization",
    r"доступност\w*\s+интерфейс\w*": "accessible interfaces",
    r"безопасн\w*\s+код\w*|қауіпсіз\s+код\w*|безопасн\w*\s+разработ\w*": "secure coding",
    r"информационн\w*\s+безопасност\w*|ақпараттық\s+қауіпсіздік": "information security",
    r"защит\w*\s+персональн\w*\s+данн\w*|дербес\s+деректер\w*\s+қорға\w*": "personal data protection",
    r"аналитик\w*|аналитика": "analytics",
    r"производительност\w*\s+веб\w*|веб\w*\s+производительност\w*": "web performance",
    r"продаж\w*|сату\w*": "selling",
    r"трудов\w*\s+прав\w*|еңбек\s+құқы\w*": "labor law",
    r"интервью|собеседован\w*|сұхбат\w*": "interviewing",
    r"дорожн\w*\s+карт\w*|жол\s+карт\w*": "roadmapping",
    r"решени\w*\s+проблем\w*|мәселелерді\s+шешу": "problem solving",
    r"коммуникаци\w*|қарым\s+қатынас": "communication",
    r"командн\w*\s+работ\w*|топтық\s+жұмыс": "teamwork",
    r"критическ\w*\s+мышлен\w*|сыни\s+ойлау": "critical thinking",
}


def reply_locale(message: str, fallback: str) -> str:
    if re.search(r"[әғқңөұүһі]|\b(?:тауып|курсын|бер|деген|туралы|мен|бар|жоқ)\b", message, re.I):
        return "kk"
    if re.search(r"[а-яё]", message, re.I):
        return "ru"
    if re.search(
        r"\b(what|why|how|did|have|can|find|show|which|is|explain|complete|search)\b", message, re.I
    ):
        return "en"
    return fallback if fallback in ("ru", "en", "kk") else "ru"


def normalize(text: str) -> str:
    text = re.sub(r"[^\w\s]", " ", text.casefold().replace("ё", "е"))
    for pattern, replacement in ALIASES.items():
        text = re.sub(pattern, replacement, text)
    return " ".join(text.split())


def matches(catalog: list[dict], message: str, history: list[dict]) -> list[dict]:
    query = normalize(message)
    words = set(query.split())
    scored = []
    for c in catalog:
        title = normalize(c["title"])
        title_words = set(title.split()) - {"in", "and", "for", "the", "of"}
        common = words & title_words
        # Typo tolerance only for meaningful words, never numeric IDs.
        fuzzy = sum(
            1
            for t in title_words - common
            if len(t) >= 4
            and any(len(w) >= 4 and SequenceMatcher(None, t, w).ratio() >= 0.84 for w in words)
        )
        score = len(common) * 20 + fuzzy * 12
        skill_words = set(normalize(" ".join(c.get("search_terms", []))).split())
        score += len((words & skill_words) - title_words) * 10
        if title in query or normalize(c["event_id"]) in query:
            score += 200
        if score:
            scored.append((score, c))
    scored.sort(key=lambda x: (-x[0], x[1]["event_id"]))
    if scored:
        best = scored[0][0]
        return [c for score, c in scored if score == best][:3]

    # Follow-ups refer to the most recent assistant choices, not any older profile data.
    last = next((h["content"] for h in reversed(history) if h["role"] == "assistant"), "")
    # A blocker explanation can mention another title before the numbered choices.
    last = "\n".join(re.findall(r"(?m)^\s*\d+\.\s+(.+)$", last)) or last
    referenced = sorted(
        (c for c in catalog if c["title"].casefold() in last.casefold()),
        key=lambda c: last.casefold().index(c["title"].casefold()),
    )
    ordinal = re.search(r"\b(перв\w*|втор\w*|трет\w*|first|second|third|1|2|3)\b", query)
    if ordinal and referenced:
        word = ordinal[0]
        index = (
            0
            if word.startswith(("перв", "first", "1"))
            else 1
            if word.startswith(("втор", "second", "2"))
            else 2
        )
        return referenced[index : index + 1]
    if re.search(r"\b(его|ее|этот|этого|него|него|это|да|yes|that|this|it)\b", query):
        return referenced[:3]
    return []


def hypothetical(message: str) -> bool:
    return bool(
        re.search(
            r"если|прой[дт]|прогноз|что измен|закончу|завершу|после|what if|complet|finish|project|аяқта|өтсем|^(да|yes|перв\w*|втор\w*|трет\w*|first|second|third|[123])[?.! ]*$",
            message,
            re.I,
        )
    )


def wants_choices(message: str) -> bool:
    return bool(
        re.search(
            r"что.*(?:пройти|посовету|порекоменду|выбрать|доступно)|како[йеую].*(?:курс|активност|шаг)|какие.*(?:курс|активност)|посоветуй|порекомендуй|найди|найти|поищи|покажи.*курс|курсы?\s+по\b|recommend|find|search|show.*course|what.*(?:courses|available|should)|which.*(?:course|step)|тауып|ізде|ұсын|қандай.*(?:курс|оқу)|курс.*(?:тап|бар)|не.*оқу",
            message,
            re.I,
        )
    )


def wants_status(message: str) -> bool:
    if re.search(r"если|what if|егер", message, re.I):
        return False
    return bool(
        re.search(
            r"\b(?:did|have|had)\s+i\b|\b(?:completed|finished|taken)\s+(?:by me|already)\b|\bis\b.*\b(?:complete|completed|finished)\b|проходил|прош[её]л|прошла|заверш[её]н|закончил|завершил|статус.*(?:курс|активност)|аяқтадым",
            message,
            re.I,
        )
    )


def status_text(candidate: dict, records: list[dict], locale: str) -> str:
    own = [r for r in records if r["event_id"] == candidate["event_id"]]
    completed = [r for r in own if r["status"] == "completed"]
    title = candidate["title"]
    if completed:
        date = max(r["date"] for r in completed)
        return {
            "ru": f"Да, в вашей истории есть завершение «{title}». Дата записи: {date}. Это данные истории, а не прогноз.",
            "en": f"Yes, your history records “{title}” as completed. Record date: {date}. This is your participation history, not a projection.",
            "kk": f"Иә, тарихыңызда «{title}» аяқталған деп жазылған. Жазба күні: {date}. Бұл болжам емес, қатысу тарихы.",
        }[locale]
    if own:
        latest = max(own, key=lambda r: (r["date"], r["record_id"]))
        labels = {
            "ru": {
                "in_progress": "в процессе",
                "no_show": "неявка",
                "dropped": "прервано",
                "declined": "отказ",
                "overdue": "просрочено",
            },
            "en": {
                "in_progress": "in progress",
                "no_show": "no-show",
                "dropped": "dropped",
                "declined": "declined",
                "overdue": "overdue",
            },
            "kk": {
                "in_progress": "орындалуда",
                "no_show": "қатыспады",
                "dropped": "тоқтатылған",
                "declined": "бас тартқан",
                "overdue": "мерзімі өткен",
            },
        }
        status = labels[locale].get(latest["status"], latest["status"])
        return {
            "ru": f"Завершение «{title}» в вашей истории не зафиксировано. Последний статус: {status}; дата записи: {latest['date']}.",
            "en": f"Your history has no completion recorded for “{title}”. Latest status: {status}; record date: {latest['date']}.",
            "kk": f"«{title}» аяқталғаны тарихта тіркелмеген. Соңғы күйі: {status}; жазба күні: {latest['date']}.",
        }[locale]
    return {
        "ru": f"В вашей истории нет записей об участии в «{title}». Подтвердить завершение по данным платформы не могу.",
        "en": f"There are no participation records for “{title}” in your history. I cannot confirm completion from the platform's data.",
        "kk": f"Тарихыңызда «{title}» туралы қатысу жазбасы жоқ. Платформа деректері бойынша аяқталғанын растай алмаймын.",
    }[locale]


def unsupported(message: str) -> bool:
    return bool(
        re.search(
            r"зарплат|salary|weather|погод|ignore.*instruction|игнорируй.*инструк|назначь|запиши меня|отметь|отмени|^\s*(?:пожалуйста\s+)?заверши\b|^\s*(?:please\s+)?(?:assign|enroll|mark|cancel)\b",
            message,
            re.I,
        )
    )


REASONS = {
    "ru": {
        "MANDATORY": "это обязательная активность, она не входит в добровольный маршрут",
        "AUDIENCE_MISMATCH": "активность предназначена для другой роли или грейда",
        "PREREQUISITES_UNMET": "сначала нужны навыки допуска",
        "ALREADY_COMPLETED": "активность уже завершена",
        "NO_UPCOMING_SESSION": "в каталоге нет предстоящей сессии",
        "SNOOZED": "активность отложена кнопкой «Не сейчас»; её можно вернуть в настройках",
    },
    "en": {
        "MANDATORY": "this is a mandatory activity, outside the voluntary route",
        "AUDIENCE_MISMATCH": "this activity targets a different role or grade",
        "PREREQUISITES_UNMET": "prerequisite skills are missing",
        "ALREADY_COMPLETED": "already completed",
        "NO_UPCOMING_SESSION": "no upcoming session in the catalog",
        "SNOOZED": "snoozed; restore it in Settings",
    },
    "kk": {
        "MANDATORY": "бұл міндетті белсенділік",
        "AUDIENCE_MISMATCH": "басқа рөлге немесе грейдке арналған",
        "PREREQUISITES_UNMET": "алғышарт дағдылары қажет",
        "ALREADY_COMPLETED": "бұрын аяқталған",
        "NO_UPCOMING_SESSION": "алдағы сессия жоқ",
        "SNOOZED": "кейінге қалдырылған; баптауларда қайтарыңыз",
    },
}


def blocked_text(candidate: dict, locale: str, names: dict[str, str]) -> str:
    reasons = []
    for reason in candidate["reasons"]:
        text = REASONS[locale].get(reason["code"])
        if not text:
            continue
        unmet = reason.get("unmet", [])
        if unmet:
            text += ": " + ", ".join(
                f"{names.get(u['skill_id'], u['skill_id'])} {u['current']}/{u['required']}"
                for u in unmet
            )
        reasons.append(text)
    prefix = {
        "ru": "Сейчас нельзя смоделировать завершение",
        "en": "Completion cannot be projected yet for",
        "kk": "Қазір аяқталуын болжау мүмкін емес",
    }[locale]
    return f"{prefix} «{candidate['title']}»: " + "; ".join(reasons) + "."

"""Общий парсер day-плана и подстановка плейсхолдеров."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List


def parse_outreach_plan(plan_file: str | Path) -> List[Dict]:
    """Парсит markdown-план: шаблон берётся только из блока ``` ... ```."""
    content = Path(plan_file).read_text(encoding="utf-8")
    touches: List[Dict] = []

    heading_re = re.compile(
        r"^## (\d+) · ([^·]+) · ([^·]+) · `([^`]+)` · id=(\d+)\s*$",
        re.MULTILINE,
    )
    headings = list(heading_re.finditer(content))

    for i, match in enumerate(headings):
        num, channel, context, template, id_num = match.groups()
        start = match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(content)
        block = content[start:end]

        when_match = re.search(r"\*\*When:\*\*\s*(.+?)(?=\n\n|\*\*|```)", block, re.DOTALL)
        when_rule = when_match.group(1).strip() if when_match else ""

        code_match = re.search(r"```(?:\w+)?\n(.*?)```", block, re.DOTALL)
        template_text = code_match.group(1).strip() if code_match else ""

        lang = "RU" if "ru" in template else "EN"
        medium = "dm" if template.startswith("dm") else "comment"
        channel_clean = channel.strip()
        touches.append(
            {
                "id": id_num,
                "num": num,
                "channel": channel_clean,
                "context": context.strip(),
                "template": template,
                "template_text": template_text,
                "when_rule": when_rule,
                "language": lang,
                "url": (
                    f"https://gameforge.website/{lang.lower()}/locforge"
                    f"?utm_source={channel_clean.lower()}"
                    f"&utm_medium={medium}"
                    f"&utm_campaign=lf_{lang.lower()}"
                    f"&from=locforge"
                ),
            }
        )

    return touches


def fill_template(template: str, game_name: str) -> str:
    message = template.replace("{game}", game_name)
    message = message.replace("{игру / пост}", game_name)
    message = message.replace("{игру}", game_name)
    return message


def build_personalize_prompt(message: str, game_name: str, touch: Dict) -> str:
    lang = touch.get("language", "EN")
    lang_rule = (
        "строго английский (English only, no Russian words)"
        if lang == "EN"
        else "строго русский (только русский, без английских фраз кроме названий)"
    )
    return f"""Персонализируй это сообщение для холодного outreach в геймдеве.

Исходный шаблон:
{message}

О получателе: автор игры "{game_name}" в канале {touch['channel']}
Контекст: {touch['context']}
Язык шаблона: {lang}

Правила:
1. Язык ответа: {lang_rule}
2. Максимум 3 предложения
3. Структура: [комплимент/контекст] → [оффер free pilot] → [призыв к действию]
4. Тон: дружелюбный, но деловой (без восклицаний)
5. Без приветствий ("Hey", "Привет"), без подписей
6. Ссылка и упоминание CSV обязательны
7. Обязательно упомяни название игры "{game_name}" (если это не generic your game)
8. Ответь ТОЛЬКО текстом сообщения

Персонализированное сообщение:"""


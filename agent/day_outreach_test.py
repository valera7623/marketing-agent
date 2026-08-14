import asyncio
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from local_llm import Config, ask_ollama
from outreach_plan import build_personalize_prompt, fill_template, parse_outreach_plan
from paths import CONFIG_PATH, DEFAULT_PLAN, LOGS_DIR, ensure_dirs, resolve_plan

# Windows-консоль (cp1251) часто падает на emoji/UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class OutreachDayAutomationTest:
    def __init__(self, plan_file: str | Path | None = None, config_path: str | Path | None = None):
        ensure_dirs()
        self.plan_file = resolve_plan(plan_file or DEFAULT_PLAN)
        self.config = Config(str(config_path or CONFIG_PATH))
        self.touches = parse_outreach_plan(self.plan_file)
        self.sent_log = []
        self.sent_count = 0
        self.daily_limit = 10

    def generate_mock_posts(self, touch: Dict) -> List[Dict]:
        """Генерирует тестовые посты для каждой платформы."""
        channel = touch["channel"].lower()
        context = touch["context"]

        mock_posts = {
            "discord": [
                {
                    "author": f"game_dev_{random.randint(1, 999)}",
                    "content": (
                        'Just released my game on Steam! Looking for localization help. '
                        'My game is called "Adventure Quest".'
                    ),
                    "game_name": "Adventure Quest",
                    "url": f"https://discord.com/channels/12345/67890/{random.randint(1000, 9999)}",
                },
                {
                    "author": f"indie_studio_{random.randint(1, 999)}",
                    "content": "We need to localize our game for Steam. Currently only English, need RU/ES/DE.",
                    "game_name": "Pixel Wars",
                    "url": f"https://discord.com/channels/12345/67890/{random.randint(1000, 9999)}",
                },
            ],
            "reddit": [
                {
                    "author": f"u/indie_dev_{random.randint(1, 999)}",
                    "title": 'Need help with localization for my game "Space Explorer"',
                    "game_name": "Space Explorer",
                    "url": f"https://reddit.com/r/{context}/comments/{random.randint(1000, 9999)}",
                },
                {
                    "author": f"u/game_studio_{random.randint(1, 999)}",
                    "title": 'Looking for localization partner for "Dragon Tales"',
                    "game_name": "Dragon Tales",
                    "url": f"https://reddit.com/r/{context}/comments/{random.randint(1000, 9999)}",
                },
            ],
            "telegram": [
                {
                    "author": f"@indie_dev_{random.randint(1, 999)}",
                    "content": "Кто-нибудь занимался локализацией игр? Нужны советы.",
                    "game_name": "Моя игра",
                    "url": f"https://t.me/indiedev/{random.randint(1000, 9999)}",
                }
            ],
            "vk": [
                {
                    "author": f"id{random.randint(1000, 9999)}",
                    "content": "Разрабатываем игру, нужно перевести на русский/английский.",
                    "game_name": "Новая игра",
                    "url": f"https://vk.com/wall-{random.randint(1000, 9999)}_{random.randint(100, 999)}",
                }
            ],
        }

        for key, posts in mock_posts.items():
            if key in channel:
                return posts
        return [{"author": "test_user", "game_name": "Test Game", "content": "Test post"}]

    async def generate_message(self, touch: Dict, post: Dict) -> str:
        """Генерация персонализированного сообщения через локальную модель."""
        game_name = post.get("game_name", "вашу игру")
        message = fill_template(touch["template_text"], game_name)

        print(f"\n📝 Генерирую сообщение для {post['author']}...")
        print(f"   Шаблон: {message[:50]}...")

        prompt = build_personalize_prompt(message, game_name, touch)

        try:
            personalized = await ask_ollama(prompt, self.config.get("llm"))
            if not personalized:
                return message
            if "gameforge.website" not in personalized:
                personalized += f"\n\nПодробнее: {touch['url']}"
            return personalized
        except Exception as e:
            print(f"⚠️ Ошибка генерации через LLM: {e}")
            return message

    async def send_to_channel_mock(self, touch: Dict, message: str, post: Dict) -> bool:
        """Тестовая отправка сообщения (только логирование)."""
        print(f"\n{'=' * 60}")
        print(f"📤 ТЕСТОВАЯ ОТПРАВКА #{self.sent_count + 1}")
        print(f"{'=' * 60}")
        print(f"📌 Канал: {touch['channel']}")
        print(f"📌 Контекст: {touch['context']}")
        print(f"📌 Шаблон: {touch['template']}")
        print(f"📌 Автор: {post['author']}")
        print(f"📌 Игра: {post.get('game_name', 'N/A')}")
        print("\n📝 Сообщение:")
        print("-" * 60)
        print(message)
        print("-" * 60)
        print(f"\n🔗 URL: {touch['url']}")
        print(f"{'=' * 60}\n")
        return True

    async def run_day(self):
        """Запуск тестовой автоматизации на день."""
        print("\n" + "=" * 60)
        print("🧪 ТЕСТОВЫЙ ЗАПУСК OUTREACH")
        print(f"📅 Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📋 Всего касаний в плане: {len(self.touches)}")
        print(f"🎯 Лимит на день: {self.daily_limit}")
        print("⚠️ РЕЖИМ ЗАГЛУШКИ: сообщения НЕ отправляются реально")
        print("=" * 60 + "\n")

        if not self.touches:
            print("❌ Не удалось распарсить касания из плана. Проверьте формат markdown.")
            return

        results = []
        daily_touches = self.touches[: self.daily_limit]

        for idx, touch in enumerate(daily_touches, 1):
            print(
                f"\n--- Касание {idx}/{len(daily_touches)}: "
                f"ID={touch['id']} {touch['channel']} {touch['template']} ---"
            )

            posts = self.generate_mock_posts(touch)
            if not posts:
                print(f"⚠️ Не найдено тестовых постов для {touch['context']}")
                results.append(
                    {
                        "id": touch["id"],
                        "status": "no_posts_found",
                        "reason": "Нет тестовых постов",
                    }
                )
                continue

            post = posts[0]
            print(f"✅ Найден тестовый пост от {post['author']}: {post.get('game_name', 'N/A')}")

            message = await self.generate_message(touch, post)
            success = await self.send_to_channel_mock(touch, message, post)

            if success:
                self.sent_count += 1
                results.append(
                    {
                        "id": touch["id"],
                        "status": "sent",
                        "post": post,
                        "message": message,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                print(f"✅ Тестовая отправка #{self.sent_count} завершена")
            else:
                results.append(
                    {
                        "id": touch["id"],
                        "status": "failed",
                        "reason": "Ошибка в тестовой отправке",
                    }
                )

            if idx < len(daily_touches):
                delay = 2
                print(f"⏳ Ожидание {delay} секунд...")
                await asyncio.sleep(delay)

        self.save_test_results(results)

        print("\n" + "=" * 60)
        print("📊 ИТОГИ ТЕСТОВОГО ЗАПУСКА:")
        print(
            f"✅ Успешно сгенерировано и отправлено (в тесте): "
            f"{self.sent_count}/{len(daily_touches)}"
        )
        print(
            f"⚠️ Не найдено постов: "
            f"{len([r for r in results if r['status'] == 'no_posts_found'])}"
        )
        print(f"❌ Ошибок: {len([r for r in results if r['status'] == 'failed'])}")
        print("=" * 60)

        print("\n📝 ПРИМЕРЫ СООБЩЕНИЙ:")
        for i, result in enumerate(results[:3], 1):
            if result["status"] == "sent":
                print(f"\n{i}. ID={result['id']} ({result.get('post', {}).get('author', 'N/A')}):")
                print(f"   {result['message'][:150]}...")

    def save_test_results(self, results: List[Dict]):
        """Сохранение тестовых результатов."""
        log_file = LOGS_DIR / f"test_outreach_log_{datetime.now().strftime('%Y-%m-%d')}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "date": datetime.now().isoformat(),
                    "mode": "test",
                    "results": results,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"\n📁 Тестовый лог сохранен в: {log_file}")

        report_file = LOGS_DIR / f"test_report_{datetime.now().strftime('%Y-%m-%d')}.txt"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("ТЕСТОВЫЙ ОТЧЕТ OUTREACH\n")
            f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")

            for result in results:
                if result["status"] == "sent":
                    f.write(f"ID: {result['id']}\n")
                    f.write(f"Автор: {result.get('post', {}).get('author', 'N/A')}\n")
                    f.write(f"Игра: {result.get('post', {}).get('game_name', 'N/A')}\n")
                    f.write(f"Сообщение:\n{result['message']}\n")
                    f.write("-" * 60 + "\n\n")

        print(f"📄 Текстовый отчет сохранен в: {report_file}")


async def main():
    ensure_dirs()
    plan_file = DEFAULT_PLAN
    if not plan_file.exists():
        print(f"❌ Ошибка: файл {plan_file} не найден!")
        print("Убедитесь, что план лежит в папке plans/.")
        return

    config = Config(str(CONFIG_PATH))
    if not config.get("llm"):
        config.set(
            "llm",
            {
                "provider": "ollama",
                "model": "qwen2.5:7b-instruct-q4_K_M",
                "api_base": "http://127.0.0.1:11434",
            },
        )

    print("🚀 Запуск тестового скрипта...")
    print("⚠️ Убедитесь, что Ollama запущена (модель qwen2.5:7b-instruct-q4_K_M)!")

    automation = OutreachDayAutomationTest(plan_file)
    await automation.run_day()


if __name__ == "__main__":
    asyncio.run(main())

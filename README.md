# marketing-agent

LocForge outreach agent (локальная Ollama + Discord REST; Reddit/VK/TG — browser scout / ручная отправка).

## Структура

```
marketing-agent/
├── run_outreach.py      # основной запуск
├── run_test.py          # тест с mock-постами
├── check_channels.py    # проверка доступа к channel id
├── scout.py             # URL канала → сигналы → черновики
├── requirements.txt
├── agent/               # Python-код
├── plans/               # day-планы (markdown)
├── data/                # config.json, CSV, contacted_users.json
├── docs/                # MANUAL_DISCORD / MANUAL_REDDIT / MANUAL_VK / MANUAL_TG
└── logs/                # логи и отчёты
```

## Быстрый старт

```powershell
venv\Scripts\activate
pip install -r requirements.txt

# тест генерации (без реальной отправки в чужие каналы)
python run_test.py

# проверка Discord channel id
python check_channels.py --write-plan

# пилот (доступные каналы)
python run_outreach.py --plan day-discord-accessible.md --limit 2

# скаут по URL канала (скиньте ссылку из Discord)
python scout.py "https://discord.com/channels/GUILD_ID/CHANNEL_ID"
```

## Workflow: вы кидаете URL

1. Откройте канал в Discord → скопируйте URL из адресной строки  
   (`https://discord.com/channels/.../...`)
2. Пришлите URL в чат **или** запустите:

```powershell
python scout.py "URL"
```

3. Скрипт найдёт посты с сигналами (localization / Steam / CSV / showcase),  
   сгенерирует черновики DM/Reply → файлы в `logs/scout_*.md`
4. Вы копируете draft и отправляете вручную (см. `docs/MANUAL_DISCORD.md`)

## Workflow: Discord

1. Скаут целевых каналов (Indie Park / Godot / Unity) через браузер или `scout.py`.
2. Отчёт: `logs/scout_discord_*.md` · планы: `plans/day-*.md`
3. Публичный **Reply** (предпочтительно) или DM после intent.
4. Отметьте `sent` в `data/outreach-leads.csv`.

## Конфиг

Скопируйте пример и заполните токены локально (файл `data/config.json` **не** коммитится):

```powershell
copy data\config.example.json data\config.json
```

Day 2 (2026-08-12): `plans/day-02-2026-08-12.md` · `logs/scout_discord_20260812.md`  
Day 3 (2026-08-13): `plans/day-03-2026-08-13.md` · Reddit ready · Discord/VK/TG hold login  
Day 4 (2026-08-14): `plans/day-04-2026-08-14.md` · Reddit/VK/TG/Discord done  
Day 5 (2026-08-15): `plans/day-05-2026-08-15.md` · done  
Day 6 (2026-08-16): `plans/day-06-2026-08-16.md` · done (317 blocked · rest sent)  
Day 7 (2026-08-17): `plans/day-07-2026-08-17.md` · CIS mix done (801–804 · 506–508 · 606 sent · 607 + Reddit skipped)  
Day 8 (2026-08-18): `plans/day-08-2026-08-18.md` · done (608–609 TG skipped · chatter)  
Day 9 (2026-08-20): `plans/day-09-2026-08-20.md` · done (809–812 · 512–514 · 610–611 · 423 sent)

## Workflow: Reddit

1. Скаут целевых сабов из плана (`r/gamedev`, `r/godot`, `r/Unity3D`, `r/IndieGaming`)  
   через браузер (Reddit JSON API часто 403 без ключей).
2. Отчёт с лидами и черновиками: `logs/scout_reddit_*.md`
3. Отправьте **публичный comment** (DM — только при явном запросе help/loc/CSV).
4. Отметьте `sent` в `data/outreach-leads.csv` (id=1..4).

Чеклист: `docs/MANUAL_REDDIT.md` · шаблоны: `plans/day-01-2026-08-10.md`

## Workflow: VK

1. Скаут пабликов (`play_with_ducat`, `gamedev56`, …) через браузер (`vk_token` пуст).
2. Отчёт: `logs/scout_vk_*.md`
3. Один публичный **comment** (DM — только после ответа).
4. Отметьте `sent` в `data/outreach-leads.csv` (id=15).

Чеклист: `docs/MANUAL_VK.md`

## Workflow: Telegram

1. Скаут чатов (`gamedev_chat_rus`, `unity3d_ru`, `godot_engine`) через Telegram Web (`telegram_token` пуст).
2. Отчёт: `logs/scout_tg_*.md`
3. Один **reply** в треде (DM — только после ответа).
4. Отметьте `sent` в `data/outreach-leads.csv` (id=16).

Чеклист: `docs/MANUAL_TG.md`

## Документация

- Discord: `docs/MANUAL_DISCORD.md` / `docs/Manual_Discord.pdf`
- Reddit: `docs/MANUAL_REDDIT.md`
- VK: `docs/MANUAL_VK.md`
- Telegram: `docs/MANUAL_TG.md`
- Конфиг: `data/config.json`

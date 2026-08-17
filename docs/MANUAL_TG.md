# Ручные касания в Telegram — чеклист LocForge

Когда `telegram_token` в `data/config.json` пуст — скаут и отправка **вручную** через Telegram Web / приложение.

Связанные файлы:
- план дня: `plans/day-01-2026-08-10.md` (касание id=16)
- отчёты: `logs/scout_tg_*.md`
- учёт: `data/outreach-leads.csv`

---

## Workflow

1. Скаутить чаты:
   - https://t.me/gamedev_chat_rus — Unity / инди (основной)
   - https://t.me/unity3d_ru — Q&A
   - https://t.me/godot_engine — Godot RU
2. Сигналы: Steam-страница / релиз / демо / локализация / перевод / CSV / EN-only.
3. Черновики → `logs/scout_tg_*.md`
4. Один **reply** в треде (предпочтительно) или DM → CSV.

Не питчить в каналах бюро/русификаторов (`GameLoc_RU`, `iti_gameloc`).

---

## 1. Найти живой пост

Публичный intent:
- «вышла в Steam / демо / страница»
- вопрос про перевод / локализацию / CSV
- WIP с запросом фидбека

Не отвечать на дайджест-ботов и оффтоп.

---

## 2. Reply в группе (предпочтительно)

1. Откройте сообщение автора.
2. **Reply** → вставьте draft (имя игры подставить).
3. UTM: `utm_source=tg&utm_medium=comment&utm_campaign=lf_ru`
4. **1 касание / день** по day-плану.

**Автоматизация:** не используйте `keyboard.type()` с переносами — в мессенджерах Enter часто = отправка (дубликаты, как в VK). Только paste / `insertText` + один Send.

---

## 3. DM (осторожно)

1. Только после ответа на reply или явного «напишите в ЛС».
2. Холодные ЛС в Telegram часто режутся / выглядят как спам.
3. UTM: `utm_medium=dm`.

Шаблон `dm_ru` (из плана):

```
Привет! Увидел {игру / пост}. LocForge — локализация инди CSV за один вечер: глоссарий, QA длины UI, экспорт Unity/Godot.

Могу сделать бесплатный пилот (RU/ES/DE). Если ок — укажем игру в кейсе на лендинге.

https://gameforge.website/ru/locforge?utm_source=tg&utm_medium=dm&utm_campaign=lf_ru&from=locforge
Или просто пришлите CSV в ответ.
```

---

## 4. Антиспам

- CIS-режим: до **2 TG-касаний / день** (разные чаты или reply + 1 value-post; не два value-post подряд в один чат). Иначе по умолчанию **1 / день**.
- Cooldown **7 дней** на автора.
- Не копируйте один текст в несколько чатов подряд.
- Соблюдайте pinned-правила чата (вакансии/реклама могут быть запрещены — тогда только value-reply по делу).

---

## 5. Учёт в CSV

Для id=16:
- `status=sent`, `sent_at`, `author`, `game_name`
- `notes` — ссылка на сообщение / «reply in @gamedev_chat_rus»

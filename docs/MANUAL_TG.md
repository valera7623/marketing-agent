# Ручные касания в Telegram — чеклист LocForge

Когда `telegram_token` в `data/config.json` пуст — скаут и отправка **вручную** через Telegram Web / приложение.

**Тон и шаблоны:** `docs/MESSAGING.md` (обязательно перед Day12+)

Связанные файлы:
- план дня: `plans/day-*.md`
- отчёты: `logs/scout_tg_*.md`
- учёт: `data/outreach-leads.csv`

---

## Workflow

1. Скаутить чаты:
   - https://t.me/gamedev_chat_rus — Unity / инди (**reply-only**, value-post на паузе)
   - https://t.me/unity3d_ru — Q&A
   - https://t.me/godot_engine — Godot RU (reply предпочтительно)
2. Сигналы: вопрос про перевод / локализацию / CSV / UI overflow / Next Fest / «строки не влезают».
3. Черновики → `logs/scout_tg_*.md`
4. **Reply в треде** → CSV. DM — только после ответа.

Не питчить в каналах бюро/русификаторов (`GameLoc_RU`, `iti_gameloc`).

---

## 1. Найти живой пост

Публичный intent:
- вопрос про перевод / локализацию / CSV / plurals
- «вышла в Steam / демо» **+** можно ответить по делу (не реклама в пустоту)
- жалоба на длину строк / HUD / achievements

Не отвечать на дайджест-ботов и оффтоп.  
**Skip**, если в чате болтовня и нет loc-треда (как Day8/Day11).

---

## 2. Reply в группе (единственный режим для gamedev_chat_rus)

1. Откройте **чужое** сообщение (вопрос / пост разработчика).
2. **Reply** → черновик из `MESSAGING.md` (без ссылки в первом сообщении).
3. Ссылку и «пилот» — только если спросили.
4. UTM при ссылке: `utm_source=tg&utm_medium=comment&utm_campaign=lf_ru`
5. **1 касание / день** по day-плану.

**Шаблон reply (шаг 1, без ссылки):**

```
С Unity Localization / I2 таблица обычно уже есть — грабли чаще в другом: {боль под тред: length QA / achievements ≠ HUD / термины в двух CSV}.

Могу накидать чеклист или глянуть sample, если скинете пару строк.
```

**Шаблон reply (шаг 2, если спросили):**

```
LocForge — QA глоссария и длины UI поверх вашего CSV, не вместо пакета. Бесплатно на sample: https://gameforge.website/ru/locforge?utm_source=tg&utm_medium=comment&utm_campaign=lf_ru&from=locforge
```

**Автоматизация:** не используйте `keyboard.type()` с переносами — Enter = отправка. Только paste / `insertText` + один Send.

---

## 3. Value-post (ограничено)

- **`@gamedev_chat_rus` — пауза** (реакция «спам» на повторяющиеся посты про CSV).
- Другие чаты: не чаще 1 value-post / 14 дней / чат; только новый угол из `MESSAGING.md`.
- Не дублировать формулировку «CSV → глоссарий + length QA + экспорт».

---

## 4. DM (осторожно)

1. Только после ответа на reply или явного «напишите в ЛС».
2. UTM: `utm_medium=dm`.

```
Привет! По {игре}: LocForge — QA глоссария и длины UI по CSV (поверх Unity/Godot Localization), без бюро.

Могу бесплатный пилот на sample. Если ок — укажем в кейсе.

https://gameforge.website/ru/locforge?utm_source=tg&utm_medium=dm&utm_campaign=lf_ru&from=locforge
```

---

## 5. Антиспам

- **1 TG-касание / день** (reply предпочтительно).
- Cooldown **7 дней** на автора / угол в одном чате.
- Не копировать один текст в несколько чатов.
- Соблюдать pinned-правила (реклама может быть запрещена).

---

## 6. Учёт в CSV

- `status=sent` / `skipped` (болтовня / нет треда)
- `notes` — «reply in @gamedev_chat_rus» / «skip chatter»

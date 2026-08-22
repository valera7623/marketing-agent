# Ручные касания в Reddit — чеклист LocForge

Когда Reddit API не настроен (`data/config.json` → `reddit.client_id` пуст) — скаут и отправка **вручную** через браузер.

Связанные файлы:
- план дня: `plans/day-01-2026-08-10.md` (касания id=1..4)
- отчёты скаута: `logs/scout_reddit_*.md`
- учёт: `data/outreach-leads.csv`
- конфиг: `data/config.json`

---

## Workflow: скинуть URL / попросить скаут

1. Агент скаутит сабреддиты из плана:
   - `r/gamedev` (Feedback Friday / Steam page)
   - `r/godot` (localization / CSV)
   - `r/Unity3D` (showcase / Steam page)
   - `r/IndieGaming` (launch / wishlist)
2. Сигналы: localization, CSV, Steam, EN-only, showcase, release, launch.
3. Черновики → `logs/scout_reddit_*.md`
4. Отправьте comment (предпочтительно) или DM → отметьте в CSV.

Локально можно кинуть готовый URL поста:

```text
https://www.reddit.com/r/SUB/comments/ID/slug/
```

---

## 1. Найти живой пост

Ищите **публичный intent**:
- вопрос про localization / translation / CSV / i18n
- «feedback on my Steam page»
- launch / wishlist / demo feedback

Не пишите вхолодную под случайный арт без Steam/loc сигнала.

---

## 2. Comment (предпочтительно)

1. Откройте пост своим аккаунтом.
2. **Add a comment** → вставьте draft из плана / scout report.
3. Замените `{game}` на реальное название.
4. Один comment на автора в день; не дублируйте в нескольких сабах сразу.

**Тон:** `docs/MESSAGING.md`

Шаблон `comment_en` (одна боль, не каталог фич):

```
Unity/Godot Localization usually covers the table — the painful bit is often {glossary drift / UI overflow / achievement strings ≠ in-game}. LocForge does QA on that layer without a bureau. Happy to pilot on a sample CSV if useful — DM or link in profile.
```

---

## 3. DM (осторожно)

1. Только если OP явно просит help / loc / CSV, или после тёплого обмена в треде.
2. Reddit часто режет cold DM новым аккаунтам — при отказе оставайтесь на comment.
3. UTM: `utm_medium=dm`.

---

## 4. Антиспам

- Максимум **4 Reddit-касания / день** (как в day-плане).
- Не копируйте один и тот же текст во все треды без правок.
- Не комментируйте Feedback Friday mega-thread рекламой пачкой — берите **конкретный OP-коммент / отдельный пост**.
- Cooldown **7 дней** на одного автора (`contacted_users` / CSV notes).
- **Не гоняйте пачку комментариев через автоматизацию браузера подряд** — Reddit может заблокировать аккаунт («подозрительная активность» → сброс пароля). Между касаниями делайте паузу вручную (минуты, не секунды).

---

## 5. Учёт в CSV

В `data/outreach-leads.csv`:

| Поле | Значение |
|------|----------|
| `status` | `sent` |
| `sent_at` | дата, например `2026-08-11` |
| `author` | Reddit username |
| `game_name` | название игры |
| `notes` | URL поста |

В markdown-плане поставьте `- [x] Sent`.

---

## 6. Если ответили

| Поле | Значение |
|------|----------|
| `reply` | `yes` / `no` / `maybe` |
| `reply_at` | дата |

Пилот: CSV `key,source` на `gameforge.website@yandex.ru` (subject: `LocForge pilot`).

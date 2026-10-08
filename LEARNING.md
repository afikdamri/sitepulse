# יומן למידה — SitePulse

היומן מתעד כל שלב בפרויקט: מה בנינו, המושגים החשובים, למה בחרנו כך, ומה למדנו על עבודה עם Claude Code.
המונחים הטכניים כתובים באנגלית (כך תשמע אותם בראיונות ובתיעוד), ההסברים בעברית.

---

## שלב 0 — Setup & Claude Code Foundations

### מה בנינו
- Git repository חדש (`git init -b main`).
- `pyproject.toml` — קובץ ההגדרות המרכזי של הפרויקט: שם, גרסה, dependencies, ופקודת ה-CLI.
- מבנה **src layout**: הקוד תחת `src/sitepulse/`, הבדיקות תחת `tests/`.
- הגדרות לכלי איכות: ruff, mypy, pytest, pre-commit.
- `CLAUDE.md` — קובץ ההוראות ל-Claude Code.
- פקודת CLI ראשונה: `sitepulse version` + בדיקה ראשונה (smoke test).

### מושגים חשובים
| מונח | הסבר |
|---|---|
| **Virtual Environment (venv)** | תיקייה מבודדת (`.venv`) עם Python וספריות רק לפרויקט הזה. מונע התנגשות גרסאות בין פרויקטים. |
| **Dependency** | ספרייה חיצונית שהקוד שלנו צריך כדי לרוץ (למשל `httpx`). |
| **Dev Dependency** | ספרייה שצריך רק בזמן פיתוח (pytest, ruff) — המשתמש הסופי לא מתקין אותה. מוגדר ב-`[dependency-groups]`. |
| **Package Manager — uv** | כלי שמתקין ספריות, מנהל venv ונועל גרסאות. מחליף pip + venv + pip-tools, ומהיר פי 10–100. |
| **Lock file (`uv.lock`)** | מקבע את הגרסה *המדויקת* של כל ספרייה, כדי שכולם (וגם ה-CI) יריצו בדיוק אותו דבר. נכנס ל-git. |
| **src layout** | הקוד בתוך `src/`. מכריח להתקין את החבילה כדי לבדוק אותה — כך הבדיקות רצות מול מה שהמשתמש באמת יקבל, ולא "במקרה" מול קבצים בתיקייה. |
| **Entry Point / Console Script** | השורה `sitepulse = "sitepulse.cli:app"` ב-`[project.scripts]` יוצרת פקודה בשם `sitepulse` בטרמינל שמריצה את `app` מתוך `cli.py`. |
| **`__main__.py`** | מאפשר להריץ `python -m sitepulse`. |
| **Build Backend (hatchling)** | הכלי שהופך את הקוד לחבילה שניתן להתקין (wheel). |
| **Linter (ruff)** | סורק קוד ומוצא בעיות סגנון ובאגים נפוצים. גם formatter (מסדר עיצוב אוטומטית). |
| **Type Checker (mypy)** | בודק שה-Type Hints עקביים *לפני* הרצה. `strict = true` = הרמה המחמירה ביותר. |
| **pre-commit** | מריץ בדיקות אוטומטית לפני כל `git commit`, כך שקוד לא מסודר לא נכנס ל-repo. |
| **Smoke Test** | בדיקה מינימלית שמוודאת ש"הדבר בכלל עולה". |
| **Line Endings (CRLF vs LF)** | Windows מסיים שורה ב-`\r\n` (CRLF), Linux/Mac ב-`\n` (LF). קובץ `.gitattributes` עם `eol=lf` מבטיח שב-repo תמיד יהיה LF — אחרת ה-CI (שרץ על Linux) יראה "שינויים" בכל שורה. |

### החלטות ארכיטקטורה ולמה
- **Python** — כבר מותקן, ויש לו אקוסיסטם מצוין ל-scraping (httpx, BeautifulSoup) ול-UI בטרמינל (Rich).
- **Pipeline Architecture** — הנתונים זורמים בכיוון אחד: Crawl → Analyze → Score → Report. כל שלב עצמאי וניתן לבדיקה בנפרד.
- **Plugin pattern לאנלייזרים** — כל אנלייזר הוא מחלקה שמממשת ממשק משותף. להוסיף בדיקה חדשה = להוסיף קובץ, בלי לשנות קוד קיים (**Open/Closed Principle**).
- **בלי Claude API בתוך הכלי** — הכלי דטרמיניסטי: אותו אתר → אותו דוח. ה-AI הוא כלי *הפיתוח* שלנו.

### טיפ Claude Code מהשלב
- **CLAUDE.md** הוא ה"זיכרון" של הפרויקט: Claude Code קורא אותו אוטומטית בתחילת כל session. שמים בו את מה שצריך לדעת *ושאי אפשר להבין מהקוד*: פקודות הרצה, כללי ארכיטקטורה, קונבנציות. קצר וממוקד עדיף על ארוך.
- **Plan Mode** — התחלנו את הפרויקט במצב תכנון: Claude חקר, שאל שאלות, כתב תוכנית, ורק אחרי אישור התחיל לכתוב קוד. למשימות גדולות זה חוסך הרבה תיקונים.
- אפשר לייצר CLAUDE.md אוטומטית עם `/init`, ואז לערוך ידנית.

### שאלות ראיון אפשריות
1. מה ההבדל בין dependency ל-dev dependency?
2. למה צריך lock file אם כבר כתבנו גרסאות ב-`pyproject.toml`? (תשובה: `>=0.27` הוא טווח; ה-lock מקבע גרסה מדויקת לשחזוריות — **Reproducibility**.)
3. מה היתרון של src layout?
4. מה זה Open/Closed Principle ואיפה השתמשת בו?

---

## שלב 1 — Models + CLI Skeleton

### מה בנינו
- `models.py` — כל מבני הנתונים שזורמים ב-pipeline: `PageResult` (נתונים גולמיים על עמוד), `LinkResult` (תוצאת בדיקת קישור), `Issue` (בעיה + המלצת תיקון), `CategoryScore`, `AuditReport`.
- `config.py` — `AuditConfig`: כל האפשרויות של הסריקה + ספים (thresholds) ל-SEO ול-Performance, עם validation.
- `cli.py` — הפקודה `sitepulse scan <url>` עם האפשרויות `--max-pages`, `--depth`, `--concurrency`, `--timeout`, `--external/--no-external`, `--robots/--ignore-robots`, `--json`, `--fail-under`.
- 43 בדיקות, Coverage של 100%.

### מושגים חשובים
| מונח | הסבר |
|---|---|
| **Type Hints** | `def f(x: int) -> str` — מצהירים על סוגי הנתונים. Python לא אוכף אותם בזמן ריצה, אבל mypy בודק אותם מראש, וספריות כמו Pydantic ו-Typer *משתמשות* בהם כדי לעבוד. |
| **Pydantic `BaseModel`** | מחלקת נתונים שמבצעת **Validation** אוטומטי: `Field(ge=1, le=50)` = חייב להיות בין 1 ל-50. ערך לא תקין → `ValidationError`. |
| **Serialization** | המרת אובייקט לפורמט שניתן לשמור/לשלוח (JSON). `model_dump_json()` עושה את זה בחינם — כך נקבל את `--json` כמעט בלי קוד. |
| **`exclude=True`** | שדה `html` קיים באובייקט (האנלייזרים צריכים אותו), אבל לא נכנס לייצוא ה-JSON (הוא ענק). |
| **`computed_field`** | שדה שמחושב משדות אחרים (`grade` מתוך `score`, `is_broken` מתוך `status_code`). אין סיכוי שיהיו לא מסונכרנים, והוא כן מופיע ב-JSON. |
| **`frozen=True` (Immutability)** | אחרי יצירה אי אפשר לשנות את ה-config. מונע באגים שבהם קוד אחד משנה הגדרה "מתחת לרגליים" של קוד אחר — חשוב במיוחד בקוד async. |
| **`StrEnum`** | קבוצה סגורה של ערכים (`Severity.CRITICAL`). עדיף על מחרוזות חופשיות: אין טעויות כתיב, ו-mypy מזהה שגיאות. |
| **Normalization** | הפיכת קלטים שונים לצורה קנונית אחת: `Example.COM` ו-`https://example.com/` → אותו URL. קריטי בשלב 2, כדי לא לסרוק אותו עמוד פעמיים. |
| **Exit Code** | המספר שתוכנית מחזירה למערכת ההפעלה. 0 = הצלחה, כל דבר אחר = כישלון. כך CI (GitHub Actions) יודע אם להכשיל build. הגדרנו: `0` OK, `1` ציון נמוך מ-`--fail-under`, `2` קלט לא תקין, `3` הסריקה נכשלה. |
| **stdout vs stderr** | שני ערוצי פלט נפרדים. הדוח הולך ל-stdout, שגיאות ל-stderr — כך אפשר להפנות את הדוח לקובץ ועדיין לראות שגיאות במסך. |
| **Parametrized Tests** | `@pytest.mark.parametrize` — אותה בדיקה רצה על הרבה קלטים. בדיקה אחת, 8 מקרים. |
| **Boundary Testing** | בודקים בדיוק על הגבולות: 90 → A, 89.9 → B. רוב הבאגים מסתתרים ב"off-by-one". |
| **Coverage** | איזה אחוז מהקוד הבדיקות הריצו. 100% לא אומר שאין באגים — רק שאין שורה שלא נבדקה אף פעם. |

### החלטות ארכיטקטורה ולמה
- **ה-validation נמצא ב-`AuditConfig` ולא ב-CLI** — **Single Source of Truth**. אם מחר נוסיף API או GUI, אותם כללים יחולו אוטומטית. ה-CLI רק מתרגם שגיאות להודעות יפות.
- **`PageResult` מכיל רק עובדות, בלי שיפוט** — ה-crawler אוסף (status, זמנים, קישורים), והאנלייזרים מחליטים מה "רע". כך אפשר לשנות ספים בלי לגעת ב-crawler.
- **ספים (thresholds) ב-config ולא hardcoded** — "מהו עמוד איטי" זו החלטה עסקית, לא לוגיקה. מרכזים אותה במקום אחד.
- **`rule_id` יציב לכל Issue** (`seo.title.missing`) — מאפשר בעתיד להשתיק כלל ספציפי, ולכלים אחרים לקרוא את ה-JSON בצורה אמינה.

### הבאג שהבדיקות תפסו 🐛
הקוד הוסיף `https://` לכל קלט בלי `://`. אז `mailto:me@example.com` הפך ל-`https://mailto:me@example.com` — URL "תקין" ש-Python מפרש כמשתמש `mailto` בשרת `example.com`!
הפתרון: Regex שמזהה **scheme** (`mailto:`) לעומת **port** (`localhost:8000`) — אחרי הנקודתיים של port בא תמיד מספר.
**הלקח:** כתבנו את הבדיקה *לפני* שחשבנו על המקרה הזה בקוד, והיא מצאה אותו. זה הערך של בדיקות על קלטים "מוזרים" (**Edge Cases**).

### טיפ Claude Code מהשלב
- **לולאת משוב (Feedback Loop):** Claude Code כתב קוד → הריץ בדיקות → ראה כישלון → תיקן → הריץ שוב. הכלל ב-CLAUDE.md ("Run tests, ruff and mypy before declaring any task done") הוא מה שגורם לו לסגור את הלולאה בעצמו ולא להגיד "סיימתי" על קוד שבור.
- **בדיקות הן ה"עיניים" של ה-AI** — ככל שיש יותר בדיקות טובות, Claude Code יכול לעבוד בביטחון רב יותר ולגלות את הטעויות של עצמו.
- כשמבקשים פיצ'ר, כדאי לבקש במפורש גם בדיקות ל-edge cases.

### שאלות ראיון אפשריות
1. למה להשתמש ב-Pydantic ולא ב-`dataclass` רגיל? (Validation + Serialization מובנים.)
2. מה ההבדל בין exit code 0 ל-1, ולמה זה חשוב ב-CI?
3. למה לעשות את ה-config immutable?
4. ספר על באג שבדיקה תפסה לך. (יש לך עכשיו סיפור טוב — ה-`mailto:`.)
5. מה ההבדל בין stdout ל-stderr?

---

## שלב 2 — Async Crawler

### מה בנינו
- `url_utils.py` — Normalization של URLs, resolve של קישורים יחסיים, ובדיקת "אותו אתר".
- `parsing.py` — חילוץ קישורים (`<a href>`) ומשאבים (`<img>`, `<script>`, `<link rel=stylesheet>`) מ-HTML, כולל תמיכה ב-`<base href>`.
- `robots.py` — קריאת `robots.txt`: אילו נתיבים אסור לסרוק, ו-`Crawl-delay`.
- `crawler.py` — ה-Crawler: BFS אסינכרוני עם Worker Pool, מדידת TTFB וזמן כולל, טיפול בשגיאות, redirects ו-Rate Limiting.
- `auditor.py` — ה-Orchestrator: יוצר HTTP client, טוען robots, מריץ את ה-crawler ומחזיר `AuditReport`.
- CLI עם Progress Bar, טבלת עמודים, ו-`--json` שכבר עובד.
- 99 בדיקות, Coverage 97%, נבדק על אתר אמיתי (books.toscrape.com: 20 עמודים ב-4 שניות).

### מושגים חשובים
| מונח | הסבר |
|---|---|
| **Crawler / Spider** | תוכנה שמתחילה מ-URL, מורידה את הדף, מוצאת בו קישורים, ומורידה גם אותם — וכך הלאה. |
| **BFS (Breadth-First Search)** | סריקה "לפי שכבות": קודם כל העמודים במרחק 1 מהדף הראשי, אחר כך מרחק 2 וכו'. כשיש מגבלת `max_pages`, BFS מבטיח שנסרוק את העמודים *החשובים* (הקרובים לדף הבית) ולא נצלול לעומק של ענף אחד. ההפך: **DFS**. |
| **Visited Set** | `_seen` — רשימת URLs שכבר תוזמנו. בלעדיו, אתר שבו A מקשר ל-B ו-B ל-A ייצור **לולאה אינסופית**. |
| **async / await** | קוד שיכול "להשהות את עצמו" בזמן שהוא מחכה לרשת, ולתת לקוד אחר לרוץ בינתיים. `await` = "אני מחכה, תריצו מישהו אחר". |
| **Event Loop** | המנגנון שמריץ את כל ה-tasks האסינכרוניים ב-thread **אחד**, ומחליף ביניהם בכל `await`. `asyncio.run()` מפעיל אותו. |
| **Concurrency vs Parallelism** | **Concurrency** = הרבה משימות *בתהליך* באותו זמן (מחליפים ביניהן בזמן המתנה). **Parallelism** = הרבה משימות *רצות פיזית* באותו רגע (כמה ליבות CPU). Crawler מבלה 99% מהזמן בהמתנה לרשת (**I/O-bound**), ולכן Concurrency מספיק — thread אחד מחזיק עשרות בקשות פתוחות. |
| **Worker Pool** | מספר קבוע (`concurrency`) של workers ששולפים משימות מתור משותף. ככה מגבילים כמה בקשות רצות במקביל. |
| **`asyncio.Queue`** | תור בטוח לשימוש בין tasks. `queue.join()` מחכה עד שכל משימה סומנה `task_done()` — כך יודעים שהסריקה הסתיימה (גם כשעמודים חדשים מתווספים תוך כדי). |
| **Graceful Error Handling** | `try/except/finally` בכל worker: עמוד אחד שקורס לא מפיל את כל הסריקה, ו-`task_done()` ב-`finally` מבטיח שהתור לא "ייתקע". |
| **TTFB (Time To First Byte)** | הזמן מרגע שליחת הבקשה עד שהשרת התחיל לענות (headers). מודד כמה מהר **השרת** עובד. **Total time** כולל גם את הורדת התוכן. |
| **Streaming** | `client.stream()` — קוראים את ה-headers *לפני* שמורידים את הגוף. כך מודדים TTFB, ולא מורידים קבצי PDF/וידאו שלמים סתם. |
| **Connection Pooling / Keep-Alive** | שימוש חוזר בחיבור TCP+TLS שכבר פתוח. ראינו את זה בפועל: 10 הבקשות הראשונות (חיבורים חדשים) ~495ms TTFB, הבאות ~150ms. ה-handshake לבד עלה ~350ms! |
| **robots.txt** | קובץ שבעל אתר שם ב-`/robots.txt` ואומר לבוטים מה מותר לסרוק. לא מנגנון אבטחה — רק "נימוס", אבל crawler מקצועי מכבד אותו. |
| **Rate Limiting / Crawl-delay** | הגבלת קצב הבקשות כדי לא להעמיס על השרת. מימשנו `RateLimiter` עם `asyncio.Lock` — כל ה-workers חולקים "שעון" אחד. |
| **User-Agent** | כותרת HTTP שמזהה מי שולח את הבקשה (`SitePulse/0.1.0`). Crawler הגון מזדהה. |
| **Dependency Injection** | ה-`Crawler` *מקבל* `httpx.AsyncClient` מבחוץ במקום ליצור אותו. בבדיקות מזריקים client שכל הבקשות שלו מיורטות ע"י `respx`. |
| **Mocking (respx)** | החלפת הרשת האמיתית בתשובות מזויפות. הבדיקות רצות ב-5 שניות, בלי אינטרנט, ותמיד עם אותה תוצאה (**Deterministic**). |

### החלטות ארכיטקטורה ולמה
- **Worker Pool ולא `Semaphore`** — בתוכנית כתבנו Semaphore, אבל עם Worker Pool אנחנו מקבלים *גם* הגבלת מקביליות *וגם* סדר BFS טבעי מהתור, ואין צורך ליצור task לכל URL. (שינוי תוכנית מנומק זה דבר טוב — לא חייבים להיצמד לתכנון אם מצאנו דרך טובה יותר.)
- **Trailing slash נשמר** — `/about` ו-`/about/` *יכולים* להיות דפים שונים. אם הם אותו דף, השרת בדרך כלל עושה redirect, ואנחנו מזהים את זה דרך `_redirect_targets`.
- **`www.` ו-http/https נחשבים "אותו אתר"** — אחרת `example.com` שמפנה ל-`www.example.com` היה גורם לכל הקישורים להיראות חיצוניים.
- **לא מפרסרים דפי שגיאה (4xx/5xx) ודפים מאתרים אחרים** — לא רוצים לסרוק קישורים מדף 404 או "לברוח" לאתר אחר דרך redirect.
- **הגבלת גודל HTML ל-5MB ו-Crawl-delay ל-5 שניות** — הגנות מפני מקרי קצה שיכולים לתקוע את הכלי.
- **robots.txt שלא נטען → מותר הכל** — גוגל מחמיר יותר (5xx = אסור הכל), אבל כלי audit שבעל האתר מריץ על האתר שלו צריך להיות סלחני.

### באגים ותגליות מהשלב 🐛
1. **באג שמנענו בתכנון:** בגרסה הראשונה, URL שהגענו אליו דרך redirect נכנס ל-`_seen` — והיה "גוזל" מכסה מ-`max_pages` בלי שבאמת סרקנו עמוד. העברנו אותו ל-set נפרד.
2. **מגבלה של הספרייה הסטנדרטית:** `urllib.robotparser` מבין רק Crawl-delay שלם (`isdigit()`). `Crawl-delay: 0.5` פשוט מתעלם. בדיקה נכשלה וגילתה את זה — לא באג שלנו, אבל טוב לדעת.
3. **בעיית SEO אמיתית שמצאנו:** ב-books.toscrape.com, `/` ו-`/index.html` הם אותו דף בשתי כתובות — **Duplicate Content**. ננתח את זה בשלב 4.

### טיפ Claude Code מהשלב
- **בדיקות כמפרט (Tests as Specification):** כל התנהגות חשובה של ה-crawler מתועדת בשם של בדיקה: `test_redirects_are_followed_and_target_not_refetched`, `test_never_exceeds_concurrency_limit`. כשתבקש מ-Claude Code לשנות משהו בעתיד, הבדיקות האלה יגנו על ההתנהגות הקיימת (**Regression Tests**).
- **בדיקת מקביליות אמיתית:** `test_never_exceeds_concurrency_limit` סופר כמה בקשות "באוויר" בכל רגע. בדיקה כזו מוכיחה ש-limit עובד — לא רק שהקוד "נראה נכון".
- **אימות מול העולם האמיתי:** mocks לא מספיקים. הרצה אחת על אתר אמיתי לימדה אותנו על Connection Pooling ו-Duplicate Content. תמיד לבקש מ-Claude Code להריץ את הכלי בסוף ולא רק את הבדיקות.

### שאלות ראיון אפשריות
1. מה ההבדל בין Concurrency ל-Parallelism? למה async מתאים ל-crawler ולא ל-עיבוד תמונות?
2. למה BFS ולא DFS לסריקת אתר?
3. איך מונעים לולאה אינסופית ב-crawler?
4. איך יודעים שה-crawler סיים, כשעמודים חדשים מתגלים תוך כדי? (`queue.join()` + `task_done()`.)
5. מה זה TTFB ומה הוא מודד שזמן כולל לא מודד?
6. למה הבקשות הראשונות איטיות יותר? (TCP + TLS handshake, Connection Pooling.)
7. איך בודקים קוד שעושה בקשות רשת בלי רשת? (Dependency Injection + Mocking.)

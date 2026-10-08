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

---

## שלב 3 — Broken Links

### מה בנינו
- `link_checker.py` — אוסף כל הקישורים והמשאבים מכל העמודים, מסיר כפילויות, זוכר מאיזה עמוד הגיע כל קישור, ובודק כל אחד: עמודים שה-crawler כבר הוריד ממוחזרים בחינם, השאר נבדקים ב-`HEAD` עם fallback ל-`GET`.
- `analyzers/base.py` — ה-`Analyzer` Protocol ו-`AuditData`: החוזה שכל אנלייזר מממש.
- `analyzers/links.py` — `LinkAnalyzer`: הופך תוצאות בדיקה ל-Issues עם חומרה והמלצה. 9 כללים.
- `rate_limit.py` — ה-`RateLimiter` עבר למודול משלו, כי עכשיו גם ה-crawler וגם ה-link checker חולקים אותו.
- `AuditProgress` — ממשק שדרכו ה-auditor מדווח התקדמות, וה-CLI מציג שני progress bars.
- 127 בדיקות, Coverage 96%.

### הכללים שמימשנו
| `rule_id` | חומרה | מתי |
|---|---|---|
| `links.internal.broken` | 🔴 critical | קישור פנימי מחזיר 4xx/5xx |
| `links.resource.broken` | 🔴 critical | תמונה/סקריפט/CSS חסרים (שובר את הדף ויזואלית) |
| `links.unreachable` | 🔴/🟡 | timeout / DNS / connection refused (קריטי אם פנימי) |
| `links.external.broken` | 🟡 warning | קישור לאתר חיצוני מחזיר 4xx/5xx (לא בשליטתנו, אבל פוגע בחוויה) |
| `links.redirect.insecure` | 🟡 warning | HTTPS שמפנה ל-HTTP — **נמצא באתר אמיתי!** |
| `links.redirect.chain` | 🟡 warning | 2+ הפניות ברצף |
| `links.mixed_content` | 🟡 warning | דף HTTPS שטוען משאבים ב-HTTP |
| `links.internal.redirect` | 🔵 info | קישור פנימי שעובר הפניה אחת — עדיף לקשר ישר ליעד |
| `links.external.unverifiable` | 🔵 info | 401/403/429/999 מאתר חיצוני — כנראה חסימת בוטים, לא בהכרח שבור |

### מושגים חשובים
| מונח | הסבר |
|---|---|
| **Broken Link** | קישור שמוביל לשגיאה. פוגע בחוויית משתמש וב-SEO (גוגל רואה אתר "מוזנח"). |
| **HTTP Status Codes** | `2xx` הצלחה · `3xx` הפניה · `4xx` שגיאת לקוח (`404` לא נמצא, `403` אסור, `410` נמחק לצמיתות, `429` יותר מדי בקשות) · `5xx` שגיאת שרת (`500`, `502`, `503`). |
| **HEAD vs GET** | `HEAD` מבקש רק את ה-headers בלי התוכן — מהיר וזול. **אבל** הרבה שרתים מממשים אותו לא נכון (מחזירים 405, 403 ואפילו 404). לכן: HEAD קודם, ואם נכשל — GET לפני שמכריזים "שבור". דיוק > מהירות. |
| **301 vs 302** | `301` = הפניה **קבועה** (גוגל מעביר את ה"ציון" לכתובת החדשה). `302` = **זמנית** (הכתובת המקורית נשארת הקנונית). `307/308` = אותו דבר, אבל שומרים על ה-method. |
| **Redirect Chain** | A→B→C. כל hop = round-trip נוסף. גוגל מפסיק לעקוב אחרי ~10, ו"כוח" ה-SEO נשחק בכל hop. |
| **Mixed Content** | דף HTTPS שטוען קובץ ב-HTTP. דפדפנים חוסמים סקריפטים כאלה ומציגים אזהרת אבטחה. |
| **HTTPS Downgrade** | הפניה מ-HTTPS ל-HTTP. המשתמש יוצא מחיבור מוצפן בלי לשים לב — חשוף להאזנה (**MITM — Man in the Middle**). |
| **False Positive** | התראה על בעיה שלא קיימת. אתרים כמו LinkedIn מחזירים `999` לבוטים — אם נדווח "שבור", המשתמש יפסיק לסמוך על הכלי. לכן הם רק **info**. |
| **Protocol (Python typing)** | "ממשק" מבני — כל מחלקה שיש לה `category` ו-`analyze()` מתאימה, בלי לרשת ממחלקת בסיס (**Structural Typing / Duck Typing** עם בדיקת mypy). |
| **Pure Function** | פונקציה שהפלט שלה תלוי רק בקלט, בלי side effects (רשת, הדפסה, קבצים). האנלייזרים טהורים → קל מאוד לבדוק: בונים `LinkResult` ביד ובודקים את ה-Issue. |
| **Observer / Callback pattern** | ה-auditor לא יודע כלום על Rich או טרמינל. הוא רק קורא ל-`progress.page_done()`. ה-CLI מחליט מה להציג. אפשר מחר לחבר GUI בלי לגעת ב-auditor. |
| **Null Object pattern** | `NullProgress` — מימוש ש"לא עושה כלום". חוסך `if progress is not None` בכל מקום. |
| **`asyncio.gather` + `Semaphore`** | כאן כן השתמשנו ב-Semaphore: כל הקישורים ידועים מראש (אין תור שגדל), אז יוצרים task לכל אחד ו-Semaphore מגביל כמה רצים יחד. |

### החלטות ארכיטקטורה ולמה
- **הפרדה בין `link_checker` (רשת) ל-`LinkAnalyzer` (לוגיקה)** — בתוכנית המקורית האנלייזר היה עושה גם בקשות רשת. פיצלנו: איסוף נתונים בנפרד משיפוט. התוצאה: 15 בדיקות של האנלייזר שרצות במילישניות בלי mock אחד.
- **מיחזור עמודים שכבר נסרקו** — אם ה-crawler כבר הוריד את `/about`, אין סיבה לבקש אותו שוב. חוסך בקשות ועומס על השרת.
- **Issue אחד לכל URL שבור, עם רשימת המקורות** — אם תמונה שבורה מופיעה ב-header של 50 עמודים, זו *בעיה אחת* שמתקנים במקום אחד, לא 50.
- **`max_link_checks` (תקציב בקשות)** — אתר עם אלפי קישורים לא יגרום לכלי לרוץ שעה. מה שלא נבדק מדווח ב-notes — **שקיפות** במקום הסתרה.
- **Crawl-delay חל רק על האתר שלנו** — זו הוראה של בעל האתר הספציפי, לא רלוונטית לאתרים חיצוניים.

### באגים ותגליות מהשלב 🐛
1. **ספירה כפולה:** URL חסום ב-robots.txt נספר פעם ב-crawler ופעם ב-link checker → "2 URLs skipped" על URL אחד. הבדיקה תפסה את זה. התיקון: לשמור את ה-URLs עצמם ולספור **איחוד של sets** (`set_a | set_b`).
2. **בעיית אבטחה אמיתית ב-quotes.toscrape.com:** כל 20 הקישורים ל-`/author/...` מדף HTTPS מפנים ל-`http://`. הכלל `links.redirect.insecure` נולד מהתגלית הזו — **הרצה על אתר אמיתי חשפה סוג בעיה שלא חשבנו עליו**.

### טיפ Claude Code מהשלב
- **"הבדיקה שמכשילה היא חברה":** ב-2 מתוך 3 השלבים עד עכשיו, בדיקה שנכשלה חשפה באג אמיתי. אל תבקש מ-Claude Code "לתקן את הבדיקה" — בקש ממנו *להבין למה היא נכשלת*. לפעמים הבדיקה צודקת והקוד שגוי.
- **עדכון CLAUDE.md כשהארכיטקטורה משתנה:** שינינו את הכלל "אנלייזרים לא עושים רשת חוץ מ-LinkAnalyzer" ל"אנלייזרים תמיד טהורים". אם לא נעדכן, session עתידי של Claude Code יקרא כלל ישן ויכתוב קוד לא עקבי.
- **ניקוי קוד אחרי עצמך:** בכתיבה הראשונה של הבדיקות נכנסו `# type: ignore` ו-mutable default — ניקינו לפני ה-commit. גם קוד בדיקות הוא קוד.

### שאלות ראיון אפשריות
1. מה ההבדל בין HEAD ל-GET, ולמה לא להסתמך רק על HEAD?
2. מה ההבדל בין 301 ל-302 מבחינת SEO?
3. מה זה Mixed Content ולמה דפדפנים חוסמים אותו?
4. איך מתמודדים עם False Positives בכלי בדיקה? (סיווג חומרה, info במקום error.)
5. מה ההבדל בין Protocol ל-ABC (Abstract Base Class) ב-Python?
6. למה כדאי שאנלייזרים יהיו Pure Functions?
7. מתי Worker Pool עם Queue ומתי `gather` + `Semaphore`? (תור שגדל דינמית מול רשימה ידועה מראש.)

---

## שלב 4 — SEO Analyzer

### מה בנינו
- `analyzers/seo.py` בשתי שכבות:
  1. **Extraction** — `extract_seo_facts(html)` → `SeoFacts`: אובייקט נתונים פשוט (title, description, רמות headings, canonical, noindex, lang, viewport, Open Graph, תמונות בלי alt).
  2. **Rules** — `SeoAnalyzer` מפעיל 18 כללים per-page + 3 כללים site-wide על ה-facts.
- תיקון באג Windows: הכלי קרס כשהפלט הופנה ל-`NUL`/קונסול ישן.
- 157 בדיקות, Coverage 97%.

### הכללים שמימשנו
| `rule_id` | חומרה | למה זה חשוב |
|---|---|---|
| `seo.title.missing` | 🔴 | ה-title הוא הכותרת הכחולה בתוצאות גוגל. בלעדיו גוגל ממציא אחת. |
| `seo.title.long` / `.short` / `.multiple` | 🟡/🔵/🟡 | גוגל חותך אחרי ~60 תווים (~600px). קצר מדי = לא מתאר. |
| `seo.description.missing` / `.long` / `.short` | 🟡/🔵/🔵 | ה-snippet מתחת לכותרת. לא משפיע ישירות על דירוג, אבל משפיע מאוד על **CTR** (כמה לוחצים). |
| `seo.h1.missing` / `.multiple` | 🟡/🔵 | ה-H1 אומר לגוגל (ולקורא) מה הנושא המרכזי של הדף. |
| `seo.headings.skipped_level` | 🔵 | h1→h3 שובר את מבנה המסמך — חשוב במיוחד ל-screen readers. |
| `seo.noindex` | 🟡 | הדף **לא יופיע בגוגל**. לפעמים מכוון, לפעמים שכחו אותו מסביבת staging — אסון. |
| `seo.canonical.missing` / `.multiple` / `.broken` | 🔵/🟡/🔴 | ראה Canonical למטה. |
| `seo.lang.missing` | 🟡 | שפת הדף — לגוגל ולנגישות. |
| `seo.viewport.missing` | 🟡 | בלעדיו הדף נראה כמו desktop מוקטן בנייד. גוגל מאנדקס את גרסת המובייל (**Mobile-First Indexing**). |
| `seo.img.alt_missing` | 🟡 | גוגל "לא רואה" תמונות — הוא קורא את ה-alt. וגם נגישות לעיוורים. |
| `seo.open_graph.missing` | 🔵 | איך הקישור נראה כשמשתפים בוואטסאפ/לינקדאין. |
| `seo.duplicate.content` | 🟡 | אותו תוכן בכמה URLs — **מצאנו באתר אמיתי**: `/` ו-`/index.html`. |
| `seo.duplicate.title` / `.description` | 🟡 | עמודים שונים עם אותה כותרת "מתחרים" זה בזה בגוגל. |

### מושגים חשובים
| מונח | הסבר |
|---|---|
| **SEO (Search Engine Optimization)** | התאמת האתר כך שמנועי חיפוש יבינו אותו וידרגו אותו גבוה. **On-page SEO** = מה שבתוך ה-HTML (מה שבדקנו). **Off-page** = קישורים מאתרים אחרים. **Technical SEO** = מהירות, robots, sitemap, canonical. |
| **SERP (Search Engine Results Page)** | עמוד התוצאות של גוגל. ה-title וה-description שלך הם ה"מודעה" שלך שם. |
| **Indexing** | גוגל מכניס את הדף למאגר שלו. רק דף מאונדקס יכול להופיע בתוצאות. `noindex` = "אל תכניס אותי". |
| **Canonical URL** | `<link rel="canonical" href="...">` — "הכתובת הרשמית של התוכן הזה". כשאותו תוכן זמין בכמה URLs (`?utm_source=...`, `/index.html`, גרסת הדפסה), ה-canonical אומר לגוגל איזה מהם לדרג, ומאחד אליו את ה"כוח". |
| **Duplicate Content** | אותו תוכן בכמה כתובות. גוגל לא יודע איזו לדרג, והדירוג מתפצל. פתרון: 301 redirect או canonical משותף. |
| **Open Graph (OG)** | פרוטוקול של פייסבוק (`og:title`, `og:image`...) שכל הרשתות והאפליקציות משתמשות בו כדי לבנות "כרטיס תצוגה מקדימה" לקישור. |
| **Accessibility (a11y)** | נגישות לאנשים עם מוגבלויות. הרבה כללי SEO (alt, lang, heading order) הם גם כללי נגישות — מה שטוב ל-screen reader טוב לגוגל. |
| **Content Hashing (SHA-256)** | המרת התוכן ל"טביעת אצבע" קצרה. שני עמודים עם אותו hash = תוכן זהה. השוואת hash מהירה מהשוואת מחרוזות ארוכות. |
| **Grouping / `defaultdict(list)`** | מקבצים עמודים לפי מפתח (hash / title) ומחפשים קבוצות בגודל ≥2. כך מוצאים כפילויות ב-O(n) במקום להשוות כל זוג (O(n²)). |
| **Character Encoding** | איך תווים הופכים ל-bytes. **UTF-8** מכיל הכל; **cp1252** (ברירת מחדל ישנה של Windows) מכיל רק ~256 תווים — בלי `⠋` או `┌`. |

### החלטות ארכיטקטורה ולמה
- **שתי שכבות: Facts ← Rules** — הכללים לא יודעים ש-BeautifulSoup קיים. אם מחר נחליף parser, רק `extract_seo_facts` משתנה. וכל שכבה נבדקת לחוד.
- **Baseline Test ("עמוד מושלם = 0 issues")** — הבדיקה החשובה ביותר בקובץ. כל בדיקה אחרת לוקחת את העמוד המושלם ומשנה **דבר אחד**, ומוודאת ש**בדיוק כלל אחד** נדלק. כך מגלים גם כללים שנדלקים בטעות (false positives), לא רק כללים שלא נדלקים.
- **כפילויות חכמות** — לא מדווחים על אותה בעיה פעמיים: עמודים זהים מדווחים כ-duplicate content בלבד (לא שוב כ-duplicate title). עמודי noindex ועמודים שה-canonical שלהם מפנה למקום אחר מוחרגים — הם לא "מתחרים" בגוגל.
- **`alt=""` תקין** — תמונה דקורטיבית *צריכה* alt ריק (כדי ש-screen reader ידלג). רק **היעדר** של ה-attribute הוא בעיה. הבחנה כזו היא ההבדל בין כלי מקצועי לכלי שמציף false positives.
- **`<title>` בתוך `<svg>` מוחרג** — SVG משתמש ב-`<title>` ככיתוב לאייקון. בלי ההחרגה, כל אתר עם אייקונים היה מקבל "multiple titles".
- **ספים מה-config** — 60 תווים ל-title זו המלצה, לא חוק טבע. משתמש יכול לשנות.

### באגים ותגליות מהשלב 🐛
1. **קריסה ב-Windows כשמפנים את הפלט:** `sitepulse scan ... > /dev/null` קרס עם `UnicodeEncodeError`. הסיבה: ב-Windows, `NUL` הוא "character device", אז Rich חושב שזה טרמינל ומצייר spinner (`⠋`) — אבל הקידוד הוא cp1252 שלא מכיר את התו. התיקון: `stream.reconfigure(errors="replace")` — תו שלא ניתן לקידוד הופך ל-`?` במקום להפיל את כל הסריקה. **לקח: תמיד לבדוק גם את מסלול "הפלט לא הולך לטרמינל"** — ככה הכלי ירוץ ב-CI.
2. **Description ריק = חסר:** books.toscrape מכיל `<meta name="description" content="">`. התג *קיים* אבל ריק — הכלי מזהה את זה נכון כ-missing. אימתנו מול ה-HTML האמיתי עם `curl` לפני שהאמנו לתוצאה.
3. **mypy תפס שימוש חוזר בשם משתנה** (`page`) לשני טיפוסים שונים באותה פונקציה — באג קלאסי שגורם לבלבול.

### טיפ Claude Code מהשלב
- **לאמת תוצאות מפתיעות:** "20 מתוך 20 עמודים בלי description" נשמע חשוד. במקום לקבל את זה, Claude Code בדק את ה-HTML המקורי עם `curl`. כשה-AI (או הכלי שלך) מחזיר משהו מפתיע — לאמת מול המקור.
- **שגיאה שקטה היא הכי מסוכנת:** הקריסה ב-Windows התגלתה רק כי שמנו לב ש-`exit=1` ושקובץ ה-JSON לא נוצר. כדאי לבקש מ-Claude Code להדפיס תמיד את ה-exit code של פקודות חשובות.
- **Linters כ"סוקר קוד" נוסף:** ruff הציע `itertools.pairwise()` (קוד אידיומטי יותר) ו-mypy תפס באג. ככל שיש יותר כלים אוטומטיים, ה-AI מקבל יותר משוב ומתקן את עצמו.

### שאלות ראיון אפשריות
1. מה זה canonical URL ומתי משתמשים בו?
2. מה ההבדל בין `noindex` ב-meta robots לבין `Disallow` ב-robots.txt? (Disallow = "אל תסרוק", noindex = "אל תאנדקס". דף חסום ב-robots.txt עדיין יכול להופיע בגוגל אם מקשרים אליו!)
3. למה `alt=""` תקין אבל `alt` חסר לא?
4. איך מוצאים כפילויות ביעילות באוסף גדול? (Hashing + grouping ב-O(n).)
5. מה זה Baseline Test ולמה הוא חשוב לכלי שמחפש בעיות?
6. מה ההבדל בין UTF-8 ל-cp1252, ולמה קוד שעובד בטרמינל יכול לקרוס ב-CI?

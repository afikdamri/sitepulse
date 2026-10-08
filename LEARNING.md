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

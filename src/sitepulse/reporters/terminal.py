"""The human-facing report: a Rich layout of scores, recommendations, broken links and timings.

Reporters only *display* the AuditReport - every number shown was computed upstream.
"""

from collections import defaultdict

from rich import box
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from sitepulse.analyzers.base import short_url
from sitepulse.analyzers.links import UNVERIFIABLE_STATUSES
from sitepulse.models import (
    AuditReport,
    Category,
    CategoryScore,
    Issue,
    LinkResult,
    PageResult,
    Severity,
    grade_for,
)

GRADE_STYLES = {"A": "bold green", "B": "green", "C": "yellow", "D": "dark_orange", "F": "bold red"}
SEVERITY_STYLES = {Severity.CRITICAL: "bold red", Severity.WARNING: "yellow", Severity.INFO: "cyan"}
CATEGORY_LABELS = {
    Category.LINKS: "Links",
    Category.SEO: "SEO",
    Category.PERFORMANCE: "Performance",
    Category.SECURITY: "Security",
}
SHORT_LABELS = {Category.PERFORMANCE: "Perf"}  # for narrow terminals
MAX_BROKEN_LINKS = 15
MAX_ISSUES_PER_RULE = 25  # in --details mode
MAX_BAR_WIDTH = 20
CARD_CHROME = 6  # panel borders + padding + grid gap around each bar


class TerminalReporter:
    def __init__(self, console: Console, *, top: int = 10, details: bool = False) -> None:
        self._console = console
        self._top = top
        self._details = details

    @property
    def _ascii(self) -> bool:
        """True on consoles that can't draw Unicode (legacy Windows code pages)."""
        return self._console.options.ascii_only

    def render(self, report: AuditReport) -> None:
        sections: list[RenderableType | None] = [
            self._header(report),
            self._scorecards(report),
            self._recommendations(report),
            self._broken_links(report),
            self._performance(report),
        ]
        if self._details:
            sections += [self._all_issues(report), self._pages(report)]
        sections.append(self._footer(report))
        for section in sections:
            if section is not None:
                self._console.print(section)
                self._console.print()

    # ---- header & scores ----------------------------------------------------------------------

    def _header(self, report: AuditReport) -> Panel:
        started = report.started_at.strftime("%Y-%m-%d %H:%M UTC")
        facts = self._join(
            [
                started,
                f"{report.duration_s:g}s",
                f"{len(report.pages)} pages crawled",
                f"{len(report.links)} links checked",
            ]
        )
        body = Group(Text(report.target_url, style="bold underline"), Text(facts, style="dim"))
        return Panel(
            body,
            title="[bold]SitePulse[/] audit report",
            title_align="left",
            border_style="blue",
        )

    def _scorecards(self, report: AuditReport) -> Table:
        criticals = sum(1 for i in report.issues if i.severity == Severity.CRITICAL)
        overall_note = (
            Text(f"{criticals} critical issue(s)", style="bold red")
            if criticals
            else Text("no critical issues", style="green")
        )
        # Fit the bars to the terminal: five cards share the width.
        card_count = 1 + len(report.scores)
        bar_width = max(5, min(MAX_BAR_WIDTH, self._console.width // card_count - CARD_CHROME))
        narrow = bar_width < len(CATEGORY_LABELS[Category.PERFORMANCE]) + 2
        cards = [self._card("Overall", report.overall_score, overall_note, bar_width)]
        cards += [
            self._card(self._label(s.category, narrow), s.score, self._counts(s), bar_width)
            for s in report.scores
        ]
        # A grid with equal-ratio columns spreads the cards evenly across the terminal width.
        grid = Table.grid(expand=True, padding=(0, 1))
        for _ in cards:
            grid.add_column(ratio=1)
        grid.add_row(*cards)
        return grid

    @staticmethod
    def _label(category: Category, narrow: bool) -> str:
        if narrow:
            return SHORT_LABELS.get(category, CATEGORY_LABELS[category])
        return CATEGORY_LABELS[category]

    def _card(self, title: str, score: float, note: Text, bar_width: int) -> Panel:
        grade = grade_for(score)
        style = GRADE_STYLES[grade]
        headline = Text.assemble(
            (f"{score:g}", f"bold {style}"), ("/100  ", "dim"), (grade, f"bold {style}")
        )
        return Panel(
            Group(headline, self._bar(score, style, bar_width), note),
            title=title,
            title_align="left",
            border_style=style,
        )

    def _bar(self, score: float, style: str, width: int) -> Text:
        filled = round(score / 100 * width)
        full, empty = ("#", "-") if self._ascii else ("█", "░")
        return Text(full * filled, style=style) + Text(empty * (width - filled), style="dim")

    def _counts(self, score: CategoryScore) -> Text:
        parts = [
            (f"{score.issue_counts[sev]} {sev.value}", SEVERITY_STYLES[sev])
            for sev in Severity
            if score.issue_counts.get(sev)
        ]
        if not parts:
            return Text("no issues", style="green")
        text = Text()
        for index, (label, style) in enumerate(parts):
            if index:
                text.append(", ", style="dim")
            text.append(label, style=style)
        return text

    # ---- recommendations ------------------------------------------------------------------------

    def _recommendations(self, report: AuditReport) -> RenderableType:
        if not report.recommendations:
            return Panel(
                Text("No issues found - this site is in great shape!", style="bold green"),
                border_style="green",
            )
        shown = report.recommendations[: self._top]
        table = Table(
            title=f"Top {len(shown)} recommendations",
            title_justify="left",
            title_style="bold",
            box=box.SIMPLE_HEAD,
            expand=True,
        )
        table.add_column("#", justify="right", style="dim", width=3)
        table.add_column("Severity", no_wrap=True)
        table.add_column("Problem", ratio=2)
        table.add_column("Pages", justify="right")
        table.add_column("Gain", justify="right", no_wrap=True)
        table.add_column("How to fix", ratio=3)
        for index, rec in enumerate(shown, start=1):
            problem = Text(rec.title)
            if rec.example_urls:
                problem.append(f"\ne.g. {short_url(rec.example_urls[0])}", style="dim")
            table.add_row(
                str(index),
                Text(rec.severity.value, style=SEVERITY_STYLES[rec.severity]),
                problem,
                str(rec.affected_pages),
                Text(f"+{rec.impact:.1f}", style="green"),
                rec.action,
            )
        hidden = len(report.recommendations) - len(shown)
        if hidden:
            table.caption = f"+{hidden} more - run with --details to see everything"
        return table

    # ---- broken links -------------------------------------------------------------------------

    def _broken_links(self, report: AuditReport) -> Table | None:
        broken = [link for link in report.links if _really_broken(link)]
        if not broken:
            return None
        broken.sort(key=lambda link: (not link.is_internal, link.status_code or 0, link.url))
        table = Table(
            title=f"Broken links ({len(broken)})",
            title_justify="left",
            title_style="bold",
            box=box.SIMPLE_HEAD,
            expand=True,
        )
        table.add_column("Status", no_wrap=True)
        table.add_column("Type", no_wrap=True)
        table.add_column("Link", ratio=3, overflow="fold")
        table.add_column("Found on", ratio=2, overflow="fold")
        for link in broken[:MAX_BROKEN_LINKS]:
            status = str(link.status_code) if link.status_code else (link.error or "error")
            kind = (
                "resource" if link.is_resource else "internal" if link.is_internal else "external"
            )
            found_on = short_url(link.found_on[0]) if link.found_on else "-"
            if len(link.found_on) > 1:
                found_on += f" (+{len(link.found_on) - 1})"
            table.add_row(Text(status, style="bold red"), kind, link.url, found_on)
        if len(broken) > MAX_BROKEN_LINKS:
            table.caption = f"+{len(broken) - MAX_BROKEN_LINKS} more - see the JSON report"
        return table

    # ---- performance --------------------------------------------------------------------------

    def _performance(self, report: AuditReport) -> Panel | None:
        stats = report.performance
        if stats is None:
            return None
        timings = Table(box=None, show_header=True, padding=(0, 2))
        timings.add_column("")
        for column in ("p50", "p95", "max"):
            timings.add_column(column, justify="right")
        timings.add_row(
            "Server response",
            _ms(stats.server_time.p50_ms),
            _ms(stats.server_time.p95_ms),
            _ms(stats.server_time.max_ms),
        )
        timings.add_row(
            "Full download",
            _ms(stats.response_time.p50_ms),
            _ms(stats.response_time.p95_ms),
            _ms(stats.response_time.max_ms),
        )

        lines: list[RenderableType] = [timings, Text()]
        if stats.avg_connect_ms is not None:
            lines.append(Text(f"New connection setup (TCP+TLS): {stats.avg_connect_ms:.0f} ms"))
        arrow = "->" if self._ascii else "→"
        size_line = (
            f"HTML: {stats.total_html_kb:,.0f} KB {arrow} {stats.total_transfer_kb:,.0f} KB "
            f"transferred, {stats.compressed_pages}/{stats.pages_measured} pages compressed"
        )
        if stats.total_html_kb and stats.total_transfer_kb < stats.total_html_kb:
            saved = 1 - stats.total_transfer_kb / stats.total_html_kb
            size_line += f" ({saved:.0%} saved)"
        lines.append(Text(size_line))

        pages = {page.url: page for page in report.pages}
        slowest = [pages[url] for url in stats.slowest_pages if url in pages]
        if slowest:
            table = Table(title="Slowest pages", title_justify="left", box=box.SIMPLE_HEAD)
            table.add_column("Server", justify="right")
            table.add_column("Total", justify="right")
            table.add_column("Page", overflow="fold")
            for page in slowest:
                table.add_row(_ms(page.server_ms), _ms(page.response_time_ms), page.url)
            lines += [Text(), table]

        title = f"Performance ({stats.pages_measured} pages measured)"
        return Panel(Group(*lines), title=title, title_align="left", border_style="magenta")

    # ---- details mode -------------------------------------------------------------------------

    def _all_issues(self, report: AuditReport) -> Tree | None:
        if not report.issues:
            return None
        by_rule: dict[str, list[Issue]] = defaultdict(list)
        for issue in report.issues:
            by_rule[issue.rule_id].append(issue)
        tree = Tree(Text(f"All issues ({len(report.issues)})", style="bold"))
        for rec in report.recommendations:
            issues = by_rule[rec.rule_id]
            branch = tree.add(
                Text.assemble(
                    (rec.title, SEVERITY_STYLES[rec.severity]),
                    (f"  [{rec.rule_id}] x{len(issues)}", "dim"),
                )
            )
            for issue in issues[:MAX_ISSUES_PER_RULE]:
                branch.add(issue.message)
            if len(issues) > MAX_ISSUES_PER_RULE:
                branch.add(Text(f"... {len(issues) - MAX_ISSUES_PER_RULE} more", style="dim"))
        return tree

    def _pages(self, report: AuditReport) -> Table:
        table = Table(
            title=f"Crawled pages ({len(report.pages)})",
            title_justify="left",
            title_style="bold",
            box=box.SIMPLE_HEAD,
        )
        table.add_column("Status", justify="right")
        table.add_column("Server", justify="right")
        table.add_column("Total", justify="right")
        table.add_column("Depth", justify="right")
        table.add_column("URL", overflow="fold")
        for page in report.pages:
            table.add_row(
                _status(page),
                _ms(page.server_ms),
                _ms(page.response_time_ms),
                str(page.depth),
                page.url,
            )
        return table

    # ---- footer -------------------------------------------------------------------------------

    def _footer(self, report: AuditReport) -> Group:
        lines = [Text(f"i {note}", style="dim") for note in report.notes]
        criticals = sum(1 for i in report.issues if i.severity == Severity.CRITICAL)
        if criticals:
            verdict = Text(f"{criticals} critical issue(s) need attention.", style="bold red")
        elif report.issues:
            verdict = Text("No critical issues - see recommendations above.", style="bold yellow")
        else:
            verdict = Text("All checks passed.", style="bold green")
        grade = report.overall_grade
        lines.append(
            Text.assemble(
                ("Overall: ", "bold"),
                (f"{report.overall_score:g}/100 ({grade})", GRADE_STYLES[grade]),
                "  ",
                verdict,
            )
        )
        return Group(*lines)

    def _join(self, parts: list[str]) -> str:
        return (" | " if self._ascii else " · ").join(parts)


def _really_broken(link: LinkResult) -> bool:
    """Broken, excluding external sites that merely block bots (reported as info only)."""
    if not link.is_broken:
        return False
    return link.is_internal or link.status_code not in UNVERIFIABLE_STATUSES


def _status(page: PageResult) -> Text:
    if page.status_code is None:
        return Text(page.error or "error", style="bold red")
    code = page.status_code
    style = "green" if code < 300 else "yellow" if code < 400 else "bold red"
    return Text(str(code), style=style)


def _ms(value: float | None) -> str:
    return "-" if value is None else f"{value:,.0f} ms"

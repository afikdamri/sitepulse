"""Turn link check results into issues: broken links, dead hosts, redirects, mixed content."""

from sitepulse.analyzers.base import AuditData, describe_pages
from sitepulse.models import Category, Issue, LinkResult, PageResult, Severity

# External sites often block bots with these codes; the link probably works for humans.
UNVERIFIABLE_STATUSES = {401, 403, 429, 999}  # 999 = LinkedIn's anti-bot response
MAX_REDIRECT_HOPS = 1


class LinkAnalyzer:
    category = Category.LINKS

    def analyze(self, data: AuditData) -> list[Issue]:
        issues: list[Issue] = []
        for link in data.links:
            issue = self._check(link)
            if issue is not None:
                # A broken link in the site navigation hurts every page that shows it.
                issue.affected = max(1, len(link.found_on))
                issues.append(issue)
        issues.extend(self._mixed_content(page) for page in data.pages if _has_mixed_content(page))
        return issues

    def _check(self, link: LinkResult) -> Issue | None:
        where = f"linked from {describe_pages(link.found_on)}"
        kind = "resource" if link.is_resource else "link"

        if link.error is not None:
            internal = link.is_internal or link.is_resource
            return self._issue(
                "links.unreachable",
                Severity.CRITICAL if internal else Severity.WARNING,
                f"Unreachable {kind} {link.url} ({link.error}), {where}",
                "Check that the host is up and the URL is correct; remove the link if the "
                "site no longer exists.",
                link.url,
            )

        status = link.status_code or 0
        if status >= 400:
            if not link.is_internal and status in UNVERIFIABLE_STATUSES:
                return self._issue(
                    "links.external.unverifiable",
                    Severity.INFO,
                    f"Could not verify external link {link.url} (HTTP {status}, likely bot "
                    f"protection), {where}",
                    "Open the link in a browser to confirm it works.",
                    link.url,
                )
            if link.is_resource:
                return self._issue(
                    "links.resource.broken",
                    Severity.CRITICAL,
                    f"Broken resource {link.url} (HTTP {status}), {where}",
                    "Restore the missing file or update the src/href; broken images, scripts "
                    "and stylesheets visibly break the page.",
                    link.url,
                )
            if link.is_internal:
                return self._issue(
                    "links.internal.broken",
                    Severity.CRITICAL,
                    f"Broken internal link {link.url} (HTTP {status}), {where}",
                    "Fix the href on those pages, or add a 301 redirect from this URL to the "
                    "correct page.",
                    link.url,
                )
            return self._issue(
                "links.external.broken",
                Severity.WARNING,
                f"Broken external link {link.url} (HTTP {status}), {where}",
                "Update the link to the page's new address or remove it.",
                link.url,
            )

        if (
            link.url.startswith("https://")
            and link.final_url is not None
            and link.final_url.startswith("http://")
        ):
            return self._issue(
                "links.redirect.insecure",
                Severity.WARNING,
                f"HTTPS link {link.url} redirects to insecure {link.final_url}, {where}",
                "Fix the server redirect so it keeps https://; downgrading to HTTP exposes "
                "visitors to eavesdropping and triggers browser warnings.",
                link.url,
            )
        if link.redirect_count > MAX_REDIRECT_HOPS:
            return self._issue(
                "links.redirect.chain",
                Severity.WARNING,
                f"Redirect chain of {link.redirect_count} hops: {link.url} -> {link.final_url}, "
                f"{where}",
                "Point the link (and the first redirect) straight at the final URL; every hop "
                "adds latency and dilutes ranking signals.",
                link.url,
            )
        if link.is_internal and link.redirect_count == 1:
            return self._issue(
                "links.internal.redirect",
                Severity.INFO,
                f"Internal link {link.url} redirects to {link.final_url}, {where}",
                "Update the href to the final URL to save a round-trip.",
                link.url,
            )
        return None

    def _mixed_content(self, page: PageResult) -> Issue:
        insecure = [url for url in page.resources if url.startswith("http://")]
        return self._issue(
            "links.mixed_content",
            Severity.WARNING,
            f"HTTPS page loads {len(insecure)} resource(s) over insecure HTTP: "
            f"{', '.join(insecure[:3])}",
            "Serve these resources over https://; browsers block or warn about mixed content.",
            page.url,
        )

    def _issue(
        self, rule_id: str, severity: Severity, message: str, recommendation: str, url: str
    ) -> Issue:
        return Issue(
            rule_id=rule_id,
            category=self.category,
            severity=severity,
            message=message,
            recommendation=recommendation,
            url=url,
        )


def _has_mixed_content(page: PageResult) -> bool:
    page_url = page.final_url or page.url
    return page_url.startswith("https://") and any(
        url.startswith("http://") for url in page.resources
    )

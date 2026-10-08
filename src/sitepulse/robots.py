"""robots.txt support: which URLs we may crawl and how fast."""

from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import httpx

ROBOTS_AGENT = "SitePulse"  # the token site owners would use in `User-agent:` lines


class RobotsPolicy:
    def __init__(self, parser: RobotFileParser | None = None, agent: str = ROBOTS_AGENT) -> None:
        self._parser = parser  # None means "no rules, everything allowed"
        self._agent = agent

    @classmethod
    def allow_all(cls) -> "RobotsPolicy":
        return cls()

    @classmethod
    def from_text(cls, text: str, agent: str = ROBOTS_AGENT) -> "RobotsPolicy":
        parser = RobotFileParser()
        parser.parse(text.splitlines())
        return cls(parser, agent)

    @classmethod
    async def fetch(cls, client: httpx.AsyncClient, site_url: str) -> "RobotsPolicy":
        """Download /robots.txt for the site. Missing or unreadable files allow everything.

        (Google treats a 5xx here as "disallow all"; for an audit tool the owner runs on their
        own site, being lenient is more useful.)
        """
        try:
            response = await client.get(urljoin(site_url, "/robots.txt"))
        except httpx.HTTPError:
            return cls.allow_all()
        if response.status_code >= 400:
            return cls.allow_all()
        return cls.from_text(response.text)

    def can_fetch(self, url: str) -> bool:
        return self._parser is None or self._parser.can_fetch(self._agent, url)

    @property
    def crawl_delay(self) -> float | None:
        if self._parser is None:
            return None
        delay = self._parser.crawl_delay(self._agent)
        return float(delay) if delay is not None else None

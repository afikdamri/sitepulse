"""Machine-readable output: the full AuditReport as JSON."""

from pathlib import Path

from sitepulse.models import AuditReport


def report_to_json(report: AuditReport) -> str:
    return report.model_dump_json(indent=2)


def write_json(report: AuditReport, path: Path) -> None:
    path.write_text(report_to_json(report) + "\n", encoding="utf-8")

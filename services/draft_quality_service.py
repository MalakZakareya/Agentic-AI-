"""Conservative, deterministic draft-quality review hints.

This module does not establish legal compliance or semantic correctness.
"""

from typing import Any
import re


GENERIC_PHRASES = {
    "as applicable",
    "to be agreed",
    "subject to agreement",
    "the details of this section shall be agreed upon by the parties",
}


def inspect_draft_quality(
    draft_text: str,
    structure_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return review flags without modifying or rejecting the draft."""

    text = draft_text if isinstance(draft_text, str) else ""
    lines = text.splitlines()

    heading_pattern = re.compile(
        r"^\s*\d+\.\s+\S.*$"
    )

    headings = [
        index
        for index, line in enumerate(lines)
        if heading_pattern.match(line)
    ]

    findings: list[dict[str, Any]] = []
    seen_content: dict[str, int] = {}

    for position, start in enumerate(headings):
        end = (
            headings[position + 1]
            if position + 1 < len(headings)
            else len(lines)
        )

        heading = lines[start].strip()
        body = " ".join(
            line.strip()
            for line in lines[start + 1:end]
            if line.strip()
        )

        normalized = " ".join(body.lower().split())
        normalized_no_period = normalized.rstrip(". ")

        if not body:
            findings.append({
                "heading": heading,
                "code": "EMPTY_SECTION",
                "severity": "review",
            })
            continue

        if normalized_no_period in GENERIC_PHRASES:
            findings.append({
                "heading": heading,
                "code": "GENERIC_SECTION",
                "severity": "review",
            })

        if len(body) < 35:
            findings.append({
                "heading": heading,
                "code": "VERY_SHORT_SECTION",
                "severity": "review",
            })

        if len(normalized) >= 80:
            if normalized in seen_content:
                findings.append({
                    "heading": heading,
                    "code": "DUPLICATED_SECTION_TEXT",
                    "severity": "review",
                    "matches_section": seen_content[normalized],
                })
            else:
                seen_content[normalized] = position + 1

    return {
        "status": (
            "REVIEW_FLAGS_PRESENT"
            if findings
            else "NO_DETERMINISTIC_FLAGS"
        ),
        "findings": findings,
        "finding_count": len(findings),
        "sections_inspected": len(headings),
        "semantic_consistency_verified": False,
        "legal_compliance_verified": False,
        "human_review_required": True,
    }

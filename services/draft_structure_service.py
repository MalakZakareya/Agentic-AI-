
"""Structural checks for draft documents; not legal verification."""

import re
from typing import Any

from services.draft_service import get_draft_sections


def inspect_draft_structure(
    draft_type: str,
    draft_text: str,
) -> dict[str, Any]:
    sections = get_draft_sections(draft_type)
    text = draft_text if isinstance(draft_text, str) else ""
    lines = text.splitlines()

    missing = []
    empty = []
    duplicate = []
    placeholder_sections = []
    generic_sections = []
    findings = []
    headings = []

    slash = chr(92)

    for section in sections:
        key = str(section.get("key", "")).strip()
        title = str(section.get("title", "")).strip()

        if not title:
            continue

        pattern = re.compile(
            "^" + slash + "s*" +
            slash + "d+" + slash + "." +
            slash + "s+" + re.escape(title) +
            slash + "s*$",
            re.IGNORECASE,
        )

        matches = [
            index
            for index, line in enumerate(lines)
            if pattern.match(line)
        ]

        if not matches:
            missing.append(key)
            findings.append({
                "key": key,
                "title": title,
                "status": "MISSING",
            })
        elif len(matches) > 1:
            duplicate.append(key)
            findings.append({
                "key": key,
                "title": title,
                "status": "DUPLICATE",
            })
        else:
            headings.append((matches[0], key, title))

    headings.sort()

    for position, (line_index, key, title) in enumerate(headings):
        next_index = (
            headings[position + 1][0]
            if position + 1 < len(headings)
            else len(lines)
        )

        content = [
            line.strip()
            for line in lines[line_index + 1:next_index]
            if line.strip()
            and set(line.strip()) != {"-"}
        ]

        placeholder_pattern = re.compile(
            r"\[(?:TO BE COMPLETED|INSERT[^\]]*|TBD|"
            r"FILL IN[^\]]*|PLACEHOLDER)\]",
            re.IGNORECASE,
        )

        generic_section_pattern = re.compile(
            r"This section\s*\([^)]*\)\s*shall\s+"
            r"contain\s+the\s+terms\s+agreed\s+"
            r"by\s+the\s+parties\s+based\s+on\s+"
            r"the\s+information\s+provided\s*\.?",
            re.IGNORECASE,
        )

        has_placeholder = any(
            placeholder_pattern.search(line)
            or line.strip().upper() in {"TBD", "N/A"}
            for line in content
        )

        generic_phrases = {
            "as applicable.",
            "as applicable",
            "to be agreed.",
            "to be agreed",
            "subject to agreement.",
            "subject to agreement",
            "the details of this section shall be "
            "agreed upon by the parties.",
        }

        normalized_content = " ".join(
            " ".join(content).lower().split()
        )

        has_generic_content = (
            normalized_content in generic_phrases
            or any(
                generic_section_pattern.search(line)
                for line in content
            )
        )

        if not content:
            empty.append(key)
            section_status = "EMPTY"
        elif has_generic_content:
            generic_sections.append(key)
            section_status = "GENERIC_CONTENT_REVIEW_REQUIRED"
        elif has_placeholder:
            placeholder_sections.append(key)
            section_status = "PLACEHOLDER_REVIEW_REQUIRED"
        else:
            section_status = "PRESENT"

        findings.append({
            "key": key,
            "title": title,
            "status": section_status,
            "content_characters": sum(map(len, content)),
        })

    if not text.strip():
        status = "EMPTY_DOCUMENT"
    elif not sections:
        status = "UNSTRUCTURED_REVIEW_REQUIRED"
    elif (
        missing
        or empty
        or duplicate
        or generic_sections
    ):
        status = "INCOMPLETE"
    elif placeholder_sections:
        status = "NEEDS_USER_INPUT"
    else:
        status = "STRUCTURALLY_PRESENT"

    return {
        "draft_type": draft_type,
        "status": status,
        "expected_sections": len(sections),
        "missing_sections": missing,
        "empty_sections": empty,
        "duplicate_sections": duplicate,
        "placeholder_sections": placeholder_sections,
        "generic_sections": generic_sections,
        "sections": findings,
        "legal_compliance_verified": False,
        "human_review_required": True,
    }

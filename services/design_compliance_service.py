import json
from typing import Any, cast

from core.config import settings
from services.ai_provider import generate_ai_text


class DesignComplianceError(Exception):
    pass


ALLOWED_STATUSES = {
    "PASS",
    "ISSUE",
    "WARNING",
    "NOT VERIFIED",
}


def clean_json_response(
    text: str,
) -> str:
    cleaned = text.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]

    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    return cleaned.strip()


def get_requirement_source_url(
    requirement: dict[str, Any],
) -> str:
    """
    Return a trusted official NEA source URL.

    Prefer the direct official standards document.
    Fall back to the official NEA documents page.
    """

    document_url = str(
        requirement.get(
            "document_url",
            "",
        )
    ).strip()

    if document_url:
        return document_url

    source_page_url = str(
        requirement.get(
            "source_page_url",
            "",
        )
    ).strip()

    if source_page_url:
        return source_page_url

    return ""


def build_requirement_key(
    section_number: str,
    title: str,
) -> str:
    return (
        section_number.strip().lower()
        + "|"
        + title.strip().lower()
    )


def build_trusted_requirement_map(
    nea_requirements: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Build a map of the NEA requirements that were actually
    retrieved from the trusted local knowledge base.

    The AI is only allowed to return sections contained here.
    """

    trusted_map: dict[
        str,
        dict[str, Any],
    ] = {}

    for requirement in nea_requirements:
        section_number = str(
            requirement.get(
                "section_number",
                "",
            )
        ).strip()

        title = str(
            requirement.get(
                "title",
                "",
            )
        ).strip()

        if not section_number:
            continue

        key = build_requirement_key(
            section_number=section_number,
            title=title,
        )

        trusted_map[key] = requirement

    return trusted_map


def find_trusted_requirement(
    section_number: str,
    title: str,
    nea_requirements: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Find the real NEA requirement corresponding
    to an AI result.

    First try section number + title.
    If that fails, fall back to section number only.
    """

    trusted_map = build_trusted_requirement_map(
        nea_requirements
    )

    exact_key = build_requirement_key(
        section_number=section_number,
        title=title,
    )

    exact_match = trusted_map.get(
        exact_key
    )

    if exact_match is not None:
        return exact_match

    normalized_section = (
        section_number.strip().lower()
    )

    section_matches: list[
        dict[str, Any]
    ] = []

    for requirement in nea_requirements:
        trusted_section = str(
            requirement.get(
                "section_number",
                "",
            )
        ).strip().lower()

        if (
            trusted_section
            == normalized_section
        ):
            section_matches.append(
                requirement
            )

    if len(section_matches) == 1:
        return section_matches[0]

    return None


def build_safe_requirements_for_ai(
    nea_requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Build the requirements sent to the AI.

    Source metadata is included for context, but
    the final source returned to the frontend is
    always restored from the trusted knowledge
    base after the AI response.
    """

    safe_requirements: list[
        dict[str, Any]
    ] = []

    for requirement in nea_requirements:
        section_number = str(
            requirement.get(
                "section_number",
                "",
            )
        ).strip()

        if not section_number:
            continue

        safe_requirements.append(
            {
                "source_id": str(
                    requirement.get(
                        "source_id",
                        "",
                    )
                ).strip(),
                "source_title": str(
                    requirement.get(
                        "source_title",
                        "",
                    )
                ).strip(),
                "authority": str(
                    requirement.get(
                        "authority",
                        "",
                    )
                ).strip(),
                "section_number": (
                    section_number
                ),
                "title": str(
                    requirement.get(
                        "title",
                        "",
                    )
                ).strip(),
                "text": str(
                    requirement.get(
                        "text",
                        "",
                    )
                ).strip(),
                "matched_element": str(
                    requirement.get(
                        "matched_element",
                        "",
                    )
                ).strip(),
                "source_url": (
                    get_requirement_source_url(
                        requirement
                    )
                ),
            }
        )

    return safe_requirements


def build_compliance_prompt(
    observations: list[dict[str, Any]],
    nea_requirements: list[dict[str, Any]],
) -> str:
    observations_json = json.dumps(
        observations,
        ensure_ascii=False,
        indent=2,
    )

    safe_requirements = (
        build_safe_requirements_for_ai(
            nea_requirements
        )
    )

    requirements_json = json.dumps(
        safe_requirements,
        ensure_ascii=False,
        indent=2,
    )

    return f"""
You are reviewing a website or mobile application
UI design against retrieved Bahrain NEA requirements.

You must use ONLY:

1. The visual observations provided below.
2. The retrieved NEA requirements provided below.

Do not invent requirements.
Do not use requirements that were not provided.
Do not invent section numbers.
Do not invent titles.
Do not invent source URLs.
Do not claim that something is visible unless it
appears in the visual observations.

For each relevant NEA requirement, determine one
of these statuses:

PASS:

The visual evidence clearly shows that the
requirement is satisfied.

ISSUE:

The visual evidence clearly shows a conflict
with the requirement.

WARNING:

There is visible evidence of a possible concern,
but the evidence is not sufficient for a definite
ISSUE.

NOT VERIFIED:

The requirement cannot be reliably checked from
the supplied visual design alone.

Important:

Technical, behavioral, accessibility, navigation,
link-target, HTML, runtime, keyboard, screen-reader,
responsive, or implementation requirements that
cannot be proven from the supplied static visual
evidence must be NOT VERIFIED.

For every result:

- preserve the exact NEA section number
- preserve the exact NEA title
- explain only the observed visual evidence
- explain the comparison with the requirement
- provide a practical recommendation when useful
- use only a requirement supplied below
- do not invent a source
- do not make assumptions about hidden behavior

VISUAL OBSERVATIONS:

{observations_json}

RETRIEVED NEA REQUIREMENTS:

{requirements_json}

Return valid JSON only in this exact structure:

{{
    "results": [
        {{
            "section_number": "4.20",
            "title": "Colors",
            "status": "PASS",
            "observed_evidence": "Visible evidence",
            "analysis": "Comparison with the requirement",
            "recommendation": "Recommendation"
        }}
    ]
}}
"""
def validate_compliance_results(
    raw_results: Any,
    nea_requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Validate AI output against the requirements actually
    retrieved from the trusted NEA knowledge base.

    The source URL is NEVER trusted from AI output.
    """

    if not isinstance(
        raw_results,
        list,
    ):
        raise DesignComplianceError(
            "AI returned an invalid "
            "compliance results list."
        )

    validated: list[
        dict[str, Any]
    ] = []

    seen_requirements: set[str] = set()

    for raw_item in cast(
        list[Any],
        raw_results,
    ):
        if not isinstance(
            raw_item,
            dict,
        ):
            continue

        item = cast(
            dict[str, Any],
            raw_item,
        )

        section_number = str(
            item.get(
                "section_number",
                "",
            )
        ).strip()

        title = str(
            item.get(
                "title",
                "",
            )
        ).strip()

        status = str(
            item.get(
                "status",
                "NOT VERIFIED",
            )
        ).strip().upper()

        observed_evidence = str(
            item.get(
                "observed_evidence",
                "",
            )
        ).strip()

        analysis = str(
            item.get(
                "analysis",
                "",
            )
        ).strip()

        recommendation = str(
            item.get(
                "recommendation",
                "",
            )
        ).strip()

        if not section_number:
            continue

        trusted_requirement = (
            find_trusted_requirement(
                section_number=section_number,
                title=title,
                nea_requirements=(
                    nea_requirements
                ),
            )
        )

        # Reject any requirement invented by AI.
        if trusted_requirement is None:
            continue

        trusted_section = str(
            trusted_requirement.get(
                "section_number",
                "",
            )
        ).strip()

        trusted_title = str(
            trusted_requirement.get(
                "title",
                "",
            )
        ).strip()

        unique_key = (
            build_requirement_key(
                section_number=trusted_section,
                title=trusted_title,
            )
        )

        if unique_key in seen_requirements:
            continue

        seen_requirements.add(
            unique_key
        )

        if status not in ALLOWED_STATUSES:
            status = "NOT VERIFIED"


        # Safety guard used in real AI and test workflows.
        # A visual design alone cannot establish hidden behavior.
        requirement_text = str(
            trusted_requirement.get("text", "")
        ).strip()

        evidence = observed_evidence.strip()
        evidence_normalized = evidence.casefold()

        unverifiable_evidence = {
            "",
            "none",
            "n/a",
            "not visible",
            "not observed",
            "not provided",
            "unknown",
            "no evidence",
            "insufficient evidence",
        }

        informational_titles = {
            "introduction",
            "scope",
            "objective",
            "objectives",
            "definitions",
            "references",
            "background",
            "purpose",
        }

        title_normalized = trusted_title.strip().casefold()

        informational_section = (
            title_normalized in informational_titles
        )

        # Avoid declaring a violation from a section that
        # has no actionable requirement language.
        actionable_terms = (
            "must", "shall", "required", "mandatory",
            "should", "ensure", "provide", "display",
            "include", "use", "avoid", "do not",
            "recommended", "recommendation",
        )

        has_actionable_text = any(
            term in requirement_text.casefold()
            for term in actionable_terms
        )

        if status in {"ISSUE", "PASS"}:
            if (
                evidence_normalized in unverifiable_evidence
                or informational_section
                or not has_actionable_text
            ):
                status = "NOT VERIFIED"

        # Recommendations and guidelines must not be
        # represented as confirmed mandatory violations.
        mandatory_terms = (
            "must", "shall", "mandatory", "required",
            "prohibited", "shall not", "must not",
        )

        mandatory = any(
            term in requirement_text.casefold()
            for term in mandatory_terms
        )

        if status == "ISSUE" and not mandatory:
            status = "WARNING"

        source_url = (
            get_requirement_source_url(
                trusted_requirement
            )
        )

        validated.append(
            {
                "section_number": (
                    trusted_section
                ),
                "title": trusted_title,
                "status": status,
                "observed_evidence": (
                    observed_evidence
                ),
                "analysis": analysis,
                "recommendation": (
                    recommendation
                ),
                "source_url": source_url,
            }
        )

    return validated


def get_test_compliance_results(
    observations: list[dict[str, Any]],
    nea_requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Build mock compliance results from the REAL
    NEA requirements retrieved from the knowledge base.

    No AI provider request is made.

    Official source URLs are taken directly from
    the trusted NEA knowledge base.
    """

    results: list[
        dict[str, Any]
    ] = []

    statuses = [
        "PASS",
        "WARNING",
        "NOT VERIFIED",
        "PASS",
        "ISSUE",
    ]

    for index, requirement in enumerate(
        nea_requirements[:5]
    ):
        section_number = str(
            requirement.get(
                "section_number",
                "",
            )
        ).strip()

        title = str(
            requirement.get(
                "title",
                "NEA Requirement",
            )
        ).strip()

        if not section_number:
            continue

        source_url = (
            get_requirement_source_url(
                requirement
            )
        )

        status = statuses[
            index % len(statuses)
        ]

        if observations:
            observation = observations[
                index % len(observations)
            ]

            observed_evidence = str(
                observation.get(
                    "observation",
                    "Test-mode visual observation.",
                )
            ).strip()

        else:
            observed_evidence = (
                "No visual observation was "
                "available for this requirement."
            )

        if status == "PASS":
            analysis = (
                "Test mode: the visible design "
                "evidence is being treated as "
                "consistent with this retrieved "
                "NEA requirement."
            )

            recommendation = (
                "Maintain the current design "
                "approach and verify again in "
                "real AI mode."
            )

        elif status == "ISSUE":
            analysis = (
                "Test mode: this result simulates "
                "a visible conflict with the "
                "retrieved NEA requirement."
            )

            recommendation = (
                "Review this design element "
                "against the cited NEA requirement."
            )

        elif status == "WARNING":
            analysis = (
                "Test mode: the visual evidence "
                "suggests a possible concern but "
                "is not sufficient for a definite "
                "issue."
            )

            recommendation = (
                "Review the element manually and "
                "confirm it in real AI mode."
            )

        else:
            analysis = (
                "Test mode: this requirement "
                "cannot be reliably verified from "
                "the available visual evidence."
            )

            recommendation = (
                "Verify this requirement through "
                "implementation or runtime testing."
            )

        results.append(
            {
                "section_number": (
                    section_number
                ),
                "title": title,
                "status": status,
                "observed_evidence": (
                    observed_evidence
                ),
                "analysis": analysis,
                "recommendation": (
                    recommendation
                ),
                "source_url": source_url,
            }
        )

    return results
def analyze_design_compliance(
    observations: list[dict[str, Any]],
    nea_requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Compare visual design observations against
    retrieved Bahrain NEA requirements.

    TEST_MODE:
    Returns deterministic mock compliance results
    without calling an external AI provider.

    REAL AI MODE:
    Uses the centrally selected AI provider through
    generate_ai_text().
    """

    if not nea_requirements:
        return []

    # ---------------------------------------------------------
    # TEST MODE
    # ---------------------------------------------------------

    if settings.TEST_MODE:
        return get_test_compliance_results(
            observations=observations,
            nea_requirements=nea_requirements,
        )

    # ---------------------------------------------------------
    # REAL AI MODE
    # ---------------------------------------------------------

    prompt = build_compliance_prompt(
        observations=observations,
        nea_requirements=nea_requirements,
    )

    try:
        # -----------------------------------------------------
        # SELECTED AI PROVIDER
        # -----------------------------------------------------
        output_text = generate_ai_text(
            prompt
        )

        if not output_text:
            raise DesignComplianceError(
                "AI returned an empty "
                "compliance analysis."
            )

        cleaned = clean_json_response(
            output_text
        )

        parsed_raw: Any = json.loads(
            cleaned
        )

        if not isinstance(
            parsed_raw,
            dict,
        ):
            raise DesignComplianceError(
                "AI returned invalid "
                "compliance JSON."
            )

        parsed = cast(
            dict[str, Any],
            parsed_raw,
        )

        raw_results: Any = parsed.get(
            "results",
            [],
        )

        return validate_compliance_results(
            raw_results=raw_results,
            nea_requirements=nea_requirements,
        )

    except DesignComplianceError:
        raise

    except json.JSONDecodeError as exc:
        raise DesignComplianceError(
            "AI returned invalid JSON "
            "for compliance analysis."
        ) from exc

    except Exception as exc:
        raise DesignComplianceError(
            "AI design compliance analysis "
            f"failed: {str(exc)}"
        ) from exc
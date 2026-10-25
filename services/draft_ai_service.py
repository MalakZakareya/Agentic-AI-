import json
from typing import Any, cast

from core.config import settings
from services.ai_provider import generate_ai_text
from services.draft_service import (
    get_draft_sections,
    get_draft_type,
)


class DraftAIServiceError(Exception):
    pass


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


def group_requirements_by_topic(
    legal_requirements: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """
    Group retrieved Bahrain legal material
    by the legal topic assigned by the
    retrieval service.
    """

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for requirement in legal_requirements:
        topic = str(
            requirement.get(
                "legal_topic",
                "",
            )
        ).strip()

        if not topic:
            continue

        if topic not in grouped:
            grouped[topic] = []

        grouped[topic].append(
            requirement
        )

    return grouped


def prepare_legal_context(
    legal_requirements: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """
    Prepare a compact and trusted legal
    context for the AI.

    Only fields originating from the
    retrieved Bahrain knowledge base are
    included.
    """

    grouped = group_requirements_by_topic(
        legal_requirements
    )

    prepared: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for topic, requirements in grouped.items():
        prepared[topic] = []

        for requirement in requirements:
            prepared[topic].append(
                {
                    "regulation_id": str(
                        requirement.get(
                            "regulation_id",
                            requirement.get(
                                "id",
                                "",
                            ),
                        )
                    ).strip(),

                    "law_id": str(
                        requirement.get(
                            "law_id",
                            requirement.get(
                                "source_id",
                                "",
                            ),
                        )
                    ).strip(),

                    "law_title": str(
                        requirement.get(
                            "title",
                            "",
                        )
                    ).strip(),

                    "article_number": str(
                        requirement.get(
                            "article_number",
                            requirement.get(
                                "article",
                                "",
                            ),
                        )
                    ).strip(),

                    "article_text": str(
                        requirement.get(
                            "text",
                            "",
                        )
                    ).strip(),

                    "source_url": str(
                        requirement.get(
                            "source_url",
                            "",
                        )
                    ).strip(),

                    "consolidated_url": str(
                        requirement.get(
                            "consolidated_url",
                            "",
                        )
                    ).strip(),

                    "relevance_score": (
                        requirement.get(
                            "relevance_score",
                            0,
                        )
                    ),
                }
            )

    return prepared


def build_draft_prompt(
    draft_type: str,
    details: dict[str, Any],
    legal_requirements: list[dict[str, Any]],
) -> str:
    """
    Build the prompt for Real AI Mode.

    The AI receives:
    - user details
    - required document sections
    - Bahrain legal material grouped by topic
    """

    draft_config = get_draft_type(
        draft_type
    )

    sections = get_draft_sections(
        draft_type
    )

    legal_context = prepare_legal_context(
        legal_requirements
    )

    details_json = json.dumps(
        details,
        ensure_ascii=False,
        indent=2,
    )

    sections_json = json.dumps(
        sections,
        ensure_ascii=False,
        indent=2,
    )

    legal_json = json.dumps(
        legal_context,
        ensure_ascii=False,
        indent=2,
    )

    return f"""
You are creating a professional legal or business
document draft for use in the Kingdom of Bahrain.

DRAFT TYPE:

{draft_config["name"]}

USER-PROVIDED DETAILS:

{details_json}

REQUIRED DOCUMENT STRUCTURE:

{sections_json}

TRUSTED RETRIEVED BAHRAIN LEGAL MATERIAL,
GROUPED BY LEGAL TOPIC:

{legal_json}


IMPORTANT GROUNDING RULES:

1. Use the user-provided details accurately.

2. Never invent a person's name, company name,
   salary, date, duration, amount, address,
   obligation, or other factual detail.

3. Follow the REQUIRED DOCUMENT STRUCTURE.

4. Create a complete professional document,
   not merely a summary of the user details.

5. For each section that has a legal_topic,
   use only the retrieved legal material under
   that same legal topic when making a statement
   about Bahrain legal requirements.

6. You may draft normal contractual wording,
   but you must clearly distinguish contractual
   wording from a statement that Bahrain law
   specifically requires something.

7. Never invent a Bahrain law, decree, regulation,
   article number, authority, legal requirement,
   or source.

8. Never cite an article unless that exact article
   exists in the TRUSTED RETRIEVED BAHRAIN LEGAL
   MATERIAL above.

9. Do not change the meaning of a retrieved legal
   provision.

10. Do not claim that this document guarantees
    legal compliance.

11. If legal material is unavailable for a section,
    draft neutral contractual wording where
    appropriate, but do not describe that wording
    as a verified Bahrain legal requirement.

12. If important factual information is missing,
    use a clear placeholder such as:
    [TO BE COMPLETED]

13. Do not invent legal citations inside the
    document.

14. Keep the language professional, clear,
    consistent, and suitable for a formal document.

15. Avoid unnecessary repetition.

16. used_requirements must contain ONLY provisions
    that you actually relied upon when drafting
    the document.

17. Copy law_id and article_number EXACTLY from
    the trusted retrieved material.

18. If you did not rely upon any retrieved legal
    provision, return an empty used_requirements
    list.

19. Do not put Markdown code fences around the
    response.

20. Return valid JSON only.


RETURN EXACTLY THIS JSON STRUCTURE:

{{
  "title": "Professional document title",

  "draft": "Complete professional document text",

  "notes": [
    "Important drafting or verification note"
  ],

  "used_requirements": [
    {{
      "law_id": "exact law_id from retrieved material",
      "article_number": "exact article number from retrieved material"
    }}
  ]
}}
"""


def get_requirement_identifier(
    requirement: dict[str, Any],
) -> tuple[str, str]:
    """
    Return normalized law/article identifiers.
    """

    law_id = str(
        requirement.get(
            "law_id",
            requirement.get(
                "source_id",
                "",
            ),
        )
    ).strip()

    article_number = str(
        requirement.get(
            "article_number",
            requirement.get(
                "article",
                "",
            ),
        )
    ).strip()

    return (
        law_id,
        article_number,
    )


def get_test_used_requirements(
    legal_requirements: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """
    TEST MODE still uses REAL retrieved Bahrain
    legal identifiers.

    This allows the validation layer to be tested
    without making an AI provider request.
    """

    used_requirements: list[
        dict[str, str]
    ] = []

    seen: set[str] = set()

    for requirement in legal_requirements:
        law_id, article_number = (
            get_requirement_identifier(
                requirement
            )
        )

        if (
            not law_id
            or not article_number
        ):
            continue

        key = (
            law_id
            + "|"
            + article_number
        )

        if key in seen:
            continue

        seen.add(key)

        used_requirements.append(
            {
                "law_id": law_id,
                "article_number": (
                    article_number
                ),
            }
        )

    return used_requirements


def readable_field_name(
    field_name: str,
) -> str:
    return (
        field_name
        .replace("_", " ")
        .strip()
        .title()
    )


def get_detail(
    details: dict[str, Any],
    key: str,
    fallback: str = "[TO BE COMPLETED]",
) -> str:
    value = details.get(
        key,
        "",
    )

    cleaned = str(
        value
    ).strip()

    if cleaned:
        return cleaned

    return fallback
def build_test_section_content(
    section_key: str,
    section_title: str,
    details: dict[str, Any],
    topic_requirements: list[dict[str, Any]],
    draft_type: str = '',
) -> list[str]:
    """
    Build deterministic Test Mode content.

    This does NOT attempt to replace the real AI.
    It creates a structured document so the entire
    workflow, retrieval and validation pipeline can
    be tested without AI provider credits.
    """

    lines: list[str] = []

    if draft_type == "offer_letter" and section_key == "offer":
        employer = get_detail(details, "employer_name")
        employee = get_detail(details, "employee_name")

        lines.append(
            f"{employer} offers employment to {employee}, "
            "subject to the terms stated in this offer letter "
            "and the final employment documentation."
        )

    elif draft_type == "offer_letter" and section_key == "position":
        job_title = get_detail(details, "job_title")

        lines.append(
            f"The offered position is {job_title}."
        )

        lines.append(
            "The duties and reporting arrangements should "
            "be confirmed in the final employment documentation."
        )

    elif draft_type == "offer_letter" and section_key == "start_date":
        start_date = get_detail(details, "start_date")

        lines.append(
            f"The proposed employment start date is {start_date}."
        )

        lines.append(
            "Any change to the proposed start date should "
            "be confirmed in writing by the parties."
        )

    elif section_key == "parties":
        employer = get_detail(
            details,
            "employer_name",
        )

        employee = get_detail(
            details,
            "employee_name",
        )

        lines.append(
            "This document is made between "
            f"{employer} (the Employer) and "
            f"{employee} (the Employee)."
        )

    elif section_key in {
        "appointment",
        "appointment_and_job_duties",
    }:
        employee = get_detail(
            details,
            "employee_name",
        )

        job_title = get_detail(
            details,
            "job_title",
        )

        lines.append(
            f"{employee} is appointed in the "
            f"position of {job_title}."
        )

        lines.append(
            "The Employee shall perform the duties "
            "reasonably associated with the agreed "
            "position and any documented duties "
            "agreed between the parties."
        )

    elif section_key in {
        "term",
        "term_and_commencement",
    }:
        start_date = get_detail(
            details,
            "start_date",
        )

        duration = get_detail(
            details,
            "contract_duration",
        )

        lines.append(
            "The employment shall commence on "
            f"{start_date}."
        )

        lines.append(
            "The stated contract duration is "
            f"{duration}."
        )

    elif section_key in {
        "probation",
        "probation_period",
    }:
        lines.append(
            "Any probation arrangement shall be "
            "recorded expressly in the final "
            "agreement and shall be applied only "
            "to the extent supported by the "
            "applicable verified legal provisions."
        )

    elif section_key in {
        "salary",
        "salary_and_payment",
        "compensation",
    }:
        salary = get_detail(
            details,
            "salary",
        )

        lines.append(
            "The agreed salary is "
            f"{salary}."
        )

        lines.append(
            "The payment method and payment date "
            "should be recorded clearly in the "
            "final signed document."
        )

    elif section_key in {
        "working_hours",
        "working_hours_and_rest_periods",
    }:
        lines.append(
            "Working hours, rest periods and any "
            "applicable overtime arrangements "
            "shall be recorded and administered "
            "in accordance with the agreed terms "
            "and the verified legal provisions "
            "applicable to this section."
        )

    elif section_key in {
        "annual_leave",
        "leave",
    }:
        lines.append(
            "Annual leave entitlement and its "
            "administration shall be handled in "
            "accordance with the applicable "
            "verified legal provisions and any "
            "more favourable agreed terms."
        )

    elif section_key == "sick_leave":
        lines.append(
            "Sick leave shall be administered in "
            "accordance with the applicable "
            "verified legal provisions and the "
            "Employer's lawful procedures."
        )

    elif section_key in {
        "confidentiality",
        "confidentiality_and_data_protection",
        "data_protection",
    }:
        lines.append(
            "The parties shall protect confidential "
            "information and personal data handled "
            "in connection with this document, "
            "subject to the applicable verified "
            "legal provisions."
        )

    elif section_key in {
        "termination",
        "termination_and_notice",
    }:
        lines.append(
            "Termination and any applicable notice "
            "requirements shall be handled in "
            "accordance with the agreed terms and "
            "the applicable verified legal "
            "provisions."
        )

    elif section_key in {
        "end_of_service",
        "end_of_service_rights",
    }:
        lines.append(
            "Any end-of-service rights shall be "
            "determined using the applicable "
            "verified legal provisions and the "
            "facts existing at the end of the "
            "relationship."
        )

    elif section_key in {
        "governing_law",
        "applicable_law",
    }:
        lines.append(
            "This document is intended for use in "
            "the Kingdom of Bahrain and is subject "
            "to applicable Bahrain law."
        )

    elif section_key in {
        "signatures",
        "signature",
    }:
        if draft_type == "employment_contract":
            parties = [
                ("Employer", details.get("employer_name", "")),
                ("Employee", details.get("employee_name", "")),
            ]
        elif draft_type in {"nda", "service_agreement"}:
            parties = [
                ("First Party", details.get("first_party", "")),
                ("Second Party", details.get("second_party", "")),
            ]
        else:
            parties = []

        for index, (label, name) in enumerate(parties):
            if index:
                lines.append("")

            lines.extend(
                [
                    f"{label}:",
                    f"Name: {str(name).strip() or '____________________'}",
                    "Signature: ____________________",
                    "Date: ________________________",
                ]
            )

    elif section_key == "acceptance":
        if draft_type == "offer_letter":
            lines.extend(
                [
                    "Employee Acceptance:",
                    "Name: " + str(
                        details.get("employee_name", "")
                    ).strip(),
                    "Signature: ____________________",
                    "Date: ________________________",
                ]
            )

    elif section_key == "acknowledgement":
        if draft_type == "warning_letter":
            lines.extend(
                [
                    "Employee Acknowledgement of Receipt:",
                    "Name: " + str(
                        details.get("employee_name", "")
                    ).strip(),
                    "Signature: ____________________",
                    "Date: ________________________",
                    "Acknowledgement confirms receipt only; "
                    "it does not necessarily indicate agreement "
                    "with the contents.",
                ]
            )

    else:
        lines.append(
            f"This section ({section_title}) shall "
            "contain the terms agreed by the "
            "parties based on the information "
            "provided."
        )

    if topic_requirements:
        unique_articles: list[str] = []
        seen_articles: set[str] = set()

        for requirement in topic_requirements:
            law_id, article_number = (
                get_requirement_identifier(
                    requirement
                )
            )

            if (
                not law_id
                or not article_number
            ):
                continue

            reference = (
                law_id
                + " — Article "
                + article_number
            )

            if reference in seen_articles:
                continue

            seen_articles.add(
                reference
            )

            unique_articles.append(
                reference
            )

        if unique_articles:
            lines.append("")

            lines.append(
                "Verified legal material retrieved "
                "for this section:"
            )

            for reference in unique_articles:
                lines.append(
                    "- " + reference
                )

    return lines


def get_test_draft(
    draft_type: str,
    details: dict[str, Any],
    legal_requirements: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Generate a structured deterministic document
    in TEST_MODE.

    Real user details and real retrieved Bahrain
    legal references are used.

    No AI provider request is made.
    """

    draft_config = get_draft_type(
        draft_type
    )

    sections = get_draft_sections(
        draft_type
    )

    grouped_requirements = (
        group_requirements_by_topic(
            legal_requirements
        )
    )

    title = draft_config["name"]

    lines: list[str] = [
        title.upper(),
        "",
    ]

    if sections:
        section_number = 1

        for section in sections:
            section_key = str(
                section.get(
                    "key",
                    "",
                )
            ).strip()

            section_title = str(
                section.get(
                    "title",
                    "",
                )
            ).strip()

            legal_topic_raw = (
                section.get(
                    "legal_topic"
                )
            )

            legal_topic = (
                str(legal_topic_raw).strip()
                if legal_topic_raw
                else ""
            )

            if not section_title:
                continue

            lines.append(
                f"{section_number}. "
                f"{section_title.upper()}"
            )

            lines.append(
                "-" * (
                    len(section_title)
                    + len(
                        str(section_number)
                    )
                    + 2
                )
            )

            topic_requirements = (
                grouped_requirements.get(
                    legal_topic,
                    [],
                )
                if legal_topic
                else []
            )

            section_lines = (
                build_test_section_content(
                    draft_type=draft_type,
                    section_key=section_key,
                    section_title=section_title,
                    details=details,
                    topic_requirements=(
                        topic_requirements
                    ),
                )
            )

            lines.extend(
                section_lines
            )

            lines.append("")
            section_number += 1

    else:
        lines.append(
            "DOCUMENT DETAILS"
        )

        lines.append(
            "----------------"
        )

        for field_name, value in details.items():
            lines.append(
                readable_field_name(
                    field_name
                )
                + ": "
                + str(value)
            )

    draft_text = "\n".join(
        lines
    ).strip()

    used_requirements = (
        get_test_used_requirements(
            legal_requirements
        )
    )

    notes = [
        (
            "TEST MODE is enabled. "
            "No AI provider was called."
        ),
        (
            "The document structure, submitted "
            "details, legal retrieval and legal "
            "reference validation can be tested "
            "in this mode."
        ),
        (
            "Test Mode uses deterministic template "
            "wording and should not be treated as "
            "a final legal document."
        ),
    ]

    if not legal_requirements:
        notes.append(
            "No Bahrain legal material was "
            "retrieved for this draft."
        )

    return {
        "title": title,
        "draft": draft_text,
        "notes": notes,
        "used_requirements": (
            used_requirements
        ),
    }
def normalize_ai_used_requirements(
    used_raw: Any,
) -> list[dict[str, str]]:
    """
    Normalize references returned by the AI provider.

    Final trust validation is performed later
    by draft_validation_service.py.
    """

    used_requirements: list[
        dict[str, str]
    ] = []

    if not isinstance(
        used_raw,
        list,
    ):
        return used_requirements

    seen: set[str] = set()

    for item in cast(
        list[Any],
        used_raw,
    ):
        if not isinstance(
            item,
            dict,
        ):
            continue

        requirement = cast(
            dict[str, Any],
            item,
        )

        law_id = str(
            requirement.get(
                "law_id",
                "",
            )
        ).strip()

        article_number = str(
            requirement.get(
                "article_number",
                "",
            )
        ).strip()

        if (
            not law_id
            or not article_number
        ):
            continue

        key = (
            law_id
            + "|"
            + article_number
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        used_requirements.append(
            {
                "law_id": law_id,
                "article_number": (
                    article_number
                ),
            }
        )

    return used_requirements


def normalize_notes(
    notes_raw: Any,
) -> list[str]:
    notes: list[str] = []

    if not isinstance(
        notes_raw,
        list,
    ):
        return notes

    for item in cast(
        list[Any],
        notes_raw,
    ):
        if not isinstance(
            item,
            str,
        ):
            continue

        cleaned = item.strip()

        if cleaned:
            notes.append(
                cleaned
            )

    return notes


def generate_draft(
    draft_type: str,
    details: dict[str, Any],
    legal_requirements: list[dict[str, Any]],
) -> dict[str, Any]:

    # =========================================================
    # TEST MODE
    # =========================================================

    if settings.TEST_MODE:
        return get_test_draft(
            draft_type=draft_type,
            details=details,
            legal_requirements=(
                legal_requirements
            ),
        )

    # =========================================================
    # REAL AI MODE
    # =========================================================

    prompt = build_draft_prompt(
        draft_type=draft_type,
        details=details,
        legal_requirements=(
            legal_requirements
        ),
    )

    try:
        output_text = generate_ai_text(
            prompt
        )

        if not output_text:
            raise DraftAIServiceError(
                "AI returned an empty draft."
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
            raise DraftAIServiceError(
                "AI returned an invalid draft."
            )

        parsed = cast(
            dict[str, Any],
            parsed_raw,
        )

        title = str(
            parsed.get(
                "title",
                "",
            )
        ).strip()

        draft = str(
            parsed.get(
                "draft",
                "",
            )
        ).strip()

        if not title:
            raise DraftAIServiceError(
                "AI draft has no title."
            )

        if not draft:
            raise DraftAIServiceError(
                "AI draft has no content."
            )

        notes = normalize_notes(
            parsed.get(
                "notes",
                [],
            )
        )

        used_requirements = (
            normalize_ai_used_requirements(
                parsed.get(
                    "used_requirements",
                    [],
                )
            )
        )

        return {
            "title": title,
            "draft": draft,
            "notes": notes,
            "used_requirements": (
                used_requirements
            ),
        }

    except DraftAIServiceError:
        raise

    except json.JSONDecodeError as exc:
        raise DraftAIServiceError(
            "AI returned invalid JSON."
        ) from exc

    except Exception as exc:
        raise DraftAIServiceError(
            "AI draft generation failed: "
            f"{str(exc)}"
        ) from exc
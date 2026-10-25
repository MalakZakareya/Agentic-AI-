from typing import Any, cast


class DraftValidationError(Exception):
    pass


def build_requirement_key(
    law_id: str,
    article_number: str,
) -> str:
    """
    Build the canonical validation key used
    to match AI-reported legal references
    against trusted retrieved requirements.
    """

    return (
        law_id.strip()
        + "|"
        + article_number.strip()
    )


def build_requirement_lookup(
    legal_requirements: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Build a trusted lookup using only legal
    provisions retrieved from the local
    Bahrain knowledge base.
    """

    lookup: dict[
        str,
        dict[str, Any]
    ] = {}

    for requirement in legal_requirements:

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

        if (
            not law_id
            or not article_number
        ):
            continue

        key = build_requirement_key(
            law_id=law_id,
            article_number=article_number,
        )

        # Preserve the first trusted occurrence.
        # The same article may appear under multiple
        # search queries or legal topics.
        if key not in lookup:
            lookup[key] = requirement

    return lookup


def normalize_used_requirements(
    used_raw: Any,
) -> list[dict[str, str]]:
    """
    Safely normalize the legal references
    returned by the AI.
    """

    normalized: list[
        dict[str, str]
    ] = []

    if not isinstance(
        used_raw,
        list,
    ):
        return normalized

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

        key = build_requirement_key(
            law_id=law_id,
            article_number=article_number,
        )

        if key in seen:
            continue

        seen.add(key)

        normalized.append(
            {
                "law_id": law_id,
                "article_number": (
                    article_number
                ),
            }
        )

    return normalized


def validate_used_requirements(
    used_requirements: list[dict[str, str]],
    legal_requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Accept only legal provisions that exist
    in the trusted retrieved Bahrain legal
    material.

    Any AI-invented law or article reference
    is silently rejected.
    """

    trusted_lookup = (
        build_requirement_lookup(
            legal_requirements
        )
    )

    validated: list[
        dict[str, Any]
    ] = []

    seen: set[str] = set()

    for used in used_requirements:

        law_id = str(
            used.get(
                "law_id",
                "",
            )
        ).strip()

        article_number = str(
            used.get(
                "article_number",
                "",
            )
        ).strip()

        if (
            not law_id
            or not article_number
        ):
            continue

        key = build_requirement_key(
            law_id=law_id,
            article_number=article_number,
        )

        if key in seen:
            continue

        trusted_requirement = (
            trusted_lookup.get(
                key
            )
        )

        if trusted_requirement is None:
            # The AI referenced something
            # outside the trusted retrieval.
            continue

        seen.add(
            key
        )

        verified = dict(
            trusted_requirement
        )

        # -----------------------------------------
        # Normalize identifiers for frontend/API.
        # -----------------------------------------

        verified[
            "law_id"
        ] = law_id

        verified[
            "article_number"
        ] = article_number

        verified[
            "regulation_id"
        ] = str(
            trusted_requirement.get(
                "regulation_id",
                trusted_requirement.get(
                    "id",
                    "",
                ),
            )
        ).strip()

        verified[
            "legal_topic"
        ] = str(
            trusted_requirement.get(
                "legal_topic",
                "",
            )
        ).strip()

        verified[
            "legal_topic_name"
        ] = str(
            trusted_requirement.get(
                "legal_topic_name",
                "",
            )
        ).strip()

        verified[
            "source_url"
        ] = str(
            trusted_requirement.get(
                "source_url",
                "",
            )
        ).strip()

        verified[
            "consolidated_url"
        ] = str(
            trusted_requirement.get(
                "consolidated_url",
                "",
            )
        ).strip()

        verified["verification_status"] = "HUMAN_REVIEW_REQUIRED"
        verified["reference_match_status"] = "REFERENCE_MATCHED"
        verified["legal_currency_verified"] = False

        validated.append(
            verified
        )

    return validated


def collect_unverified_references(
    used_requirements: list[dict[str, str]],
    legal_requirements: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """
    Detect references returned by the AI
    that were not present in the trusted
    retrieved legal material.

    These references are never treated as
    verified legal sources.
    """

    trusted_lookup = (
        build_requirement_lookup(
            legal_requirements
        )
    )

    unverified: list[
        dict[str, str]
    ] = []

    seen: set[str] = set()

    for used in used_requirements:

        law_id = str(
            used.get(
                "law_id",
                "",
            )
        ).strip()

        article_number = str(
            used.get(
                "article_number",
                "",
            )
        ).strip()

        if (
            not law_id
            or not article_number
        ):
            continue

        key = build_requirement_key(
            law_id=law_id,
            article_number=article_number,
        )

        if (
            key in trusted_lookup
            or key in seen
        ):
            continue

        seen.add(
            key
        )

        unverified.append(
            {
                "law_id": law_id,
                "article_number": (
                    article_number
                ),
            }
        )

    return unverified


def validate_generated_draft(
    ai_result: dict[str, Any],
    legal_requirements: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Validate the generated document and
    every legal reference reported by the AI.
    """

    title = str(
        ai_result.get(
            "title",
            "",
        )
    ).strip()

    draft = str(
        ai_result.get(
            "draft",
            "",
        )
    ).strip()

    if not title:
        raise DraftValidationError(
            "Generated draft has no title."
        )

    if not draft:
        raise DraftValidationError(
            "Generated draft has no content."
        )

    # ---------------------------------------------
    # Notes
    # ---------------------------------------------

    notes_raw: Any = (
        ai_result.get(
            "notes",
            [],
        )
    )

    notes: list[str] = []

    if isinstance(
        notes_raw,
        list,
    ):
        for item in cast(
            list[Any],
            notes_raw,
        ):

            if not isinstance(
                item,
                str,
            ):
                continue

            cleaned_note = (
                item.strip()
            )

            if cleaned_note:
                notes.append(
                    cleaned_note
                )

    # ---------------------------------------------
    # AI-reported legal references
    # ---------------------------------------------

    used_requirements = (
        normalize_used_requirements(
            ai_result.get(
                "used_requirements",
                [],
            )
        )
    )

    # ---------------------------------------------
    # Verify against trusted retrieval
    # ---------------------------------------------

    verified_sources = (
        validate_used_requirements(
            used_requirements=(
                used_requirements
            ),
            legal_requirements=(
                legal_requirements
            ),
        )
    )

    unverified_references = (
        collect_unverified_references(
            used_requirements=(
                used_requirements
            ),
            legal_requirements=(
                legal_requirements
            ),
        )
    )

    # ---------------------------------------------
    # Never silently accept invented references.
    # ---------------------------------------------

    if unverified_references:

        rejected_text = ", ".join(
            (
                item["law_id"]
                + " Article "
                + item["article_number"]
            )
            for item
            in unverified_references
        )

        notes.append(
            "The following AI-reported legal "
            "references were not verified against "
            "the retrieved Bahrain legal material "
            "and were rejected: "
            + rejected_text
        )

    # ---------------------------------------------
    # Legal coverage summary
    # ---------------------------------------------

    verified_topics: list[str] = []

    for source in verified_sources:

        topic = str(
            source.get(
                "legal_topic",
                "",
            )
        ).strip()

        if (
            topic
            and topic
            not in verified_topics
        ):
            verified_topics.append(
                topic
            )


    # Require human review when legal research
    # cannot confirm that sources are current.
    agent_requires_review = any(
        isinstance(item.get("legal_research_agent"), dict)
        and (
            item["legal_research_agent"].get("decision") != "PROCEED"
            or item["legal_research_agent"].get("evidence_status")
            != "VERIFIED_CURRENT"
        )
        for item in legal_requirements
    )

    if agent_requires_review:
        notes.append(
            "Human legal review required: retrieved legal "
            "sources have not been confirmed as currently "
            "in force."
        )

    return {
        "title": title,
        "draft": draft,
        "notes": notes,

        "verified_sources": (
            verified_sources
        ),

        "verified_source_count": (
            len(
                verified_sources
            )
        ),

        "verified_legal_topics": (
            verified_topics
        ),

        "unverified_references": (
            unverified_references
        ),

        "legal_validation": {
            "status": (
                "NOT_VERIFIED"
            ),
            "verified_sources": len(
                verified_sources
            ),
            "rejected_references": len(
                unverified_references
            ),
            "legal_currency_verified": False,
            "human_review_required": True,
            "matched_reference_count": len(verified_sources),
            "legally_verified_source_count": 0,
        },
    }
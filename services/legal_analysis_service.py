import json
from typing import Any, cast

from core.config import settings
from services.ai_provider import generate_ai_text
from services.legal_retriever import search_regulations


ALLOWED_STATUSES = {
    "PASS",
    "ISSUE",
    "WARNING",
    "NOT VERIFIED",
}


# ---------------------------------------------------------
# Batch configuration
# ---------------------------------------------------------

LEGAL_BATCH_SIZE = 8


# ---------------------------------------------------------
# Point-specific legal search expansion
# ---------------------------------------------------------

POINT_SEARCH_QUERIES: dict[str, list[str]] = {
    "employment": [
        "employment contract",
        "employment relationship",
        "عقد العمل",
        "عقد العمل الفردي",
        "بيانات عقد العمل",
    ],
    "salary": [
        "salary wages payment",
        "wages salary payment",
        "الأجر",
        "الأجور",
        "أداء الأجور",
    ],
    "working_hours": [
        "working hours",
        "rest periods",
        "overtime work",
        "ساعات العمل",
        "فترات الراحة",
        "العمل الإضافي",
    ],
    "annual_leave": [
        "annual leave",
        "annual holiday",
        "الإجازة السنوية",
        "الإجازات السنوية",
    ],
    "sick_leave": [
        "sick leave",
        "الإجازة المرضية",
    ],
    "termination": [
        "termination employment",
        "notice period",
        "termination notice",
        "إنهاء عقد العمل",
        "إنهاء العقد",
        "مهلة الإخطار",
    ],
    "probation": [
        "probation period",
        "employment probation",
        "فترة التجربة",
        "شرط التجربة",
    ],
    "confidentiality": [
        "confidentiality personal data",
        "employee personal data",
        "سرية البيانات",
        "البيانات الشخصية",
    ],
}


def normalize_lookup_text(
    value: str,
) -> str:
    """
    Light normalization used only for determining
    the type of document point.

    This does not change stored law text.
    """

    return (
        value
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )


def detect_point_search_group(
    point: dict[str, Any],
) -> str:
    """
    Determine which legal-search group best matches
    the extracted document point.
    """

    title = normalize_lookup_text(
        str(
            point.get(
                "title",
                "",
            )
        )
    )

    category = normalize_lookup_text(
        str(
            point.get(
                "category",
                "",
            )
        )
    )

    combined = (
        title
        + " "
        + category
    ).strip()

    if (
        "employment relationship" in combined
        or "employment contract" in combined
        or "employment" == category
        or "عقد العمل" in combined
    ):
        return "employment"

    if (
        "salary" in combined
        or "wage" in combined
        or "compensation" in combined
        or "أجر" in combined
        or "راتب" in combined
    ):
        return "salary"

    if (
        "working hour" in combined
        or "overtime" in combined
        or "working hours" in category
        or "ساعات العمل" in combined
        or "عمل إضافي" in combined
    ):
        return "working_hours"

    if (
        "annual leave" in combined
        or "annual holiday" in combined
        or "إجازة سنوية" in combined
        or "الاجازة السنوية" in combined
    ):
        return "annual_leave"

    if (
        "sick leave" in combined
        or "إجازة مرضية" in combined
        or "الاجازة المرضية" in combined
    ):
        return "sick_leave"

    if (
        "termination" in combined
        or "notice" in combined
        or "إنهاء" in combined
        or "اخطار" in combined
        or "إخطار" in combined
    ):
        return "termination"

    if (
        "probation" in combined
        or "فترة التجربة" in combined
        or "شرط التجربة" in combined
    ):
        return "probation"

    if (
        "confidential" in combined
        or "personal data" in combined
        or "data protection" in combined
        or "سرية" in combined
        or "بيانات شخصية" in combined
    ):
        return "confidentiality"

    return ""


def build_regulation_key(
    regulation: dict[str, Any],
) -> str:
    """
    Build a stable key for deduplicating retrieved
    legal provisions.
    """

    regulation_id = str(
        regulation.get(
            "id",
            "",
        )
    ).strip()

    if regulation_id:
        return regulation_id

    source_id = str(
        regulation.get(
            "source_id",
            "",
        )
    ).strip()

    article = str(
        regulation.get(
            "article",
            "",
        )
    ).strip()

    title = str(
        regulation.get(
            "title",
            "",
        )
    ).strip()

    return (
        source_id
        + "|"
        + article
        + "|"
        + title
    )


def get_regulation_score(
    regulation: dict[str, Any],
) -> int:
    """
    Safely read retriever relevance score.
    """

    value: Any = regulation.get(
        "relevance_score",
        0,
    )

    try:
        return int(
            str(value)
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0


def point_mentions_juvenile(
    point: dict[str, Any],
) -> bool:
    """
    Check whether the document point itself is
    specifically about juvenile employment.
    """

    point_text = " ".join(
        [
            str(
                point.get(
                    "title",
                    "",
                )
            ),
            str(
                point.get(
                    "category",
                    "",
                )
            ),
            str(
                point.get(
                    "original_text",
                    "",
                )
            ),
            str(
                point.get(
                    "explanation",
                    "",
                )
            ),
        ]
    ).lower()

    markers = [
        "juvenile",
        "minor worker",
        "young worker",
        "حدث",
        "الأحداث",
        "الاحداث",
    ]

    return any(
        marker in point_text
        for marker in markers
    )


def regulation_is_juvenile_specific(
    regulation: dict[str, Any],
) -> bool:
    """
    Detect provisions whose text is specifically
    scoped to juvenile workers.

    This is intentionally based on the provision
    text rather than hardcoding an article number.
    """

    text = " ".join(
        [
            str(
                regulation.get(
                    "title",
                    "",
                )
            ),
            str(
                regulation.get(
                    "text",
                    "",
                )
            ),
        ]
    ).lower()

    markers = [
        "juvenile",
        "juveniles",
        "minor worker",
        "young worker",
        "الحدث",
        "الأحداث",
        "الاحداث",
    ]

    return any(
        marker in text
        for marker in markers
    )


def regulation_is_applicable_to_point(
    point: dict[str, Any],
    regulation: dict[str, Any],
) -> bool:
    """
    Remove clearly special-scope provisions from
    generic document points.

    At present this protects generic employment
    analysis from juvenile-specific provisions.

    If the document point itself mentions juvenile
    employment, those provisions remain eligible.
    """

    if point_mentions_juvenile(
        point
    ):
        return True

    if regulation_is_juvenile_specific(
        regulation
    ):
        return False

    return True


def build_point_search_queries(
    point: dict[str, Any],
) -> list[str]:
    """
    Build a set of legal search queries for one
    document point.

    The original document wording is always kept.
    Topic-specific bilingual legal queries are added
    only when the point type can be identified.
    """

    title = str(
        point.get(
            "title",
            "",
        )
    ).strip()

    category = str(
        point.get(
            "category",
            "",
        )
    ).strip()

    original_text = str(
        point.get(
            "original_text",
            "",
        )
    ).strip()

    explanation = str(
        point.get(
            "explanation",
            "",
        )
    ).strip()

    original_query = " ".join(
        part
        for part in [
            title,
            category,
            original_text,
            explanation,
        ]
        if part
    ).strip()

    queries: list[str] = []

    if original_query:
        queries.append(
            original_query
        )

    search_group = (
        detect_point_search_group(
            point
        )
    )

    if search_group:
        expanded_queries = (
            POINT_SEARCH_QUERIES.get(
                search_group,
                [],
            )
        )

        for query in expanded_queries:
            clean_query = str(
                query
            ).strip()

            if (
                clean_query
                and clean_query
                not in queries
            ):
                queries.append(
                    clean_query
                )

    return queries


def retrieve_laws_for_point(
    point: dict[str, Any],
    limit: int = 5,
) -> dict[str, Any]:
    """
    Find relevant Bahrain regulations for one
    extracted document point.

    Multiple bilingual legal queries may be used
    for better retrieval accuracy.

    This step works locally and does not call AI.
    """

    queries = build_point_search_queries(
        point
    )

    if not queries:
        return {
            "point": point,
            "search_query": "",
            "search_queries": [],
            "regulations": [],
        }

    internal_limit = max(
        limit * 3,
        10,
    )

    candidates: dict[
        str,
        dict[str, Any],
    ] = {}

    for query in queries:
        matches = search_regulations(
            query=query,
            limit=internal_limit,
        )

        for match in matches:
            if not regulation_is_applicable_to_point(
                point=point,
                regulation=match,
            ):
                continue

            key = build_regulation_key(
                match
            )

            if not key:
                continue

            existing = candidates.get(
                key
            )

            if existing is None:
                candidate = {
                    **match
                }

                candidate[
                    "analysis_matched_queries"
                ] = [
                    query
                ]

                candidate[
                    "analysis_best_score"
                ] = get_regulation_score(
                    match
                )

                candidates[
                    key
                ] = candidate

                continue

            existing_queries_value: Any = (
                existing.get(
                    "analysis_matched_queries",
                    [],
                )
            )

            existing_queries: list[str] = []

            if isinstance(
                existing_queries_value,
                list,
            ):
                typed_queries = cast(
                    list[Any],
                    existing_queries_value,
                )

                for item in typed_queries:
                    item_text = str(
                        item
                    ).strip()

                    if (
                        item_text
                        and item_text
                        not in existing_queries
                    ):
                        existing_queries.append(
                            item_text
                        )

            if query not in existing_queries:
                existing_queries.append(
                    query
                )

            existing[
                "analysis_matched_queries"
            ] = existing_queries

            current_best_value: Any = (
                existing.get(
                    "analysis_best_score",
                    0,
                )
            )

            try:
                current_best = int(
                    str(
                        current_best_value
                    )
                )
            except (
                TypeError,
                ValueError,
            ):
                current_best = 0

            new_score = get_regulation_score(
                match
            )

            if new_score > current_best:
                existing[
                    "analysis_best_score"
                ] = new_score

    ranked_candidates = sorted(
        candidates.values(),
        key=lambda item: int(
            str(
                item.get(
                    "analysis_best_score",
                    0,
                )
            )
        ),
        reverse=True,
    )

    selected_regulations = (
        ranked_candidates[:limit]
    )


    return {
        "point": point,
        "search_query": (
            queries[0]
            if queries
            else ""
        ),
        "search_queries": queries,
        "regulations": selected_regulations,
    }


def retrieve_laws_for_points(
    points: list[dict[str, Any]],
    limit_per_point: int = 5,
) -> list[dict[str, Any]]:
    """
    Retrieve Bahrain regulations for all extracted
    document points.
    """

    results: list[
        dict[str, Any]
    ] = []

    for point in points:
        results.append(
            retrieve_laws_for_point(
                point=point,
                limit=limit_per_point,
            )
        )

    from core_agents.graph import evidence_check_agent

    for item in results:
        regulations = item.get("regulations", [])

        agent_result = evidence_check_agent({
            "query": item.get("search_query", ""),
            "evidence": regulations,
            "search_attempts": 2,
        })

        item["legal_research_agent"] = {
            "decision": agent_result.get("decision"),
            "evidence_status": agent_result.get("evidence_status"),
        }

    return results


def get_not_verified_analysis() -> dict[str, Any]:
    """
    Default result when no trustworthy legal
    verification can be made.
    """

    return {
        "status": "NOT VERIFIED",
        "explanation": (
            "The available Bahrain legal material "
            "was not sufficient to verify this "
            "document point."
        ),
        "relevant_articles": [],
        "recommendation": (
            "Review this point manually against "
            "the applicable Bahrain legal "
            "requirements."
        ),
    }


def get_test_legal_analysis(
    legal_sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Return deterministic mock legal analysis while
    TEST_MODE is enabled.

    The legal sources themselves are still real
    retrieved Bahrain knowledge-base sources.
    """

    if not legal_sources:
        return get_not_verified_analysis()

    first_source = legal_sources[0]

    return {
        "status": "PASS",
        "explanation": (
            "TEST MODE: the document point was "
            "successfully connected to retrieved "
            "Bahrain legal material. No external "
            "AI provider was called."
        ),
        "relevant_articles": [
            {
                "law_number": str(
                    first_source.get(
                        "law_number",
                        "",
                    )
                ).strip(),
                "year": str(
                    first_source.get(
                        "year",
                        "",
                    )
                ).strip(),
                "article": str(
                    first_source.get(
                        "article",
                        "",
                    )
                ).strip(),
                "source_url": str(
                    first_source.get(
                        "source_url",
                        "",
                    )
                ).strip(),
                "reason": (
                    "TEST MODE: this retrieved "
                    "article is being used to "
                    "confirm that the legal "
                    "analysis workflow is working."
                ),
            }
        ],
        "recommendation": (
            "Run the workflow in real AI mode "
            "for an actual legal comparison."
        ),
    }


def clean_json_response(
    result_text: str,
) -> str:
    """
    Remove common Markdown JSON fences.
    """

    cleaned = result_text.strip()

    if cleaned.startswith(
        "```json"
    ):
        cleaned = cleaned[7:]

    elif cleaned.startswith(
        "```"
    ):
        cleaned = cleaned[3:]

    if cleaned.endswith(
        "```"
    ):
        cleaned = cleaned[:-3]

    return cleaned.strip()


def build_legal_source(
    regulation: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert a retrieved regulation into a trusted
    source object used by the legal-analysis layer.
    """

    return {
        "regulation_id": str(
            regulation.get(
                "id",
                "",
            )
        ).strip(),
        "law_number": str(
            regulation.get(
                "law_number",
                "",
            )
        ).strip(),
        "year": str(
            regulation.get(
                "year",
                "",
            )
        ).strip(),
        "article": str(
            regulation.get(
                "article",
                "",
            )
        ).strip(),
        "title": str(
            regulation.get(
                "title",
                "",
            )
        ).strip(),
        "text": str(
            regulation.get(
                "text",
                "",
            )
        ).strip(),
        "source_url": str(
            regulation.get(
                "source_url",
                "",
            )
        ).strip(),
        "effective_status": str(
            regulation.get(
                "effective_status",
                "unverified",
            )
        ).strip() or "unverified",
    }



def build_legal_sources(
    regulations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Build trusted legal source objects.
    """

    sources: list[
        dict[str, Any]
    ] = []

    seen: set[str] = set()

    for regulation in regulations:
        source = build_legal_source(
            regulation
        )

        source_key = (
            str(
                source.get(
                    "regulation_id",
                    "",
                )
            )
            + "|"
            + str(
                source.get(
                    "article",
                    "",
                )
            )
        )

        if source_key in seen:
            continue

        seen.add(
            source_key
        )

        sources.append(
            source
        )

    return sources


def build_legal_source_key(
    source: dict[str, Any],
) -> str:
    """
    Build a stable trusted-source key.
    """

    regulation_id = str(
        source.get(
            "regulation_id",
            "",
        )
    ).strip()

    article = str(
        source.get(
            "article",
            "",
        )
    ).strip()

    if regulation_id:
        return (
            regulation_id
            + "|"
            + article
        )

    law_number = str(
        source.get(
            "law_number",
            "",
        )
    ).strip()

    year = str(
        source.get(
            "year",
            "",
        )
    ).strip()

    return (
        law_number
        + "|"
        + year
        + "|"
        + article
    )


def build_ai_article_key(
    article: dict[str, Any],
) -> str:
    """
    Build the lookup key from an AI-returned article.
    """

    law_number = str(
        article.get(
            "law_number",
            "",
        )
    ).strip()

    year = str(
        article.get(
            "year",
            "",
        )
    ).strip()

    article_number = str(
        article.get(
            "article",
            "",
        )
    ).strip()

    return (
        law_number
        + "|"
        + year
        + "|"
        + article_number
    )


def find_trusted_legal_source(
    ai_article: dict[str, Any],
    legal_sources: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Match an AI-returned citation against the
    trusted retrieved Bahrain legal sources.

    AI is not allowed to create new citations.
    """

    ai_law_number = str(
        ai_article.get(
            "law_number",
            "",
        )
    ).strip()

    ai_year = str(
        ai_article.get(
            "year",
            "",
        )
    ).strip()

    ai_article_number = str(
        ai_article.get(
            "article",
            "",
        )
    ).strip()

    for source in legal_sources:
        source_law_number = str(
            source.get(
                "law_number",
                "",
            )
        ).strip()

        source_year = str(
            source.get(
                "year",
                "",
            )
        ).strip()

        source_article = str(
            source.get(
                "article",
                "",
            )
        ).strip()

        if (
            ai_law_number
            == source_law_number
            and ai_year
            == source_year
            and ai_article_number
            == source_article
        ):
            return source

    return None


def validate_relevant_articles(
    raw_articles: Any,
    legal_sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Validate AI-returned legal citations against
    trusted retrieved sources.

    The source URL is always restored from the
    trusted knowledge base, never trusted from AI.
    """

    if not isinstance(
        raw_articles,
        list,
    ):
        return []

    validated: list[
        dict[str, Any]
    ] = []

    seen: set[str] = set()

    for raw_article in cast(
        list[Any],
        raw_articles,
    ):
        if not isinstance(
            raw_article,
            dict,
        ):
            continue

        article = cast(
            dict[str, Any],
            raw_article,
        )

        trusted_source = (
            find_trusted_legal_source(
                ai_article=article,
                legal_sources=legal_sources,
            )
        )

        if trusted_source is None:
            continue

        key = build_legal_source_key(
            trusted_source
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        reason = str(
            article.get(
                "reason",
                "",
            )
        ).strip()

        validated.append(
            {
                "law_number": str(
                    trusted_source.get(
                        "law_number",
                        "",
                    )
                ).strip(),
                "year": str(
                    trusted_source.get(
                        "year",
                        "",
                    )
                ).strip(),
                "article": str(
                    trusted_source.get(
                        "article",
                        "",
                    )
                ).strip(),
                "source_url": str(
                    trusted_source.get(
                        "source_url",
                        "",
                    )
                ).strip(),
                "reason": reason,
            }
        )

    return validated


def validate_legal_analysis(
    result: dict[str, Any],
    legal_sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Validate one legal-analysis result.

    This prevents AI-generated legal citations from
    being accepted unless they match retrieved
    Bahrain legal sources.
    """

    status = str(
        result.get(
            "status",
            "NOT VERIFIED",
        )
    ).strip().upper()

    if status not in ALLOWED_STATUSES:
        status = "NOT VERIFIED"

    explanation = str(
        result.get(
            "explanation",
            "",
        )
    ).strip()

    recommendation = str(
        result.get(
            "recommendation",
            "",
        )
    ).strip()

    relevant_articles = (
        validate_relevant_articles(
            raw_articles=result.get(
                "relevant_articles",
                [],
            ),
            legal_sources=legal_sources,
        )
    )

    raw_articles = result.get("relevant_articles", [])
    unsupported_citations = (
        isinstance(raw_articles, list)
        and any(
            not isinstance(article, dict)
            or find_trusted_legal_source(
                ai_article=article,
                legal_sources=legal_sources,
            ) is None
            for article in raw_articles
        )
    )

    if unsupported_citations and status in {
        "PASS", "ISSUE", "WARNING"
    }:
        status = "NOT VERIFIED"
        explanation = (
            "The AI response contained unsupported legal "
            "citations. " + explanation
        )

    if (
        status
        in {
            "PASS",
            "ISSUE",
            "WARNING",
        }
        and not relevant_articles
    ):
        status = "NOT VERIFIED"
    unverified_articles = [
        article
        for article in relevant_articles
        if (
            source := find_trusted_legal_source(
                ai_article=article,
                legal_sources=legal_sources,
            )
        ) is not None
        and str(
            source.get("effective_status", "unverified")
        ).strip().lower() != "verified_current"
    ]

    if unverified_articles:
        status = "NOT VERIFIED"
        explanation = (
            "The cited Bahrain legal provisions have not "
            "been independently verified as currently effective. "
            + explanation
        )
        recommendation = (
            "Verify the cited provisions and amendments "
            "against the official current legislation "
            "before relying on this assessment. "
            + recommendation
        )

    if (
        status == "NOT VERIFIED"
        and not explanation
    ):
        explanation = (
            "The available Bahrain legal material "
            "was not sufficient to verify this "
            "document point."
        )

    if not recommendation:
        recommendation = (
            "Review this point manually against "
            "the applicable Bahrain legal "
            "requirements."
        )

    return {
        "status": status,
        "explanation": explanation,
        "relevant_articles": (
            relevant_articles
        ),
        "recommendation": recommendation,
    }
def compare_point_with_regulations(
    point: dict[str, Any],
    regulations: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compare one document point with retrieved
    Bahrain regulations.

    Kept for compatibility with any other part
    of the application that uses single-point
    legal analysis.

    Analyze Document will use the batch function
    below for much better performance.
    """

    if not regulations:
        return get_not_verified_analysis()

    legal_sources = build_legal_sources(
        regulations
    )

    # ---------------------------------------------------------
    # TEST MODE
    # ---------------------------------------------------------

    if settings.TEST_MODE:
        test_result = get_test_legal_analysis(
            legal_sources
        )

        return validate_legal_analysis(
            result=test_result,
            legal_sources=legal_sources,
        )

    # ---------------------------------------------------------
    # REAL AI MODE
    # ---------------------------------------------------------

    prompt = f"""
You are analyzing one point from a document
against retrieved Bahrain legal provisions.

IMPORTANT RULES:

- Use ONLY the Bahrain legal provisions supplied below.
- Do NOT invent laws, articles, requirements or legal conclusions.
- Do NOT rely on legal information that is not provided below.
- A retrieved article may be irrelevant even if it contains similar words.
- Carefully determine whether each retrieved article is actually relevant.
- Ignore retrieved provisions that are not genuinely relevant.
- If the supplied provisions are insufficient to verify the document point,
  return NOT VERIFIED.
- Preserve law numbers, years, article numbers and source URLs exactly.
- Do not cite an article unless it appears in the supplied provisions.
- Explain the reasoning clearly and conservatively.

Allowed status values:

PASS
The document point appears consistent with
the supplied relevant provisions.

ISSUE
The document point appears to conflict with
a supplied relevant provision.

WARNING
There is a potential concern, ambiguity,
missing condition, or qualification that
should be reviewed.

NOT VERIFIED
The supplied provisions are not sufficient
to verify the point.

DOCUMENT POINT:

{json.dumps(
    point,
    ensure_ascii=False,
    indent=2
)}

RETRIEVED BAHRAIN LEGAL PROVISIONS:

{json.dumps(
    legal_sources,
    ensure_ascii=False,
    indent=2
)}

Return ONLY valid JSON using exactly this structure:

{{
    "status": "PASS | ISSUE | WARNING | NOT VERIFIED",
    "explanation": "",
    "relevant_articles": [
        {{
            "law_number": "",
            "year": "",
            "article": "",
            "source_url": "",
            "reason": ""
        }}
    ],
    "recommendation": ""
}}
"""

    result_text = clean_json_response(
        generate_ai_text(
            prompt
        )
    )

    try:
        raw_result: Any = json.loads(
            result_text
        )

    except json.JSONDecodeError as exc:
        raise ValueError(
            "The AI returned an invalid legal "
            "analysis JSON response."
        ) from exc

    if not isinstance(
        raw_result,
        dict,
    ):
        raise ValueError(
            "The AI returned an invalid legal "
            "analysis response."
        )

    result = cast(
        dict[str, Any],
        raw_result,
    )

    return validate_legal_analysis(
        result=result,
        legal_sources=legal_sources,
    )


# ---------------------------------------------------------
# Batch legal analysis
# ---------------------------------------------------------


def build_batch_item(
    item: dict[str, Any],
    batch_index: int,
) -> dict[str, Any]:
    """
    Build a compact item for one batch AI request.

    Only the document point and trusted retrieved
    legal sources are sent to the AI.
    """

    point_value: Any = item.get(
        "point",
        {},
    )

    regulations_value: Any = item.get(
        "regulations",
        [],
    )

    point: dict[str, Any]

    if isinstance(
        point_value,
        dict,
    ):
        point = cast(
            dict[str, Any],
            point_value,
        )
    else:
        point = {}

    regulations: list[
        dict[str, Any]
    ] = []

    if isinstance(
        regulations_value,
        list,
    ):
        for raw_regulation in cast(
            list[Any],
            regulations_value,
        ):
            if isinstance(
                raw_regulation,
                dict,
            ):
                regulations.append(
                    cast(
                        dict[str, Any],
                        raw_regulation,
                    )
                )

    legal_sources = build_legal_sources(
        regulations
    )

    return {
        "batch_index": batch_index,
        "point": point,
        "legal_sources": legal_sources,
    }


def build_batch_payload(
    batch: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Convert a retrieved-law batch into the compact
    structure sent to the AI provider.
    """

    payload: list[
        dict[str, Any]
    ] = []

    for index, item in enumerate(
        batch
    ):
        payload.append(
            build_batch_item(
                item=item,
                batch_index=index,
            )
        )

    return payload


def get_batch_test_results(
    batch_payload: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Build deterministic batch results in TEST_MODE.

    Trusted legal sources still come from the real
    Bahrain knowledge base.
    """

    results: list[
        dict[str, Any]
    ] = []

    for batch_item in batch_payload:
        batch_index_value: Any = (
            batch_item.get(
                "batch_index",
                0,
            )
        )

        try:
            batch_index = int(
                str(
                    batch_index_value
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            batch_index = 0

        legal_sources_value: Any = (
            batch_item.get(
                "legal_sources",
                [],
            )
        )

        legal_sources: list[
            dict[str, Any]
        ] = []

        if isinstance(
            legal_sources_value,
            list,
        ):
            for raw_source in cast(
                list[Any],
                legal_sources_value,
            ):
                if isinstance(
                    raw_source,
                    dict,
                ):
                    legal_sources.append(
                        cast(
                            dict[str, Any],
                            raw_source,
                        )
                    )

        test_result = (
            get_test_legal_analysis(
                legal_sources
            )
        )

        results.append(
            {
                "batch_index": (
                    batch_index
                ),
                **test_result,
            }
        )

    return results


def validate_batch_results(
    raw_results: Any,
    batch_payload: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    """
    Validate all AI batch results against the
    trusted legal sources belonging to each point.

    AI citations are never accepted unless they
    match the retrieved Bahrain sources for that
    exact document point.
    """

    validated: dict[
        int,
        dict[str, Any],
    ] = {}

    if not isinstance(
        raw_results,
        list,
    ):
        return validated

    for raw_result in cast(
        list[Any],
        raw_results,
    ):
        if not isinstance(
            raw_result,
            dict,
        ):
            continue

        result = cast(
            dict[str, Any],
            raw_result,
        )

        batch_index_value: Any = (
            result.get(
                "batch_index",
                -1,
            )
        )

        try:
            batch_index = int(
                str(
                    batch_index_value
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        if (
            batch_index < 0
            or batch_index
            >= len(
                batch_payload
            )
        ):
            continue

        batch_item = (
            batch_payload[
                batch_index
            ]
        )

        legal_sources_value: Any = (
            batch_item.get(
                "legal_sources",
                [],
            )
        )

        legal_sources: list[
            dict[str, Any]
        ] = []

        if isinstance(
            legal_sources_value,
            list,
        ):
            for raw_source in cast(
                list[Any],
                legal_sources_value,
            ):
                if isinstance(
                    raw_source,
                    dict,
                ):
                    legal_sources.append(
                        cast(
                            dict[str, Any],
                            raw_source,
                        )
                    )

        validated_result = (
            validate_legal_analysis(
                result=result,
                legal_sources=legal_sources,
            )
        )

        validated[
            batch_index
        ] = validated_result

    return validated


def analyze_legal_batch(
    batch: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Analyze multiple document points in one AI
    request.

    Each point remains isolated with its own
    retrieved Bahrain legal sources.

    The returned AI citations are validated again
    against the trusted sources after generation.
    """

    if not batch:
        return []

    batch_payload = (
        build_batch_payload(
            batch
        )
    )

    # ---------------------------------------------------------
    # TEST MODE
    # ---------------------------------------------------------

    if settings.TEST_MODE:
        test_results = (
            get_batch_test_results(
                batch_payload
            )
        )

        validated_test = (
            validate_batch_results(
                raw_results=test_results,
                batch_payload=batch_payload,
            )
        )

        ordered_test_results: list[
            dict[str, Any]
        ] = []

        for index in range(
            len(batch_payload)
        ):
            ordered_test_results.append(
                validated_test.get(
                    index,
                    get_not_verified_analysis(),
                )
            )

        return ordered_test_results

    # ---------------------------------------------------------
    # REAL AI MODE
    # ---------------------------------------------------------

    prompt = f"""
You are analyzing multiple document points
against retrieved Bahrain legal provisions.

Each item below contains:

- batch_index
- one document point
- legal_sources retrieved specifically for that point

IMPORTANT RULES:

- Analyze EACH item independently.
- Use ONLY the legal_sources supplied inside that exact item.
- Do NOT use a legal source from one item for another item.
- Do NOT invent laws, articles, source URLs or legal requirements.
- Do NOT rely on legal information that is not supplied.
- A retrieved article may still be irrelevant even if it contains
  similar words.
- Carefully determine whether each retrieved article is genuinely
  applicable to the document point.
- Ignore irrelevant retrieved provisions.
- Examine each supplied legal source for its substantive connection
  to the specific document point, not merely shared keywords.
- Distinguish legal relevance from verification of current legal effect.
- Include genuinely applicable provisions in relevant_articles,
  even when their effective_status is not verified_current.
- For each cited provision, explain which part of the document point
  it addresses and what legal condition or limitation it introduces.
- Never describe an unverified provision as confirmed currently effective.
- Do not omit a relevant provision solely because its current legal
  effect has not been independently verified.
- If the supplied provisions are insufficient, return NOT VERIFIED.
- Preserve law numbers, years and article numbers exactly.
- Return one result for every supplied batch_index.
- Explain conclusions conservatively.

Allowed status values:

PASS
The document point appears consistent with
the supplied relevant provisions.

ISSUE
The document point appears to conflict with
a supplied relevant provision.

WARNING
There is a potential concern, ambiguity,
missing condition, or qualification that
should be reviewed.

NOT VERIFIED
The supplied provisions are not sufficient
to verify the point.

BATCH ITEMS:

{json.dumps(
    batch_payload,
    ensure_ascii=False,
    indent=2
)}

Return ONLY valid JSON using exactly this structure:

{{
    "results": [
        {{
            "batch_index": 0,
            "status": "PASS | ISSUE | WARNING | NOT VERIFIED",
            "explanation": "",
            "relevant_articles": [
                {{
                    "law_number": "",
                    "year": "",
                    "article": "",
                    "source_url": "",
                    "reason": ""
                }}
            ],
            "recommendation": ""
        }}
    ]
}}
"""

    result_text = clean_json_response(
        generate_ai_text(
            prompt
        )
    )

    try:
        parsed_raw: Any = json.loads(
            result_text
        )

    except json.JSONDecodeError as exc:
        raise ValueError(
            "The AI returned an invalid batch "
            "legal analysis JSON response."
        ) from exc

    if not isinstance(
        parsed_raw,
        dict,
    ):
        raise ValueError(
            "The AI returned an invalid batch "
            "legal analysis response."
        )

    parsed = cast(
        dict[str, Any],
        parsed_raw,
    )

    raw_results: Any = parsed.get(
        "results",
        [],
    )

    validated_results = (
        validate_batch_results(
            raw_results=raw_results,
            batch_payload=batch_payload,
        )
    )

    ordered_results: list[
        dict[str, Any]
    ] = []

    for index in range(
        len(batch_payload)
    ):
        ordered_results.append(
            validated_results.get(
                index,
                get_not_verified_analysis(),
            )
        )

    return ordered_results
def analyze_legal_points(
    retrieved_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Analyze all retrieved document points against
    Bahrain legal provisions.

    Points are processed in batches to reduce the
    number of AI requests while preserving each
    point's own trusted legal context.
    """

    if not retrieved_items:
        return []

    final_results: list[
        dict[str, Any]
    ] = []

    from concurrent.futures import ThreadPoolExecutor

    batches = [
        retrieved_items[start:start + LEGAL_BATCH_SIZE]
        for start in range(0, len(retrieved_items), LEGAL_BATCH_SIZE)
    ]

    with ThreadPoolExecutor(max_workers=2) as executor:
        all_batch_results = list(
            executor.map(analyze_legal_batch, batches)
        )

    for batch, batch_results in zip(batches, all_batch_results):

        for offset, item in enumerate(
            batch
        ):
            point_value: Any = item.get(
                "point",
                {},
            )

            regulations_value: Any = (
                item.get(
                    "regulations",
                    [],
                )
            )

            search_query = str(
                item.get(
                    "search_query",
                    "",
                )
            ).strip()

            search_queries_value: Any = (
                item.get(
                    "search_queries",
                    [],
                )
            )

            if isinstance(
                point_value,
                dict,
            ):
                point = cast(
                    dict[str, Any],
                    point_value,
                )
            else:
                point = {}

            regulations: list[
                dict[str, Any]
            ] = []

            if isinstance(
                regulations_value,
                list,
            ):
                for raw_regulation in cast(
                    list[Any],
                    regulations_value,
                ):
                    if isinstance(
                        raw_regulation,
                        dict,
                    ):
                        regulations.append(
                            cast(
                                dict[str, Any],
                                raw_regulation,
                            )
                        )

            search_queries: list[str] = []

            if isinstance(
                search_queries_value,
                list,
            ):
                for raw_query in cast(
                    list[Any],
                    search_queries_value,
                ):
                    query = str(
                        raw_query
                    ).strip()

                    if query:
                        search_queries.append(
                            query
                        )

            if offset < len(
                batch_results
            ):
                legal_analysis = (
                    batch_results[
                        offset
                    ]
                )
            else:
                legal_analysis = (
                    get_not_verified_analysis()
                )

            final_results.append(
                {
                    "point": point,
                    "search_query": (
                        search_query
                    ),
                    "search_queries": (
                        search_queries
                    ),
                    "regulations": (
                        regulations
                    ),
                    "legal_analysis": (
                        legal_analysis
                    ),
                }
            )

    return final_results


def analyze_points_against_bahrain_law(
    points: list[dict[str, Any]],
    limit_per_point: int = 5,
) -> list[dict[str, Any]]:
    """
    Complete Bahrain legal-analysis workflow.

    1. Retrieve relevant Bahrain regulations for
       each extracted document point.

    2. Analyze the points against their retrieved
       legal provisions.

    3. Return the original point, retrieval data,
       trusted regulations and validated legal
       analysis.

    Retrieval remains local.

    TEST_MODE does not call an external AI provider.

    REAL AI MODE uses the provider selected in the
    central AI provider configuration.
    """

    if not points:
        return []

    retrieved_items = (
        retrieve_laws_for_points(
            points=points,
            limit_per_point=limit_per_point,
        )
    )

    return analyze_legal_points(
        retrieved_items
    )


def analyze_document_points(
    points: list[dict[str, Any]],
    limit_per_point: int = 5,
) -> list[dict[str, Any]]:
    """
    Compatibility wrapper for document-analysis
    callers.

    This keeps the public service interface simple
    while the internal legal analysis uses batched
    AI requests.
    """

    return analyze_points_against_bahrain_law(
        points=points,
        limit_per_point=limit_per_point,
    )
def compare_points_with_regulations_batch(
    legal_retrieval: list[dict[str, Any]],
    batch_size: int = LEGAL_BATCH_SIZE,
) -> list[dict[str, Any]]:
    """
    Compatibility wrapper for the document-analysis API.
    """

    return analyze_legal_points(
        legal_retrieval
    )
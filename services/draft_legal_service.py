from typing import Any, cast

from services.draft_service import (
    LegalTopic,
    get_legal_topics,
)

from services.legal_retriever import (
    search_regulations,
)


class DraftLegalServiceError(Exception):
    pass


def build_requirement_key(
    requirement: dict[str, Any],
) -> str:
    """
    Build a stable unique key using the
    actual fields stored in regulations.json.
    """

    regulation_id = str(
        requirement.get(
            "id",
            "",
        )
    ).strip()

    if regulation_id:
        return regulation_id

    source_id = str(
        requirement.get(
            "source_id",
            "",
        )
    ).strip()

    article = str(
        requirement.get(
            "article",
            "",
        )
    ).strip()

    title = str(
        requirement.get(
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


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """
    Safely convert a value to int.
    """

    try:
        return int(
            str(value)
        )

    except (
        TypeError,
        ValueError,
    ):
        return default


def get_relevance_score(
    requirement: dict[str, Any],
) -> int:
    """
    Safely read a requirement relevance score.
    """

    return safe_int(
        requirement.get(
            "relevance_score",
            0,
        )
    )


def get_topic_relevance_score(
    requirement: dict[str, Any],
) -> int:
    """
    Return the combined relevance score
    calculated across the topic queries.
    """

    return safe_int(
        requirement.get(
            "topic_relevance_score",
            get_relevance_score(
                requirement
            ),
        ),
        get_relevance_score(
            requirement
        ),
    )


def get_best_relevance_score(
    requirement: dict[str, Any],
) -> int:
    """
    Return the strongest individual query score
    recorded for a requirement.
    """

    return safe_int(
        requirement.get(
            "best_relevance_score",
            get_relevance_score(
                requirement
            ),
        ),
        get_relevance_score(
            requirement
        ),
    )


def get_query_scores(
    requirement: dict[str, Any],
) -> dict[str, int]:
    """
    Safely read stored per-query relevance scores.
    """

    result: dict[str, int] = {}

    raw_value: Any = requirement.get(
        "query_scores",
        {},
    )

    if not isinstance(
        raw_value,
        dict,
    ):
        return result

    raw_dict = cast(
        dict[Any, Any],
        raw_value,
    )

    for raw_key, raw_score in (
        raw_dict.items()
    ):
        key = str(
            raw_key
        ).strip()

        if not key:
            continue

        result[
            key
        ] = safe_int(
            raw_score
        )

    return result


def get_query_score(
    requirement: dict[str, Any],
    query: str,
) -> int:
    """
    Return one provision's score for a
    particular topic query.
    """

    query_scores = get_query_scores(
        requirement
    )

    return query_scores.get(
        query,
        0,
    )


def prepare_requirement(
    match: dict[str, Any],
    topic_key: str,
    topic_name: str,
    topic_required: bool,
    query: str,
) -> dict[str, Any]:
    """
    Add stable legal identifiers and topic
    metadata to one retrieved provision.
    """

    requirement: dict[str, Any] = {
        **match
    }

    requirement[
        "regulation_id"
    ] = str(
        match.get(
            "id",
            "",
        )
    ).strip()

    requirement[
        "law_id"
    ] = str(
        match.get(
            "source_id",
            "",
        )
    ).strip()

    requirement[
        "article_number"
    ] = str(
        match.get(
            "article",
            "",
        )
    ).strip()

    requirement[
        "legal_topic"
    ] = topic_key

    requirement[
        "legal_topic_name"
    ] = topic_name

    requirement[
        "topic_required"
    ] = topic_required

    requirement[
        "matched_query"
    ] = query

    return requirement


def combine_candidate(
    candidates: dict[
        str,
        dict[str, Any],
    ],
    requirement: dict[str, Any],
    query: str,
) -> None:
    """
    Add one provision to the candidate pool.

    Repeated matches across different queries
    provide supporting evidence, but the strongest
    individual query score is preserved separately.
    """

    unique_key = build_requirement_key(
        requirement
    )

    if not unique_key:
        return

    new_score = get_relevance_score(
        requirement
    )

    existing = candidates.get(
        unique_key
    )

    if existing is None:

        requirement[
            "best_relevance_score"
        ] = new_score

        requirement[
            "topic_relevance_score"
        ] = new_score

        requirement[
            "query_match_count"
        ] = 1

        requirement[
            "matched_queries"
        ] = [
            query
        ]

        requirement[
            "query_scores"
        ] = {
            query: new_score
        }

        candidates[
            unique_key
        ] = requirement

        return

    existing_best_score = (
        get_best_relevance_score(
            existing
        )
    )

    existing_topic_score = (
        get_topic_relevance_score(
            existing
        )
    )

    matched_queries_raw: Any = (
        existing.get(
            "matched_queries",
            [],
        )
    )

    matched_queries: list[str] = []

    if isinstance(
        matched_queries_raw,
        list,
    ):
        typed_matched_queries = cast(
            list[Any],
            matched_queries_raw,
        )

        for item in typed_matched_queries:
            item_text = str(
                item
            ).strip()

            if (
                item_text
                and item_text
                not in matched_queries
            ):
                matched_queries.append(
                    item_text
                )

    if query in matched_queries:
        return

    matched_queries.append(
        query
    )

    query_scores = get_query_scores(
        existing
    )

    query_scores[
        query
    ] = new_score

    # Supporting queries matter, but their
    # contribution is capped so repeated broad
    # matches do not completely dominate.
    support_score = min(
        new_score,
        60,
    )

    combined_score = (
        existing_topic_score
        + support_score
    )

    existing[
        "best_relevance_score"
    ] = max(
        existing_best_score,
        new_score,
    )

    existing[
        "topic_relevance_score"
    ] = combined_score

    existing[
        "query_match_count"
    ] = len(
        matched_queries
    )

    existing[
        "matched_queries"
    ] = matched_queries

    existing[
        "query_scores"
    ] = query_scores

    # Keep the query that produced the
    # strongest individual result.
    if new_score > existing_best_score:
        existing[
            "matched_query"
        ] = query


def select_diverse_requirements(
    candidates: dict[
        str,
        dict[str, Any],
    ],
    search_queries: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    """
    Select strong provisions while preserving
    diversity across the configured topic queries.

    This prevents broad matches from occupying
    every final slot when a specific query has
    a highly relevant provision.
    """

    if limit <= 0:
        return []

    ranked_requirements = list(
        candidates.values()
    )

    if not ranked_requirements:
        return []

    ranked_requirements.sort(
        key=lambda item: (
            get_topic_relevance_score(
                item
            ),
            get_best_relevance_score(
                item
            ),
        ),
        reverse=True,
    )

    strongest_topic_score = (
        get_topic_relevance_score(
            ranked_requirements[0]
        )
    )

    minimum_topic_score = max(
        1,
        int(
            strongest_topic_score
            * 0.40
        ),
    )

    quality_candidates = [
        requirement
        for requirement
        in ranked_requirements
        if get_topic_relevance_score(
            requirement
        ) >= minimum_topic_score
    ]

    if not quality_candidates:
        return []

    selected: list[
        dict[str, Any]
    ] = []

    selected_keys: set[str] = set()

    # ---------------------------------------------
    # Phase 1
    # Give each configured query an opportunity
    # to contribute its strongest unique result.
    # ---------------------------------------------

    for query_value in search_queries:

        if len(selected) >= limit:
            break

        query = str(
            query_value
        ).strip()

        if not query:
            continue

        query_candidates: list[
            dict[str, Any]
        ] = []

        for requirement in (
            quality_candidates
        ):

            requirement_key = (
                build_requirement_key(
                    requirement
                )
            )

            if not requirement_key:
                continue

            if (
                requirement_key
                in selected_keys
            ):
                continue

            query_score = get_query_score(
                requirement,
                query,
            )

            if query_score <= 0:
                continue

            query_candidates.append(
                requirement
            )

        query_candidates.sort(
            key=lambda item: (
                get_query_score(
                    item,
                    query,
                ),
                get_best_relevance_score(
                    item
                ),
                get_topic_relevance_score(
                    item
                ),
            ),
            reverse=True,
        )

        if not query_candidates:
            continue

        best_for_query = (
            query_candidates[0]
        )

        best_key = build_requirement_key(
            best_for_query
        )

        if not best_key:
            continue

        selected.append(
            best_for_query
        )

        selected_keys.add(
            best_key
        )

    # ---------------------------------------------
    # Phase 2
    # Fill remaining slots using the strongest
    # overall topic results.
    # ---------------------------------------------

    if len(selected) < limit:

        for requirement in (
            quality_candidates
        ):

            if len(selected) >= limit:
                break

            requirement_key = (
                build_requirement_key(
                    requirement
                )
            )

            if not requirement_key:
                continue

            if (
                requirement_key
                in selected_keys
            ):
                continue

            selected.append(
                requirement
            )

            selected_keys.add(
                requirement_key
            )

    # Final presentation remains ordered by
    # overall topic relevance.
    selected.sort(
        key=lambda item: (
            get_topic_relevance_score(
                item
            ),
            get_best_relevance_score(
                item
            ),
        ),
        reverse=True,
    )

    return selected[
        :limit
    ]


def retrieve_topic_requirements(
    topic: LegalTopic,
    limit_per_query: int,
) -> list[dict[str, Any]]:
    """
    Retrieve Bahrain legal provisions for one
    structured legal topic.

    All configured queries are searched and
    evidence for duplicate provisions is combined.

    Final selection considers both overall topic
    strength and query diversity.
    """

    topic_key = str(
        topic[
            "key"
        ]
    ).strip()

    topic_name = str(
        topic[
            "name"
        ]
    ).strip()

    topic_required = bool(
        topic[
            "required"
        ]
    )

    search_queries_raw = topic[
        "search_queries"
    ]

    search_queries: list[str] = [
        str(query).strip()
        for query in search_queries_raw
        if str(query).strip()
    ]

    if limit_per_query <= 0:
        return []

    if not search_queries:
        return []

    # Search more broadly internally so a strong
    # subtopic-specific provision is not discarded
    # before final selection.
    search_limit = max(
        limit_per_query * 5,
        10,
    )

    candidates: dict[
        str,
        dict[str, Any],
    ] = {}

    for query in search_queries:

        try:
            matches = search_regulations(
                query=query,
                limit=search_limit,
            )

        except Exception as exc:
            raise DraftLegalServiceError(
                "Could not retrieve legal "
                f"requirements for topic "
                f"'{topic_name}' using query "
                f"'{query}'."
            ) from exc

        for match in matches:

            requirement = (
                prepare_requirement(
                    match=match,
                    topic_key=topic_key,
                    topic_name=topic_name,
                    topic_required=(
                        topic_required
                    ),
                    query=query,
                )
            )

            combine_candidate(
                candidates=candidates,
                requirement=requirement,
                query=query,
            )

    return select_diverse_requirements(
        candidates=candidates,
        search_queries=search_queries,
        limit=limit_per_query,
    )


def retrieve_draft_legal_requirements(
    draft_type: str,
    limit_per_query: int = 3,
) -> list[dict[str, Any]]:
    """
    Retrieve Bahrain legal provisions for a
    draft organised by legal topic.

    limit_per_query is the maximum final number
    of provisions returned for each topic.
    """

    legal_topics: list[
        LegalTopic
    ] = get_legal_topics(
        draft_type
    )

    if not legal_topics:
        return []

    if limit_per_query <= 0:
        return []

    retrieved_requirements: list[
        dict[str, Any]
    ] = []

    global_seen: set[
        tuple[str, str]
    ] = set()

    for topic in legal_topics:

        topic_key = str(
            topic[
                "key"
            ]
        ).strip()

        topic_requirements = (
            retrieve_topic_requirements(
                topic=topic,
                limit_per_query=(
                    limit_per_query
                ),
            )
        )

        for requirement in (
            topic_requirements
        ):

            requirement_key = (
                build_requirement_key(
                    requirement
                )
            )

            if not requirement_key:
                continue

            # The same article may legitimately
            # support more than one legal topic.
            global_key = (
                topic_key,
                requirement_key,
            )

            if global_key in global_seen:
                continue

            global_seen.add(
                global_key
            )

            retrieved_requirements.append(
                requirement
            )

    # Preserve configured topic order.
    # Within each topic use combined relevance.
    topic_order: dict[
        str,
        int,
    ] = {
        str(
            topic[
                "key"
            ]
        ): index
        for index, topic
        in enumerate(
            legal_topics
        )
    }

    retrieved_requirements.sort(
        key=lambda item: (
            topic_order.get(
                str(
                    item.get(
                        "legal_topic",
                        "",
                    )
                ),
                999,
            ),
            -get_topic_relevance_score(
                item
            ),
        )
    )


    # Internal LangGraph research for draft legal topics.
    # Preserve the existing requirements and their format.
    from core_agents.graph import build_graph

    draft_legal_research_agent = build_graph()

    for topic in legal_topics:
        topic_queries = [
            str(q).strip()
            for q in topic.get("search_queries", [])
            if str(q).strip()
        ]

        if not topic_queries:
            continue

        agent_result = draft_legal_research_agent.invoke({
            "query": topic_queries[0],
            "search_attempts": 0,
        })

        topic_key = str(topic["key"]).strip()

        for requirement in retrieved_requirements:
            if str(requirement.get("legal_topic", "")).strip() == topic_key:
                requirement["legal_research_agent"] = {
                    "decision": agent_result.get("decision"),
                    "evidence_status": agent_result.get("evidence_status"),
                }

    return retrieved_requirements


def group_requirements_by_topic(
    requirements: list[
        dict[str, Any]
    ],
) -> dict[
    str,
    list[dict[str, Any]],
]:
    """
    Group retrieved provisions by
    their legal topic.
    """

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for requirement in requirements:

        topic_key = str(
            requirement.get(
                "legal_topic",
                "general",
            )
        ).strip()

        if not topic_key:
            topic_key = "general"

        if topic_key not in grouped:
            grouped[
                topic_key
            ] = []

        grouped[
            topic_key
        ].append(
            requirement
        )

    for topic_requirements in (
        grouped.values()
    ):
        topic_requirements.sort(
            key=get_topic_relevance_score,
            reverse=True,
        )

    return grouped
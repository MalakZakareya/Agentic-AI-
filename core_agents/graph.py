"""Bahrain legal research workflow with bounded retry."""

from typing import TypedDict
from langgraph.graph import StateGraph, START, END


class LegalAgentState(TypedDict, total=False):
    query: str
    evidence: list
    evidence_status: str
    rejected_evidence: list
    related_evidence: list
    quality_status: str
    search_attempts: int
    search_query: str
    decision: str
    previous_evidence_ids: list
    new_evidence_count: int
    evidence_unchanged: bool


def legal_research_agent(state: LegalAgentState):
    from services.legal_retriever import search_regulations

    attempts = state.get("search_attempts", 0) + 1
    query = state.get("search_query") or state["query"]

    results = search_regulations(query)

    # Retrieve narrowly related wage provisions for salary-increase questions.
    from services.legal_retriever import normalize_text

    normalized_query = normalize_text(state["query"])
    salary_increase_phrases = (
        "salary increase",
        "wage increase",
        "salary raise",
        "pay raise",
        "annual increment",
        "\u0632\u064a\u0627\u062f\u0629 \u0627\u0644\u0631\u0627\u062a\u0628",
        "\u0632\u064a\u0627\u062f\u0629 \u0627\u0644\u0623\u062c\u0631",
    )

    if any(
        phrase in normalized_query
        for phrase in salary_increase_phrases
    ):
        targeted_phrases = (
            "\u0627\u0644\u0623\u062c\u0631 \u0627\u0644\u0645\u062a\u0641\u0642 \u0639\u0644\u064a\u0647",
            "\u064a\u062d\u062f\u062f \u0623\u062c\u0631 \u0627\u0644\u0639\u0627\u0645\u0644",
        )

        seen = {
            (
                str(item.get("law_number")),
                str(item.get("article")),
                str(item.get("category")),
            )
            for item in results
        }

        for phrase in targeted_phrases:
            for item in search_regulations(phrase, limit=5):
                if item.get("category") != "labour":
                    continue

                item_text = normalize_text(
                    str(item.get("text") or "")
                )

                if not any(
                    normalize_text(term) in item_text
                    for term in targeted_phrases
                ):
                    continue

                item_id = (
                    str(item.get("law_number")),
                    str(item.get("article")),
                    str(item.get("category")),
                )

                if item_id not in seen:
                    results.append(item)
                    seen.add(item_id)


    def evidence_identity(item):
        return (
            str(item.get("law_number")),
            str(item.get("article")),
            str(item.get("category")),
        )

    current_ids = {
        evidence_identity(item)
        for item in results
    }

    previous_ids = {
        tuple(item)
        for item in state.get("previous_evidence_ids", [])
    }

    evidence_unchanged = (
        attempts > 1
        and current_ids == previous_ids
    )

    new_evidence_count = (
        len(current_ids - previous_ids)
        if attempts > 1
        else len(current_ids)
    )

    return {
        "evidence": results,
        "search_attempts": attempts,
        "search_query": query,
        "previous_evidence_ids": sorted(current_ids),
        "new_evidence_count": new_evidence_count,
        "evidence_unchanged": evidence_unchanged,
    }




def evidence_quality_agent(state: LegalAgentState):
    """Filter legal evidence by domain and supported topic."""
    from services.legal_retriever import (
        normalize_text,
        detect_legal_concepts,
    )

    query = state["query"].lower()
    evidence = state.get("evidence", [])

    labour_terms = (
        "labour law",
        "labor law",
        "employment law",
        "\u0642\u0627\u0646\u0648\u0646 \u0627\u0644\u0639\u0645\u0644",
    )

    commercial_terms = (
        "commercial law",
        "\u0642\u0627\u0646\u0648\u0646 \u0627\u0644\u062a\u062c\u0627\u0631\u0629",
        "\u0627\u0644\u0642\u0627\u0646\u0648\u0646 \u0627\u0644\u062a\u062c\u0627\u0631\u064a",
    )

    required_category = None

    if any(term in query for term in labour_terms):
        required_category = "labour"
    elif any(term in query for term in commercial_terms):
        required_category = "commercial_law"

    accepted = []
    rejected = []

    for item in evidence:
        if (
            required_category is None
            or item.get("category") == required_category
        ):
            accepted.append(item)
        else:
            rejected.append(item)

    concepts = detect_legal_concepts(state["query"])

    normalized_query = normalize_text(state["query"])

    public_holiday_phrases = (
        "public holiday",
        "public holidays",
        "official holiday",
        "official holidays",
        "\u0627\u0644\u0639\u0637\u0644\u0627\u062a \u0627\u0644\u0631\u0633\u0645\u064a\u0629",
    )

    is_public_holidays = any(
        phrase in normalized_query
        for phrase in public_holiday_phrases
    )

    if is_public_holidays:
        quality_status = "PUBLIC_HOLIDAYS_REVIEW"

    elif any(
        phrase in normalized_query
        for phrase in (
            "salary increase",
            "wage increase",
            "salary raise",
            "pay raise",
            "annual increment",
            "\u0632\u064a\u0627\u062f\u0629 \u0627\u0644\u0631\u0627\u062a\u0628",
            "\u0632\u064a\u0627\u062f\u0629 \u0627\u0644\u0623\u062c\u0631",
        )
    ):
        direct_terms = (
            "\u0632\u064a\u0627\u062f\u0629 \u0633\u0646\u0648\u064a\u0629",
            "\u0627\u0644\u0632\u064a\u0627\u062f\u0629 \u0627\u0644\u0633\u0646\u0648\u064a\u0629",
            "\u0632\u064a\u0627\u062f\u0629 \u0627\u0644\u0623\u062c\u0631",
        )

        related_terms = (
            "\u0627\u0644\u0623\u062c\u0631 \u0627\u0644\u0645\u062a\u0641\u0642 \u0639\u0644\u064a\u0647",
            "\u064a\u062d\u062f\u062f \u0623\u062c\u0631 \u0627\u0644\u0639\u0627\u0645\u0644",
        )

        direct = []
        related = []
        topic_rejected = []

        for item in accepted:
            article_text = normalize_text(str(item.get("text") or ""))

            if any(
                normalize_text(term) in article_text
                for term in direct_terms
            ):
                direct.append(item)
            elif any(
                normalize_text(term) in article_text
                for term in related_terms
            ):
                related.append(item)
            else:
                topic_rejected.append(item)

        rejected.extend(topic_rejected)
        accepted = direct

        quality_status = (
            "TOPIC_FILTERED"
            if direct
            else "TOPIC_NOT_CONFIRMED"
        )

        return {
            "evidence": accepted,
            "related_evidence": related,
            "rejected_evidence": rejected,
            "quality_status": quality_status,
        }

    elif "annual_leave" in concepts:
        annual_leave_terms = (
            "\u0625\u062c\u0627\u0632\u0629 \u0633\u0646\u0648\u064a\u0629",
            "\u0627\u0644\u0625\u062c\u0627\u0632\u0629 \u0627\u0644\u0633\u0646\u0648\u064a\u0629",
        )

        topic_matches = []
        topic_rejected = []

        for item in accepted:
            text = normalize_text(str(item.get("text", "")))

            if any(
                normalize_text(term) in text
                for term in annual_leave_terms
            ):
                topic_matches.append(item)
            else:
                topic_rejected.append(item)

        if topic_matches:
            accepted = topic_matches
            rejected.extend(topic_rejected)

            quality_status = "TOPIC_FILTERED"
        else:
            rejected.extend(accepted)
            accepted = []
            quality_status = "TOPIC_NOT_CONFIRMED"

    elif "contract_formation" in concepts:
        formation_phrases = (
            "\u064a\u0646\u0639\u0642\u062f \u0627\u0644\u0639\u0642\u062f",
            "\u0644\u0627\u0646\u0639\u0642\u0627\u062f \u0627\u0644\u0639\u0642\u062f",
            "\u0627\u0644\u0625\u064a\u062c\u0627\u0628 \u0628\u0627\u0644\u0642\u0628\u0648\u0644",
            "\u0627\u0644\u0642\u0628\u0648\u0644 \u0645\u0637\u0627\u0628\u0642\u0627",
        )

        def formation_match(item):
            article_text = normalize_text(
                str(item.get("text") or "")
            )
            return any(
                normalize_text(phrase) in article_text
                for phrase in formation_phrases
            )

        related = [
            item for item in rejected
            if formation_match(item)
        ]

        rejected = [
            item for item in rejected
            if not formation_match(item)
        ]

        accepted_matches = [
            item for item in accepted
            if formation_match(item)
        ]

        rejected.extend(
            item for item in accepted
            if not formation_match(item)
        )

        accepted = accepted_matches

        if accepted:
            quality_status = "TOPIC_FILTERED"
        else:
            quality_status = "TOPIC_NOT_CONFIRMED"

        return {
            "evidence": accepted,
            "rejected_evidence": rejected,
            "related_evidence": related,
            "quality_status": quality_status,
        }

    elif required_category is not None:
        quality_status = "DOMAIN_FILTERED"

    else:
        quality_status = "DOMAIN_NOT_SPECIFIED"

    return {
        "evidence": accepted,
        "rejected_evidence": rejected,
        "quality_status": quality_status,
    }


def evidence_check_agent(state: LegalAgentState):
    evidence = state.get("evidence", [])
    attempts = state.get("search_attempts", 0)

    if (
        attempts > 1
        and state.get("evidence_unchanged") is True
    ):
        return {
            "evidence_status": "NO_NEW_EVIDENCE",
            "decision": "HUMAN_REVIEW",
        }

    if state.get("quality_status") == "TOPIC_NOT_CONFIRMED":
        if attempts < 2:
            retry_query = state["query"].replace(
                "Bahrain", ""
            ).replace("Law", "").strip()

            current_query = (
                state.get("search_query") or state["query"]
            ).strip()

            if (
                retry_query
                and retry_query.casefold() != current_query.casefold()
            ):
                return {
                    "evidence_status": "TOPIC_NOT_CONFIRMED",
                    "decision": "RETRY",
                    "search_query": retry_query,
                }

        return {
            "evidence_status": "TOPIC_NOT_CONFIRMED",
            "decision": "HUMAN_REVIEW",
        }

    if not evidence:
        if attempts < 2:
            return {
                "evidence_status": "INSUFFICIENT",
                "decision": "RETRY",
                "search_query": state["query"].replace(
                    "Bahrain", ""
                ).replace("Law", "").strip(),
            }

        return {
            "evidence_status": "INSUFFICIENT",
            "decision": "STOP",
        }

    if state.get("quality_status") != "TOPIC_FILTERED":
        return {
            "evidence_status": "TOPIC_REQUIRES_REVIEW",
            "decision": "HUMAN_REVIEW",
        }

    if any(
        str(item.get("effective_status", "unverified"))
        .strip().lower() != "verified_current"
        for item in evidence
    ):
        return {
            "evidence_status": "REQUIRES_VERIFICATION",
            "decision": "HUMAN_REVIEW",
        }

    # Fail closed if source verification is missing or pending.
    # A source's effective_status alone cannot authorize PROCEED.
    for item in evidence:
        registry = item.get("verification_registry")

        if not isinstance(registry, dict):
            return {
                "evidence_status": "REGISTRY_REQUIRES_VERIFICATION",
                "decision": "HUMAN_REVIEW",
            }

        if (
            registry.get("status") != "verified_current"
            or registry.get("verified_current") is not True
            or not isinstance(registry.get("evidence_count"), int)
            or isinstance(registry.get("evidence_count"), bool)
            or registry.get("evidence_count") < 1
            or not registry.get("reviewed_at")
            or not registry.get("reviewed_by")
        ):
            return {
                "evidence_status": "REGISTRY_REQUIRES_VERIFICATION",
                "decision": "HUMAN_REVIEW",
            }

    # Independently verify authorization against the local registry.
    # Never trust verification metadata supplied inside evidence alone.
    from services.legal_retriever import load_verification_registry

    trusted_registry = load_verification_registry()

    for item in evidence:
        source_id = str(item.get("source_id") or "").strip()
        trusted = trusted_registry.get(source_id)

        if (
            not source_id
            or not isinstance(trusted, dict)
            or trusted.get("status") != "verified_current"
            or trusted.get("verified_current") is not True
            or not isinstance(trusted.get("evidence_count"), int)
            or isinstance(trusted.get("evidence_count"), bool)
            or trusted.get("evidence_count") < 1
            or not trusted.get("reviewed_at")
            or not trusted.get("reviewed_by")
        ):
            return {
                "evidence_status": "REGISTRY_REQUIRES_VERIFICATION",
                "decision": "HUMAN_REVIEW",
            }

    return {
        "evidence_status": "VERIFIED_CURRENT",
        "decision": "PROCEED",
    }


def route_after_check(state: LegalAgentState):
    if state["decision"] == "RETRY":
        return "legal_research"
    return END


def build_graph():
    builder = StateGraph(LegalAgentState)

    builder.add_node("legal_research", legal_research_agent)
    builder.add_node("evidence_quality", evidence_quality_agent)
    builder.add_node("evidence_check", evidence_check_agent)

    builder.add_edge(START, "legal_research")
    builder.add_edge("legal_research", "evidence_quality")
    builder.add_edge("evidence_quality", "evidence_check")

    builder.add_conditional_edges(
        "evidence_check",
        route_after_check,
        {
            "legal_research": "legal_research",
            END: END,
        },
    )

    return builder.compile()

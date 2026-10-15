"""Bahrain legal research workflow with bounded retry."""

from typing import TypedDict
from langgraph.graph import StateGraph, START, END


class LegalAgentState(TypedDict, total=False):
    query: str
    evidence: list
    evidence_status: str
    rejected_evidence: list
    quality_status: str
    search_attempts: int
    search_query: str
    decision: str


def legal_research_agent(state: LegalAgentState):
    from services.legal_retriever import search_regulations

    attempts = state.get("search_attempts", 0) + 1
    query = state.get("search_query") or state["query"]

    results = search_regulations(query)

    return {
        "evidence": results,
        "search_attempts": attempts,
        "search_query": query,
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
            quality_status = "TOPIC_NOT_CONFIRMED"

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

    if any(
        str(item.get("effective_status", "unverified"))
        .strip().lower() != "verified_current"
        for item in evidence
    ):
        return {
            "evidence_status": "REQUIRES_VERIFICATION",
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

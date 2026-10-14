from fastapi import APIRouter
from pydantic import BaseModel, Field

from core_agents.graph import build_graph


router = APIRouter(
    prefix="/api/v1/legal-research",
    tags=["Legal Research"],
)


class LegalResearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)


@router.post("")
def research_law(request: LegalResearchRequest):
    graph = build_graph()

    result = graph.invoke({
        "query": request.query,
        "search_attempts": 0,
    })

    evidence = result.get("evidence", [])

    return {
        "query": request.query,
        "decision": result.get("decision"),
        "evidence_status": result.get("evidence_status"),
        "quality_status": result.get("quality_status"),
        "articles": [
            {
                "article": law.get("article"),
                "title": law.get("title"),
                "text": law.get("text"),
                "category": law.get("category"),
                "effective_status": law.get("effective_status"),
                "relevance_score": law.get("relevance_score"),
            }
            for law in evidence
        ],
        "article_count": len(evidence),
        "disclaimer": (
            "Legal references require verification "
            "of current legal validity."
        ),
    }

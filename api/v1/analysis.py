from typing import Any, cast

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)

from services.document_service import (
    DocumentProcessingError,
    DocumentResult,
    extract_document_text,
)

from services.ai_service import (
    analyze_document_text,
)

from services.legal_analysis_service import (
    compare_points_with_regulations_batch,
    retrieve_laws_for_points,
)


router = APIRouter(
    prefix="/api/v1/analysis",
    tags=["Document Analysis"],
)


def get_valid_points(
    ai_analysis: dict[str, Any],
    document_text: str = "",
) -> list[dict[str, Any]]:
    """Accept only AI points with quotes grounded in the source document."""
    import re

    raw_points = ai_analysis.get("points", [])
    if not isinstance(raw_points, list):
        return []

    def normalized(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold()

    source = normalized(document_text)
    if not source:
        return []

    verified = []

    for raw_point in raw_points:
        if not isinstance(raw_point, dict):
            continue

        quote = raw_point.get("original_text")
        if not isinstance(quote, str) or not quote.strip():
            continue

        if normalized(quote) not in source:
            continue

        verified.append(raw_point)

    return verified



@router.post("/document")
async def analyze_document(
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """
    Complete Analyze Document pipeline:

    1. Read uploaded document.
    2. Extract document text.
    3. Use AI to understand the document.
    4. Extract meaningful document points.
    5. Retrieve relevant Bahrain regulations.
    6. Compare the points with retrieved laws
       using batched legal AI analysis.
    7. Return the complete legal analysis.
    """

    try:
        filename = file.filename

        if not filename:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Uploaded file must "
                    "have a filename."
                ),
            )

        print(
            f"\n=== ANALYZE DOCUMENT START: "
            f"{filename} ===",
            flush=True,
        )

        # ---------------------------------
        # 1. Read uploaded file
        # ---------------------------------

        print(
            "STEP 1: Reading uploaded file...",
            flush=True,
        )

        content = await file.read()

        print(
            "STEP 1 COMPLETE: File read -",
            len(content),
            "bytes",
            flush=True,
        )

        # ---------------------------------
        # 2. Extract document text
        # ---------------------------------

        print(
            "STEP 2: Extracting document text...",
            flush=True,
        )

        result: DocumentResult = (
            extract_document_text(
                filename=filename,
                content=content,
            )
        )

        print(
            "STEP 2 COMPLETE: Text extraction -",
            result["characters"],
            "characters",
            flush=True,
        )

        # ---------------------------------
        # 3. AI reads the document
        # ---------------------------------

        print(
            "STEP 3: Sending document to OpenAI...",
            flush=True,
        )

        ai_analysis = (
            analyze_document_text(
                document_text=result[
                    "text"
                ]
            )
        )

        print(
            "STEP 3 COMPLETE: "
            "OpenAI document analysis returned",
            flush=True,
        )

        # ---------------------------------
        # 4. Validate extracted points
        # ---------------------------------

        print(
            "STEP 4: Validating AI points...",
            flush=True,
        )

        points = get_valid_points(
            ai_analysis,
            document_text=result["text"],
        )

        print(
            "STEP 4 COMPLETE: Points found -",
            len(points),
            flush=True,
        )

        raw_points = ai_analysis.get("points", [])
        extracted_count = (
            len(raw_points)
            if isinstance(raw_points, list)
            else 0
        )
        verified_count = len(points)
        rejected_count = max(0, extracted_count - verified_count)

        if verified_count == 0:
            extraction_status = "NO_VERIFIED_POINTS"
        elif rejected_count:
            extraction_status = "PARTIAL_REVIEW_REQUIRED"
        else:
            extraction_status = "QUOTES_MATCHED"

        extraction_review = {
            "status": extraction_status,
            "extracted_points": extracted_count,
            "verified_points": verified_count,
            "rejected_points": rejected_count,
            "complete_analysis_verified": False,
            "human_review_required": True,
            "message": (
                "No AI-extracted quotations could be matched "
                "to the uploaded document."
                if verified_count == 0
                else (
                    "Some AI-extracted quotations could not be "
                    "matched to the uploaded document. "
                    "The legal analysis may be incomplete."
                    if rejected_count
                    else (
                        "All returned quotations matched the "
                        "extracted document text. This does not "
                        "prove every clause was extracted."
                    )
                )
            ),
        }


        for index, point in enumerate(
            points,
            start=1,
        ):
            point_title = (
                point.get("title")
                or point.get("topic")
                or point.get("name")
                or "Untitled point"
            )

            print(
                f"    Point {index}: "
                f"{point_title}",
                flush=True,
            )

        # ---------------------------------
        # 5. Retrieve Bahrain laws
        # ---------------------------------

        print(
            "STEP 5: Retrieving Bahrain laws...",
            flush=True,
        )

        legal_retrieval = (
            retrieve_laws_for_points(
                points=points,
                limit_per_point=5,
            )
        )

        print(
            "STEP 5 COMPLETE: Legal retrieval -",
            len(legal_retrieval),
            "items",
            flush=True,
        )

        # ---------------------------------
        # 6. BATCH legal comparison
        # ---------------------------------

        print(
            "STEP 6: Starting BATCH "
            "legal comparisons...",
            flush=True,
        )

        print(
            "STEP 6: Total points -",
            len(legal_retrieval),
            flush=True,
        )

        legal_analysis = (
            compare_points_with_regulations_batch(
                legal_retrieval=legal_retrieval,
                batch_size=8,
            )
        )

        print(
            "STEP 6 COMPLETE: "
            "All BATCH legal comparisons finished -",
            len(legal_analysis),
            "results",
            flush=True,
        )

        # ---------------------------------
        # 7. Return final result
        # ---------------------------------

        print(
            "STEP 7: Returning final response...",
            flush=True,
        )


        # Preserve the actual reason for each legal research decision.
        review_details = []

        for index, item in enumerate(legal_retrieval):
            agent = (
                item.get("legal_research_agent", {})
                if isinstance(item, dict)
                else {}
            )

            if not isinstance(agent, dict):
                agent = {}

            decision = str(
                agent.get("decision") or "HUMAN_REVIEW"
            ).strip().upper()

            raw_status = str(
                agent.get("evidence_status")
                or agent.get("quality_status")
                or "NOT_ASSESSED"
            ).strip().upper()

            if decision != "PROCEED" and raw_status == "VERIFIED_CURRENT":
                raw_status = "REQUIRES_VERIFICATION"

            review_details.append({
                "point_index": index,
                "decision": decision,
                "evidence_status": raw_status,
                "quality_status": agent.get("quality_status"),
                "accepted_evidence_count": agent.get(
                    "accepted_evidence_count", 0
                ),
                "related_evidence_count": agent.get(
                    "related_evidence_count", 0
                ),
                "rejected_evidence_count": agent.get(
                    "rejected_evidence_count", 0
                ),
            })

        review_reasons = sorted({
            detail["evidence_status"]
            for detail in review_details
            if detail["decision"] != "PROCEED"
            or detail["evidence_status"] != "VERIFIED_CURRENT"
        })

        if not review_details:
            review_status = "NOT_ASSESSED"
            evidence_status = "NOT_ASSESSED"
            review_message = "No legal research evidence was assessed."
        elif review_reasons:
            review_status = "HUMAN_REVIEW"
            evidence_status = (
                review_reasons[0]
                if len(review_reasons) == 1
                else "MULTIPLE_REVIEW_REASONS"
            )
            review_message = (
                "Human legal review required. Research evidence "
                "did not pass all topic and current-law checks. "
                "See point-level review details for the reasons."
            )
        else:
            review_status = "VERIFIED_CURRENT"
            evidence_status = "VERIFIED_CURRENT"
            review_message = (
                "All assessed legal sources passed the recorded "
                "topic and current-law verification checks. "
                "This does not establish document compliance."
            )

        legal_research_review = {
            "status": review_status,
            "evidence_status": evidence_status,
            "message": review_message,
            "review_reasons": review_reasons,
            "points": review_details,
        }

        response = {
            "success": True,
            "message": (
                "Document analyzed successfully."
            ),
            "document": {
                "filename": result[
                    "filename"
                ],
                "file_type": result[
                    "file_type"
                ],
                "file_size": result[
                    "file_size"
                ],
                "characters": result[
                    "characters"
                ],
            },
            "analysis": ai_analysis,
            "extraction_review": extraction_review,
            "legal_research_review": legal_research_review,
            "legal_analysis": (
                legal_analysis
            ),
        }

        print(
            "STEP 7 COMPLETE: "
            "Final response ready",
            flush=True,
        )

        print(
            "=== ANALYZE DOCUMENT COMPLETE ===\n",
            flush=True,
        )

        return response

    except HTTPException:
        print(
            "ANALYZE DOCUMENT ERROR: "
            "HTTPException",
            flush=True,
        )
        raise

    except DocumentProcessingError as exc:
        print(
            "ANALYZE DOCUMENT ERROR: "
            f"DocumentProcessingError - {exc}",
            flush=True,
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        print(
            "ANALYZE DOCUMENT ERROR: "
            f"ValueError - {exc}",
            flush=True,
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        print(
            "ANALYZE DOCUMENT ERROR:",
            type(exc).__name__,
            "-",
            str(exc),
            flush=True,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Document analysis failed: "
                f"{str(exc)}"
            ),
        ) from exc

    finally:
        await file.close()

        print(
            "Uploaded file closed.",
            flush=True,
        )
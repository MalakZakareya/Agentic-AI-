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
) -> list[dict[str, Any]]:
    """
    Safely extract document points
    returned by the AI.
    """

    raw_points: Any = ai_analysis.get(
        "points",
        [],
    )

    if not isinstance(
        raw_points,
        list,
    ):
        return []

    typed_points = cast(
        list[Any],
        raw_points,
    )

    points: list[
        dict[str, Any]
    ] = []

    for raw_point in typed_points:
        if not isinstance(
            raw_point,
            dict,
        ):
            continue

        point = cast(
            dict[str, Any],
            raw_point,
        )

        points.append(
            point
        )

    return points


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
            ai_analysis
        )

        print(
            "STEP 4 COMPLETE: Points found -",
            len(points),
            flush=True,
        )

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


        # Summarize legal research verification status.
        agent_results = [
            item.get("legal_research_agent")
            for item in legal_retrieval
            if isinstance(item, dict)
        ]

        agent_results = [
            item for item in agent_results
            if isinstance(item, dict)
        ]

        requires_review = (
            bool(legal_retrieval)
            and (
                len(agent_results) != len(legal_retrieval)
                or any(
                    item.get("decision") != "PROCEED"
                    or item.get("evidence_status") != "VERIFIED_CURRENT"
                    for item in agent_results
                )
            )
        )

        legal_research_review = {
            "status": (
                "HUMAN_REVIEW"
                if requires_review
                else "NOT_ASSESSED"
            ),
            "evidence_status": (
                "REQUIRES_VERIFICATION"
                if requires_review
                else "NOT_ASSESSED"
            ),
            "message": (
                "Human legal review required. Legal sources "
                "have not been confirmed as currently in force."
                if requires_review
                else "No current-law verification is asserted."
            ),
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
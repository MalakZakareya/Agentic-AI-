from io import BytesIO
import re
from typing import Any, cast

from docx import Document
from docx.document import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from fastapi import (
    APIRouter,
    HTTPException,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.draft_service import (
    DraftServiceError,
    get_draft_type,
    validate_draft_details,
)
from services.draft_legal_service import (
    DraftLegalServiceError,
    retrieve_draft_legal_requirements,
)
from services.draft_ai_service import (
    DraftAIServiceError,
    generate_draft,
)
from services.draft_validation_service import (
    DraftValidationError,
    validate_generated_draft,
)


router = APIRouter(
    prefix="/api/v1/draft",
    tags=["Draft"],
)


class DraftCreateRequest(BaseModel):
    draft_type: str = Field(
        ...,
        min_length=1,
    )

    details: dict[str, Any] = Field(
        default_factory=dict,
    )


class DraftDownloadRequest(BaseModel):
    title: str = Field(
        default="Legal Draft",
    )

    draft: str = Field(
        ...,
        min_length=1,
    )

    draft_type_name: str = Field(
        default="Legal Draft",
    )

    verified_sources: Any = Field(
        default_factory=list,
    )


def safe_filename(
    value: str,
) -> str:
    """
    Create a safe filename for the downloaded
    Word document.
    """

    cleaned = re.sub(
        r'[<>:"/\\|?*]',
        "",
        value,
    )

    cleaned = re.sub(
        r"\s+",
        "_",
        cleaned.strip(),
    )

    if not cleaned:
        return "legal_draft"

    return cleaned[:80]



def configure_legal_document_layout(document):
    """Apply A4 layout and consistent default typography."""
    from docx.shared import Cm

    for section in document.sections:
        section.page_width = Cm(21)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15


def apply_legal_paragraph_direction(paragraph):
    """Apply Word RTL settings to paragraphs containing Arabic."""
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    has_arabic = any(
        0x0600 <= ord(character) <= 0x06FF
        for character in (paragraph.text or "")
    )

    if not has_arabic:
        return

    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    properties = paragraph._p.get_or_add_pPr()
    bidi = properties.find(qn("w:bidi"))

    if bidi is None:
        bidi = OxmlElement("w:bidi")
        properties.append(bidi)

    bidi.set(qn("w:val"), "1")

    for run in paragraph.runs:
        run.font.name = "Arial"
        run_properties = run._r.get_or_add_rPr()
        rtl = run_properties.find(qn("w:rtl"))

        if rtl is None:
            rtl = OxmlElement("w:rtl")
            run_properties.append(rtl)

        rtl.set(qn("w:val"), "1")



def prepare_word_draft_text(draft_text, document_title):
    """Remove presentation-only duplication from generated draft text."""
    lines = draft_text.splitlines()
    result = []
    first_content_seen = False

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            result.append(raw_line)
            continue

        if (
            len(line) >= 3
            and set(line) <= {"-", "=", "_"}
        ):
            continue

        if not first_content_seen:
            first_content_seen = True

            normalized_line = " ".join(line.casefold().split())
            normalized_title = " ".join(
                document_title.casefold().split()
            )

            if normalized_line == normalized_title:
                continue

        result.append(raw_line)

    return "\n".join(result)


def is_technical_draft_type_name(type_name):
    """Recognize internal draft identifiers, not descriptive labels."""
    return type_name in {
        "employment_contract",
        "offer_letter",
        "nda",
        "warning_letter",
        "service_agreement",
        "custom",
    }




def add_professional_signature_table(document, blocks):
    """Render signature blocks in a consistently formatted Word table."""
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    if not blocks or len(blocks) > 2:
        raise ValueError("Expected one or two signature blocks.")

    table = document.add_table(
        rows=1,
        cols=len(blocks),
    )

    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    section = document.sections[0]
    available_width = (
        section.page_width
        - section.left_margin
        - section.right_margin
    )
    column_width = int(available_width / len(blocks))

    for column in table.columns:
        column.width = column_width

    row = table.rows[0]
    row_properties = row._tr.get_or_add_trPr()

    if row_properties.find(qn("w:cantSplit")) is None:
        row_properties.append(OxmlElement("w:cantSplit"))

    for index, block in enumerate(blocks):
        cell = row.cells[index]
        cell.width = column_width
        cell.text = ""

        properties = cell._tc.get_or_add_tcPr()
        margins = properties.find(qn("w:tcMar"))

        if margins is None:
            margins = OxmlElement("w:tcMar")
            properties.append(margins)

        for side in ("top", "start", "bottom", "end"):
            margin = margins.find(qn("w:" + side))

            if margin is None:
                margin = OxmlElement("w:" + side)
                margins.append(margin)

            margin.set(qn("w:w"), "140")
            margin.set(qn("w:type"), "dxa")

        for line_index, line in enumerate(block):
            paragraph = (
                cell.paragraphs[0]
                if line_index == 0
                else cell.add_paragraph()
            )

            run = paragraph.add_run(line)
            run.font.name = "Arial"
            run.font.size = Pt(10)

            if line_index == 0:
                run.bold = True

            paragraph.paragraph_format.space_after = Pt(6)
            apply_legal_paragraph_direction(paragraph)

    return table





def extract_signature_blocks(lines, start_index, draft_type):
    """Read complete signature blocks without discarding source text."""
    if draft_type not in {
        "employment_contract",
        "nda",
        "service_agreement",
        "offer_letter",
        "warning_letter",
    }:
        return None

    labels = {
        "employment_contract": ("Employer:", "Employee:"),
        "nda": ("First Party:", "Second Party:"),
        "service_agreement": ("First Party:", "Second Party:"),
        "offer_letter": ("Employee Acceptance:",),
        "warning_letter": (
            "Employee Acknowledgement of Receipt:",
        ),
    }[draft_type]

    index = start_index
    blocks = []

    for label in labels:
        while index < len(lines) and not lines[index].strip():
            index += 1

        if index >= len(lines) or lines[index].strip() != label:
            return None

        block = [lines[index].strip()]
        index += 1

        for prefix in ("Name:", "Signature:", "Date:"):
            if index >= len(lines):
                return None

            value = lines[index].strip()

            if not value.startswith(prefix):
                return None

            block.append(value)
            index += 1

        blocks.append(block)

    if draft_type == "warning_letter":
        if index < len(lines):
            note = lines[index].strip()
            if note.startswith("Acknowledgement confirms receipt only;"):
                blocks[0].append(note)
                index += 1

    return blocks, index


def add_draft_text_to_document(
    document: DocxDocument,
    draft_text: str,
    draft_type: str = "",
) -> None:
    """
    Add generated draft text to the Word document.
    """

    lines = draft_text.splitlines()

    index = 0

    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.strip()

        signature_result = extract_signature_blocks(
            lines,
            index,
            draft_type,
        )

        if signature_result is not None:
            blocks, next_index = signature_result
            add_professional_signature_table(
                document,
                blocks,
            )
            index = next_index
            continue

        index += 1

        if not line:
            document.add_paragraph()
            continue

        is_numbered_heading = bool(
            re.match(
                r"^\d+[\.\)]\s+.+",
                line,
            )
        )

        is_upper_heading = (
            len(line) <= 100
            and line.upper() == line
            and any(
                character.isalpha()
                for character in line
            )
        )

        if (
            is_numbered_heading
            or is_upper_heading
        ):
            paragraph = (
                document.add_paragraph(
                    style="Heading 1"
                )
            )

            run = paragraph.add_run(
                line
            )

            run.bold = True
            run.font.size = Pt(12)

            continue

        paragraph = (
            document.add_paragraph(
                line
            )
        )

        paragraph.paragraph_format.space_after = (
            Pt(6)
        )


def get_verified_sources(
    value: Any,
) -> list[dict[str, Any]]:
    """
    Safely convert verified_sources into a typed
    list of dictionaries.
    """

    if not isinstance(
        value,
        list,
    ):
        return []

    raw_sources = cast(
        list[Any],
        value,
    )

    verified_sources: list[
        dict[str, Any]
    ] = []

    for item in raw_sources:
        if isinstance(
            item,
            dict,
        ):
            verified_sources.append(
                cast(
                    dict[str, Any],
                    item,
                )
            )

    return verified_sources


def create_word_document(
    request: DraftDownloadRequest,
) -> BytesIO:
    """
    Build the generated legal draft as a
    professional Microsoft Word document.
    """

    document: DocxDocument = Document()

    configure_legal_document_layout(document)

    # ---------------------------------------------------------
    # Main title
    # ---------------------------------------------------------

    title = (
        request.title.strip()
        or request.draft_type_name.strip()
        or "Legal Draft"
    )

    title_paragraph = (
        document.add_paragraph(style="Title")
    )

    title_paragraph.alignment = (
        WD_ALIGN_PARAGRAPH.CENTER
    )

    title_run = (
        title_paragraph.add_run(
            title
        )
    )

    title_run.bold = True
    title_run.font.size = Pt(18)

    # ---------------------------------------------------------
    # Draft type subtitle
    # ---------------------------------------------------------

    type_name = (
        request.draft_type_name.strip()
    )

    if (
        type_name
        and type_name.lower()
        != title.lower()
        and not is_technical_draft_type_name(type_name)
    ):
        subtitle = (
            document.add_paragraph()
        )

        subtitle.alignment = (
            WD_ALIGN_PARAGRAPH.CENTER
        )

        subtitle_run = (
            subtitle.add_run(
                type_name
            )
        )

        subtitle_run.italic = True
        subtitle_run.font.size = Pt(10)

    document.add_paragraph()

    # ---------------------------------------------------------
    # Mandatory draft and legal review notice
    # ---------------------------------------------------------

    review_notice = document.add_paragraph()
    review_notice.alignment = WD_ALIGN_PARAGRAPH.CENTER

    review_run = review_notice.add_run(
        "DRAFT FOR REVIEW ONLY - NOT LEGALLY VERIFIED. "
        "Bahrain legal validity and current applicability "
        "have not been independently confirmed. "
        "Complete all missing information and obtain "
        "qualified human legal review before signing."
    )
    review_run.bold = True
    review_run.font.size = Pt(9)

    # ---------------------------------------------------------
    # Draft content
    # ---------------------------------------------------------

    add_draft_text_to_document(
        document=document,
        draft_text=prepare_word_draft_text(
            request.draft,
            title,
        ),
        draft_type=request.draft_type_name.strip().lower(),
    )

    # ---------------------------------------------------------
    # Verified Bahrain legal sources
    # ---------------------------------------------------------

    verified_sources = (
        get_verified_sources(
            request.verified_sources
        )
    )

    if verified_sources:
        document.add_page_break()

        sources_heading = (
            document.add_paragraph()
        )

        sources_run = (
            sources_heading.add_run(
                "Bahrain Legal References - Verification Pending"
            )
        )

        sources_run.bold = True
        sources_run.font.size = Pt(14)

        for index, source in enumerate(
            verified_sources,
            start=1,
        ):
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

            article = str(
                source.get(
                    "article",
                    "",
                )
            ).strip()

            source_url = str(
                source.get(
                    "source_url",
                    "",
                )
            ).strip()

            source_title = str(
                source.get(
                    "title",
                    "",
                )
            ).strip()

            parts: list[str] = []

            if source_title:
                parts.append(
                    source_title
                )

            if law_number:
                law_label = (
                    f"Law {law_number}"
                )

                if year:
                    law_label += (
                        f" / {year}"
                    )

                parts.append(
                    law_label
                )

            if article:
                parts.append(
                    f"Article {article}"
                )

            label = " — ".join(
                parts
            )

            if not label:
                label = (
                    f"Legal Source {index}"
                )

            paragraph = (
                document.add_paragraph(
                    style="List Number"
                )
            )

            label_run = (
                paragraph.add_run(
                    label
                )
            )

            label_run.bold = True

            if source_url:
                url_paragraph = (
                    document.add_paragraph(
                        source_url
                    )
                )

                url_paragraph.paragraph_format.left_indent = (
                    Pt(18)
                )

    # ---------------------------------------------------------
    # Footer note
    # ---------------------------------------------------------

    footer_note = (
        document.sections[0].footer.paragraphs[0]
    )

    footer_note.alignment = (
        WD_ALIGN_PARAGRAPH.CENTER
    )

    footer_run = (
        footer_note.add_run(
            "Generated by Agentic AI"
        )
    )

    footer_run.italic = True
    footer_run.font.size = Pt(8)

    apply_legal_paragraph_direction(footer_note)

    # ---------------------------------------------------------
    # Save Word document to memory
    # ---------------------------------------------------------

    for paragraph in document.paragraphs:
        apply_legal_paragraph_direction(paragraph)

    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    apply_legal_paragraph_direction(paragraph)

    buffer = BytesIO()

    document.save(
        buffer
    )

    buffer.seek(0)

    return buffer


@router.post("/create")
async def create_draft(
    request: DraftCreateRequest,
) -> dict[str, Any]:

    try:
        draft_type = (
            request.draft_type
            .strip()
            .lower()
        )

        draft_config = get_draft_type(
            draft_type
        )

        details = validate_draft_details(
            draft_type=draft_type,
            details=request.details,
        )

        legal_requirements = (
            retrieve_draft_legal_requirements(
                draft_type=draft_type,
                limit_per_query=3,
            )
        )

        ai_result = generate_draft(
            draft_type=draft_type,
            details=details,
            legal_requirements=(
                legal_requirements
            ),
        )

        validated_result = (
            validate_generated_draft(
                ai_result=ai_result,
                legal_requirements=(
                    legal_requirements
                ),
            )
        )

        from services.draft_structure_service import (
            inspect_draft_structure,
        )

        structure_report = inspect_draft_structure(
            draft_type=draft_type,
            draft_text=validated_result["draft"],
        )

        validated_result["structure_validation"] = (
            structure_report
        )

        from services.draft_quality_service import (
            inspect_draft_quality,
        )

        quality_report = inspect_draft_quality(
            draft_text=validated_result["draft"],
            structure_report=structure_report,
        )

        validated_result["quality_validation"] = (
            quality_report
        )

        structure_status = structure_report.get("status")

        acceptable_statuses = (
            {"UNSTRUCTURED_REVIEW_REQUIRED"}
            if draft_type == "custom"
            else {"STRUCTURALLY_PRESENT"}
        )

        needs_user_input = (
            structure_status == "NEEDS_USER_INPUT"
            and draft_type != "custom"
        )

        if (
            structure_status not in acceptable_statuses
            and not needs_user_input
        ):
            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "The generated draft did not pass "
                        "structural acceptance checks."
                    ),
                    "structure_validation": structure_report,
                },
            )

        return {
            "success": True,
            "draft_status": structure_status,
            "ready_for_signing": False,
            "required_user_input_sections": (
                structure_report.get(
                    "placeholder_sections", []
                )
                if needs_user_input
                else []
            ),
            "message": (
                "Draft created successfully."
            ),
            "draft_type": draft_type,
            "draft_type_name": (
                draft_config["name"]
            ),
            "legal_requirements_retrieved": (
                len(legal_requirements)
            ),
            "result": validated_result,
        }

    except DraftServiceError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except DraftLegalServiceError as exc:
        raise HTTPException(
            status_code=500,
            detail="Draft processing is temporarily unavailable.",
        ) from exc

    except DraftAIServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail="AI draft generation is temporarily unavailable.",
        ) from exc

    except DraftValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail="Draft processing is temporarily unavailable.",
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Draft creation failed unexpectedly.",
        ) from exc


@router.post("/download/word")
async def download_draft_word(
    request: DraftDownloadRequest,
) -> StreamingResponse:
    """
    Download a generated legal draft
    as a Microsoft Word document.
    """

    try:
        word_buffer = (
            create_word_document(
                request
            )
        )

        filename = (
            safe_filename(
                request.title
                or request.draft_type_name
            )
            + ".docx"
        )

        return StreamingResponse(
            word_buffer,
            media_type=(
                "application/"
                "vnd.openxmlformats-"
                "officedocument."
                "wordprocessingml.document"
            ),
            headers={
                "Content-Disposition": (
                    'attachment; filename="'
                    + filename
                    + '"'
                )
            },
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Word document creation "
                f"failed: {str(exc)}"
            ),
        ) from exc

import json
import re
from pathlib import Path
from typing import Any, cast


SOURCE = Path(
    "knowledge/bahrain/laws/sources/civil_law_review.json"
)

OUTPUT = Path(
    "knowledge/bahrain/laws/sources/civil_law_cleaned_review.json"
)

REPORT = Path(
    "knowledge/bahrain/laws/sources/civil_law_cleaning_report.json"
)

# Detect likely section headings.
# A match is only a candidate for removal, not proof.
HEADING_PATTERN = re.compile(
    r"(?:\s*\*\s*)*"
    r"(?:الباب|الفصل|الفرع|الكتاب)\s+"
    r"(?:الأول|الثاني|الثالث|الرابع|الخامس|"
    r"السادس|السابع|الثامن|التاسع|العاشر)"
    r"(?:\s*[-–:]?\s*[^.]{0,150})?$"
)

# Special heading already observed after Article 190.
ARTICLE_190_HEADING = re.compile(
    r"\s*\(ثانيا\)\s*الفضالة\s*:\s*$"
)


def main() -> None:
    with SOURCE.open("r", encoding="utf-8") as f:
        raw: Any = json.load(f)

    data = cast(dict[str, Any], raw)
    regulations = cast(
        list[dict[str, Any]],
        data["regulations"]
    )

    cleaned_count = 0
    report: list[dict[str, object]] = []

    for item in regulations:
        number = int(item["article"])
        original = str(item["text"])
        updated = original

        if number == 190:
            updated = ARTICLE_190_HEADING.sub(
                "",
                updated
            ).strip()

        else:
            match = HEADING_PATTERN.search(updated)

            if match is not None:
                # Only remove when heading follows a sentence end.
                prefix = updated[:match.start()].rstrip()

                if prefix.endswith(".") or prefix.endswith("۔"):
                    updated = prefix

        if updated != original:
            cleaned_count += 1

            report.append({
                "article": number,
                "removed_text": original[len(updated):].strip(),
                "original_length": len(original),
                "cleaned_length": len(updated)
            })

            item["text"] = updated
            item["notes"] = (
                str(item.get("notes", ""))
                + " Section heading removed in review copy; "
                "pending manual verification."
            )

    OUTPUT.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    REPORT.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print("=== CIVIL LAW CLEANING ===")
    print("Total articles:", len(regulations))
    print("Articles changed:", cleaned_count)
    print("Cleaned review file:", OUTPUT)
    print("Cleaning report:", REPORT)

    print()
    print("=== REMOVED TEXT ===")

    for record in report:
        print(
            f"Article {record['article']}: "
            f"{record['removed_text']}"
        )

    print()
    print("Original review JSON was not modified.")
    print("civil_law.json was not modified.")


if __name__ == "__main__":
    main()

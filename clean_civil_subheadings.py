
import json
import re
from pathlib import Path
from typing import Any, cast


BASE = Path("knowledge/bahrain/laws/sources")

SOURCE = BASE / "civil_law_cleaned_review.json"
OUTPUT = BASE / "civil_law_final_review.json"
REPORT = BASE / "civil_law_subheading_report.json"

# Known headings observed in the extraction.
EXACT_SUFFIXES: dict[int, str] = {
    16: "2 - الشخص الاعتباري",
    46: "صور خاصة في التعاقد العقد الابتدائي",
}

# Subheadings that follow the last sentence of an article.
SUBHEADING_PATTERN = re.compile(
    r"\s+(?:"
    r"\(\s*(?:أولا|أولاً|ثانيا|ثانياً|ثالثا|ثالثاً|"
    r"رابعا|رابعاً|خامسا|خامساً|سادسا|سادساً)\s*\)"
    r"|"
    r"\d+\s*[-–]?\s+"
    r"|"
    r"(?:النيابة في التعاقد|شكل العقد|"
    r"الإيجاب|القبول|التدليس|الإكراه|"
    r"الاستغلال|الغبن|التعاقد بالعربون|"
    r"التعاقد بالمزايدة|التعاقد بالإذعان|"
    r"الوعد بالعقد|التأمين من الحريق)"
    r")"
    r".*$"
)


def main() -> None:
    with SOURCE.open("r", encoding="utf-8") as file:
        raw: Any = json.load(file)

    data = cast(dict[str, Any], raw)

    regulations = cast(
        list[dict[str, Any]],
        data["regulations"]
    )

    report: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []

    for item in regulations:
        number = int(item["article"])
        original = str(item["text"])
        updated = original

        if number in EXACT_SUFFIXES:
            suffix = EXACT_SUFFIXES[number]

            if original.endswith(suffix):
                updated = original[:-len(suffix)].rstrip()

        elif original.endswith(":"):
            match = SUBHEADING_PATTERN.search(original)

            if match is not None:
                prefix = original[:match.start()].rstrip()

                # Only remove a suffix after a sentence.
                if prefix.endswith("."):
                    updated = prefix

        if updated != original:
            removed = original[len(updated):].strip()

            report.append({
                "article": number,
                "removed_text": removed,
                "before_length": len(original),
                "after_length": len(updated)
            })

            item["text"] = updated
            item["notes"] = (
                str(item.get("notes", ""))
                + " Subheading removed in review copy; "
                "pending manual verification."
            )

        elif original.endswith(":"):
            candidates.append({
                "article": number,
                "ending": original[-160:]
            })

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
            {
                "removed": report,
                "remaining_candidates": candidates
            },
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print("=== SUBHEADING CLEANING ===")
    print("Total articles:", len(regulations))
    print("Articles cleaned:", len(report))
    print("Remaining candidates:", len(candidates))

    print()
    print("=== REMOVED SUBHEADINGS ===")

    for entry in report:
        print(
            f"Article {entry['article']}: "
            f"{entry['removed_text']}"
        )

    print()
    print("=== REMAINING CANDIDATES ===")

    for entry in candidates:
        print(
            f"Article {entry['article']}: "
            f"{entry['ending']}"
        )

    print()
    print("Review file:", OUTPUT)
    print("Report:", REPORT)
    print("Original JSON files were not modified.")


if __name__ == "__main__":
    main()

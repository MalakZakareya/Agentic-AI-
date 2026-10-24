
import json
import re
from pathlib import Path
from typing import Any, cast


FILE = Path(
    "knowledge/bahrain/laws/sources/civil_law_review.json"
)


def main() -> None:
    # ============================================================
    # 1. LOAD CIVIL LAW REVIEW DATA
    # ============================================================

    with FILE.open("r", encoding="utf-8") as f:
        raw_data: Any = json.load(f)

    data = cast(dict[str, Any], raw_data)

    regulations = cast(
        list[dict[str, Any]],
        data["regulations"]
    )

    # ============================================================
    # 2. BASIC VALIDATION
    # ============================================================

    print("=== CIVIL LAW VALIDATION ===")
    print("Total articles:", len(regulations))

    numbers: list[int] = [
        int(item["article"])
        for item in regulations
    ]

    expected: set[int] = set(range(1, 1055))
    found: set[int] = set(numbers)

    missing: list[int] = sorted(expected - found)

    print("Missing articles:", missing)
    print("Duplicate numbers:", len(numbers) - len(found))

    empty: list[int] = [
        number
        for number, item in zip(numbers, regulations)
        if not str(item["text"]).strip()
    ]

    print("Empty articles:", empty)

    short: list[tuple[int, int]] = [
        (number, len(str(item["text"])))
        for number, item in zip(numbers, regulations)
        if len(str(item["text"])) < 50
    ]

    long: list[tuple[int, int]] = [
        (number, len(str(item["text"])))
        for number, item in zip(numbers, regulations)
        if len(str(item["text"])) > 3000
    ]

    print("Short articles (<50 chars):", short)
    print("Long articles (>3000 chars):", long)

    # ============================================================
    # 3. SELECTED ARTICLE TEXTS
    # ============================================================

    print()
    print("=== SELECTED ARTICLE TEXTS ===")

    selected_numbers: list[int] = [
        1, 189, 190, 191, 447, 448, 911, 1054
    ]

    for number in selected_numbers:
        item: dict[str, Any] | None = next(
            (
                record
                for record in regulations
                if int(record["article"]) == number
            ),
            None
        )

        if item is None:
            print(f"\nArticle {number}: MISSING")
            continue

        article_text: str = str(item["text"])

        print(f"\nARTICLE {number}")
        print("Length:", len(article_text))
        print("Beginning:", article_text[:350])
        print("Ending:", article_text[-200:])
        print("Notes:", item.get("notes", ""))

    # ============================================================
    # 4. CHECK POSSIBLE SECTION HEADINGS
    # ============================================================

    print()
    print("=== POSSIBLE SECTION HEADINGS ===")

    heading_pattern = re.compile(
        r"(?:الباب|الفصل|الفرع|الكتاب)\s+"
        r"(?:الأول|الثاني|الثالث|الرابع|الخامس|"
        r"السادس|السابع|الثامن|التاسع|العاشر|\d+)"
    )

    flagged: list[int] = []

    for item in regulations:
        article_text = str(item["text"])

        heading_matches: list[re.Match[str]] = list(
            heading_pattern.finditer(article_text)
        )

        if heading_matches:
            article_number: int = int(item["article"])

            flagged.append(article_number)

            previews: list[str] = [
                article_text[
                    max(0, match.start() - 40):
                    min(len(article_text), match.end() + 70)
                ]
                for match in heading_matches
            ]

            print(f"Article {article_number}:", previews)

    print()
    print(
        "Articles containing possible headings:",
        len(flagged)
    )
    print("Article numbers:", flagged)

    # ============================================================
    # 5. FINAL VALIDATION SUMMARY
    # ============================================================

    print()
    print("=== FINAL STATUS ===")

    basic_validation_passed: bool = (
        len(regulations) == 1054
        and not missing
        and len(numbers) == len(found)
        and not empty
    )

    if basic_validation_passed:
        print("PASS: Basic structural validation.")
    else:
        print("FAIL: Structural issues detected.")

    print(
        "Legal accuracy, article boundaries, and amendments "
        "still require review."
    )

    print()
    print("=== SUMMARY ===")
    print("Total articles:", len(regulations))
    print("Missing articles:", len(missing))
    print("Empty articles:", len(empty))
    print("Short articles:", len(short))
    print("Long articles:", len(long))
    print("Articles with possible section headings:", len(flagged))

    print()
    print("No JSON files were modified.")


if __name__ == "__main__":
    main()

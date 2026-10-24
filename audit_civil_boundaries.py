
import json
import re
from pathlib import Path
from typing import Any, cast


FILE = Path(
    "knowledge/bahrain/laws/sources/"
    "civil_law_cleaned_review.json"
)

REFERENCE_PATTERN = re.compile(
    r"(?<!\w)(?:ال)?مادة\s*"
    r"\(\s*([0-9\u0660-\u0669]+)\s*\)"
)

HEADING_PATTERN = re.compile(
    r"(?:الباب|الفصل|الفرع|الكتاب)\s+"
    r"(?:الأول|الثاني|الثالث|الرابع|الخامس|"
    r"السادس|السابع|الثامن|التاسع|العاشر)"
)


def main() -> None:
    with FILE.open("r", encoding="utf-8") as f:
        raw: Any = json.load(f)

    data = cast(dict[str, Any], raw)

    regulations = cast(
        list[dict[str, Any]],
        data["regulations"]
    )

    suspicious: list[tuple[int, str]] = []
    references: list[tuple[int, int]] = []

    print("=== CIVIL LAW BOUNDARY AUDIT ===")

    for item in regulations:
        number = int(item["article"])
        text = str(item["text"]).strip()

        if not text:
            suspicious.append((number, "Empty text"))
            continue

        if HEADING_PATTERN.search(text):
            suspicious.append(
                (number, "Possible section heading remains")
            )

        if len(text) > 2000:
            suspicious.append(
                (number, f"Unusually long: {len(text)} chars")
            )

        if not text.endswith((".", "؟", "!", "۔")):
            suspicious.append(
                (number, "Unusual ending")
            )

        for match in REFERENCE_PATTERN.finditer(text):
            referenced_number = int(match.group(1))
            references.append((number, referenced_number))

    print("Total articles:", len(regulations))
    print("Internal article references:", len(references))
    print("Flagged observations:", len(suspicious))

    print()
    print("=== FLAGGED ARTICLES ===")

    for number, reason in suspicious:
        print(f"Article {number}: {reason}")

    print()
    print("=== FORWARD REFERENCES ===")

    forward = [
        (source, target)
        for source, target in references
        if target > source
    ]

    print("Count:", len(forward))

    for source, target in forward[:40]:
        print(f"Article {source} references Article {target}")

    print()
    print("=== FINAL SUMMARY ===")
    print("Articles checked:", len(regulations))
    print("Flagged observations:", len(suspicious))
    print("Forward references:", len(forward))
    print("Article 190 still requires independent verification.")
    print("No files were modified.")


if __name__ == "__main__":
    main()

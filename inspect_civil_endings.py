
import json
from pathlib import Path
from typing import Any, cast


FILE = Path(
    "knowledge/bahrain/laws/sources/"
    "civil_law_cleaned_review.json"
)


def main() -> None:
    with FILE.open("r", encoding="utf-8") as f:
        raw: Any = json.load(f)

    data = cast(dict[str, Any], raw)

    regulations = cast(
        list[dict[str, Any]],
        data["regulations"]
    )

    flagged: list[tuple[int, str]] = []

    for item in regulations:
        number = int(item["article"])
        article_text = str(item["text"]).strip()

        if not article_text:
            flagged.append((number, "EMPTY"))
            continue

        if not article_text.endswith((".", "؟", "!", "۔")):
            flagged.append((number, article_text[-120:]))

    print("=== UNUSUAL ARTICLE ENDINGS ===")
    print("Total flagged:", len(flagged))

    for number, ending in flagged:
        print(f"\nArticle {number}")
        print("Ending:", ending)

    print()
    print("=== ENDING CHARACTER FREQUENCY ===")

    ending_counts: dict[str, int] = {}

    for item in regulations:
        article_text = str(item["text"]).strip()

        if article_text:
            last_char = article_text[-1]
            ending_counts[last_char] = (
                ending_counts.get(last_char, 0) + 1
            )

    for char, count in sorted(
        ending_counts.items(),
        key=lambda entry: entry[1],
        reverse=True
    ):
        print(repr(char), ":", count)

    print()
    print("No files were modified.")


if __name__ == "__main__":
    main()

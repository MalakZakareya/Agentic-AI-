
import json
from pathlib import Path
from typing import Any, cast


BASE = Path("knowledge/bahrain/laws/sources")

SOURCE = BASE / "civil_law_final_review.json"
OUTPUT = BASE / "civil_law_verified_structure.json"

# Exact trailing headings observed in the previous report.
HEADINGS: dict[int, str] = {
    30: "(أولا) أركان العقد : 1 - الرضاء :",
    31: "( أ ) التعبير عن الإرادة :",
    39: "القبول :",
    43: "ارتباط الإيجاب بالقبول :",
    51: "التعاقد بالعربون :",
    56: "التعاقد بالإذعان :",
    70: "( ب ) سلامة الرضاء :",
    71: "الأهلية في التعاقد :",
    83: "عيوب الرضاء : الغلط :",
    93: "الإكراه :",
    95: "الاستغلال :",
    97: "الغبن :",
    102: "2 - المحل :",
    117: "2 - العقد الباطل :",
    151: "الوعد بجائزة للجمهور :",
    879: "2 إثبات الحيازة :",
}


def main() -> None:
    with SOURCE.open("r", encoding="utf-8") as file:
        raw: Any = json.load(file)

    data = cast(dict[str, Any], raw)

    regulations = cast(
        list[dict[str, Any]],
        data["regulations"]
    )

    by_number: dict[int, dict[str, Any]] = {
        int(item["article"]): item
        for item in regulations
    }

    if len(regulations) != 1054 or len(by_number) != 1054:
        raise ValueError("Unexpected article count or duplicates.")

    for number, heading in HEADINGS.items():
        item = by_number.get(number)

        if item is None:
            raise ValueError(f"Article {number} is missing.")

        original = str(item["text"])

        if not original.endswith(heading):
            raise ValueError(
                f"Article {number} does not end with expected heading."
            )

        cleaned = original[:-len(heading)].rstrip()

        if not cleaned.endswith((".", "؟", "!", "۔")):
            raise ValueError(
                f"Article {number} has an unexpected ending."
            )

        item["text"] = cleaned
        item["notes"] = (
            str(item.get("notes", ""))
            + " Final trailing heading removed; "
            "pending legal verification."
        )

    OUTPUT.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print("=== FINAL HEADING CLEANUP ===")
    print("Total articles:", len(regulations))
    print("Additional headings removed:", len(HEADINGS))

    unusual = [
        int(item["article"])
        for item in regulations
        if not str(item["text"]).strip().endswith(
            (".", "؟", "!", "۔")
        )
    ]

    print("Articles with unusual endings:", unusual)
    print("Output:", OUTPUT)
    print()
    print("No original legal knowledge files were modified.")
    print("Article 190 still requires independent verification.")


if __name__ == "__main__":
    main()

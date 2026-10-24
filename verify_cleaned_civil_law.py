
import json
from pathlib import Path
from typing import Any, cast


BASE = Path("knowledge/bahrain/laws/sources")

ORIGINAL = BASE / "civil_law_review.json"
CLEANED = BASE / "civil_law_cleaned_review.json"
REPORT = BASE / "civil_law_cleaning_report.json"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    original_data = cast(
        dict[str, Any],
        load_json(ORIGINAL)
    )

    cleaned_data = cast(
        dict[str, Any],
        load_json(CLEANED)
    )

    report = cast(
        list[dict[str, Any]],
        load_json(REPORT)
    )

    original = cast(
        list[dict[str, Any]],
        original_data["regulations"]
    )

    cleaned = cast(
        list[dict[str, Any]],
        cleaned_data["regulations"]
    )

    original_by_number = {
        int(item["article"]): item
        for item in original
    }

    cleaned_by_number = {
        int(item["article"]): item
        for item in cleaned
    }

    errors: list[str] = []
    changed: list[int] = []

    expected_numbers = set(range(1, 1055))

    if len(original) != 1054 or len(cleaned) != 1054:
        errors.append("Unexpected article count.")

    if set(original_by_number) != expected_numbers:
        errors.append("Original article numbers are incomplete.")

    if set(cleaned_by_number) != expected_numbers:
        errors.append("Cleaned article numbers are incomplete.")

    if len(original_by_number) != len(original):
        errors.append("Duplicate original article numbers.")

    if len(cleaned_by_number) != len(cleaned):
        errors.append("Duplicate cleaned article numbers.")

    report_numbers: list[int] = [
        int(record["article"])
        for record in report
    ]

    if len(set(report_numbers)) != len(report_numbers):
        errors.append("Duplicate cleaning report entries.")

    report_by_number = {
        int(record["article"]): record
        for record in report
    }

    for number in sorted(
        set(original_by_number) & set(cleaned_by_number)
    ):
        before = original_by_number[number]
        after = cleaned_by_number[number]

        old_text = str(before["text"])
        new_text = str(after["text"])

        if not new_text.strip():
            errors.append(f"Article {number} is empty.")

        if new_text != old_text:
            changed.append(number)

            if number not in report_by_number:
                errors.append(
                    f"Article {number} changed without report."
                )

            # Cleaning should remove a suffix only.
            if not old_text.startswith(new_text):
                errors.append(
                    f"Article {number} changed internally."
                )

            removed = old_text[len(new_text):].strip()

            record = report_by_number.get(number)

            if record is not None:
                if removed != str(record["removed_text"]):
                    errors.append(
                        f"Article {number} report mismatch."
                    )

        # Metadata must remain unchanged except notes.
        for key, value in before.items():
            if key in ("text", "notes"):
                continue

            if after.get(key) != value:
                errors.append(
                    f"Article {number}: metadata changed ({key})."
                )

    if set(changed) != set(report_numbers):
        errors.append(
            "Changed articles do not match cleaning report."
        )

    print("=== CLEANED CIVIL LAW VERIFICATION ===")
    print("Original articles:", len(original))
    print("Cleaned articles:", len(cleaned))
    print("Changed articles:", len(changed))
    print("Cleaning report entries:", len(report))
    print("Errors:", len(errors))

    print()
    print("=== IMPORTANT ARTICLES ===")

    for number in [8, 190, 447, 1054]:
        item = cleaned_by_number.get(number)

        if item is not None:
            print(f"\nArticle {number}:")
            print("Text:", str(item["text"])[-350:])
            print("Notes:", item.get("notes", ""))

    print()
    print("=== FINAL RESULT ===")

    if errors:
        print("FAIL")

        for error in errors:
            print("-", error)
    else:
        print("PASS: Cleaning changes are structurally consistent.")

    print(
        "This does not verify legal accuracy, amendments, "
        "or whether every article boundary is correct."
    )

    print()
    print("No files were modified.")


if __name__ == "__main__":
    main()


import json
import re
from pathlib import Path
from typing import TypedDict

from bs4 import BeautifulSoup


class ArticlePosition(TypedDict):
    number: int
    start: int
    end_of_heading: int


SOURCE_FILE = Path(
    "knowledge/bahrain/laws/sources/civil_law.html"
)

OUTPUT_FILE = Path(
    "knowledge/bahrain/laws/sources/civil_law_review.json"
)

SOURCE_URL = (
    "https://www.lloc.gov.bh/Legislation/HTM/L1901"
)

LAW_TITLE = "Bahrain Civil Code"
LAW_NUMBER = "19"
LAW_YEAR = 2001
EXPECTED_ARTICLES = 1054


def extract_text() -> str:
    html = SOURCE_FILE.read_bytes().decode("utf-8-sig")

    soup = BeautifulSoup(html, "html.parser")

    for element in soup(["style", "script"]):
        element.decompose()

    text = soup.get_text(" ", strip=True)

    text = re.sub(
        r"[\u0640\u200b-\u200f\ufeff]",
        "",
        text
    )

    text = re.sub(r"\s+", " ", text)

    return text


def find_article_positions(text: str) -> list[ArticlePosition]:
    normal_pattern = re.compile(
        r"(?<!\w)(?:ال)?مادة\s*"
        r"\(\s*([0-9\u0660-\u0669]+)\s*\)"
    )

    # The downloaded source contains "مادة (19.)"
    # between Articles 189 and 191.
    malformed_190_pattern = re.compile(
        r"(?<!\w)مادة\s*\(\s*19\.\s*\)"
    )

    candidates: list[ArticlePosition] = []

    for match in normal_pattern.finditer(text):
        candidates.append({
            "number": int(match.group(1)),
            "start": match.start(),
            "end_of_heading": match.end()
        })

    for match in malformed_190_pattern.finditer(text):
        candidates.append({
            "number": 190,
            "start": match.start(),
            "end_of_heading": match.end()
        })

    candidates.sort(key=lambda item: item["start"])

    articles: list[ArticlePosition] = []
    expected = 1

    for candidate in candidates:
        if candidate["number"] == expected:
            articles.append(candidate)
            expected += 1

        if expected > EXPECTED_ARTICLES:
            break

    numbers = [article["number"] for article in articles]

    if numbers != list(range(1, EXPECTED_ARTICLES + 1)):
        missing = sorted(
            set(range(1, EXPECTED_ARTICLES + 1))
            - set(numbers)
        )

        raise ValueError(
            f"Article sequence is incomplete. Missing: {missing}"
        )

    return articles


def create_review_data(
    text: str,
    positions: list[ArticlePosition]
) -> dict[str, object]:

    regulations: list[dict[str, object]] = []

    for index, article in enumerate(positions):
        number = article["number"]

        start = article["end_of_heading"]

        if index + 1 < len(positions):
            end = positions[index + 1]["start"]
        else:
            end = len(text)

        article_text = text[start:end].strip()

        if not article_text:
            raise ValueError(
                f"Article {number} has empty text."
            )

        notes = (
            "Source heading appears as مادة (19.); "
            "article number requires independent verification."
            if number == 190
            else "Extracted from source HTML; pending review."
        )

        regulations.append({
            "id": f"BH-CIVIL-19-2001-ARTICLE-{number}",
            "source_id": "BH-CIVIL-19-2001",
            "title": LAW_TITLE,
            "law_number": LAW_NUMBER,
            "year": LAW_YEAR,
            "category": "civil_law",
            "article": str(number),
            "text": article_text,
            "source_url": SOURCE_URL,
            "source_type": "official_html",
            "effective_status": "unverified",
            "notes": notes
        })

    return {
        "jurisdiction": "Kingdom of Bahrain",
        "last_updated": None,
        "regulations": regulations
    }


def main() -> None:
    print("Reading Bahrain Civil Code...")

    text = extract_text()

    print("Extracted characters:", len(text))

    positions = find_article_positions(text)

    print("Sequential articles found:", len(positions))

    data = create_review_data(text, positions)

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print()
    print("=== IMPORT REVIEW SUMMARY ===")
    print("Articles extracted:", len(positions))
    print("First article:", positions[0]["number"])
    print("Last article:", positions[-1]["number"])
    print("Article 190: Requires verification")
    print("Review file:", OUTPUT_FILE)
    print()
    print("Original regulations.json was NOT modified.")
    print("civil_law.json was NOT modified.")


if __name__ == "__main__":
    main()


from pathlib import Path
from collections import Counter
from typing import TypedDict
import re

from bs4 import BeautifulSoup


class ArticlePosition(TypedDict):
    number: int
    start: int | None
    end_of_heading: int | None


# ============================================================
# 1. READ CIVIL LAW HTML
# ============================================================

path = Path("knowledge/bahrain/laws/sources/civil_law.html")

html = path.read_bytes().decode("utf-8-sig")

soup = BeautifulSoup(html, "html.parser")

for element in soup(["style", "script"]):
    element.decompose()

text = soup.get_text(" ", strip=True)

# Remove Arabic tatweel and invisible formatting characters
text = re.sub(r"[\u0640\u200b-\u200f\ufeff]", "", text)

# Normalize whitespace
text = re.sub(r"\s+", " ", text)


# ============================================================
# 2. FIND POSSIBLE ARTICLE HEADINGS
# ============================================================

# Matches:
# مادة (1)
# مادة ( 20 )
# المادة (100)

article_pattern = (
    r"(?<!\w)(?:ال)?مادة\s*"
    r"\(\s*([0-9\u0660-\u0669]+)\s*\)"
)

matches = list(re.finditer(article_pattern, text))

print("Total possible article references:", len(matches))

print()
print("FIRST 15 MATCHES:")

for match in matches[:15]:
    print(
        "Article:", match.group(1),
        "| Preview:", text[match.start():match.start() + 110]
    )

print()
print("LAST 10 MATCHES:")

for match in matches[-10:]:
    print(
        "Article:", match.group(1),
        "| Preview:", text[match.start():match.start() + 110]
    )


# ============================================================
# 3. VALIDATE ARTICLE NUMBERS
# ============================================================

article_numbers: list[int] = [
    int(match.group(1))
    for match in matches
]

counts = Counter(article_numbers)

expected_numbers = set(range(1, 1055))
found_numbers = set(article_numbers)

missing = sorted(expected_numbers - found_numbers)

duplicates = sorted(
    number
    for number, count in counts.items()
    if count > 1
)

print()
print("=== ARTICLE VALIDATION ===")

print("Total matches:", len(article_numbers))
print("Unique article numbers:", len(found_numbers))
print("Missing article numbers:", missing)
print("Repeated article numbers:", duplicates)

if article_numbers:
    print("Highest article number:", max(article_numbers))
else:
    print("Highest article number: None")


# ============================================================
# 4. FIND OUT-OF-ORDER REFERENCES
# ============================================================

print()
print("=== OUT-OF-ORDER REFERENCES ===")

previous = 0

for match in matches:
    number = int(match.group(1))

    if number <= previous:
        print(
            f"Found {number} after {previous}:",
            text[
                max(0, match.start() - 40):
                match.start() + 80
            ]
        )

    previous = number


# ============================================================
# 5. INVESTIGATE ARTICLE 190
# ============================================================

print()
print("=== INVESTIGATE ARTICLE 190 ===")

for keyword in ["189", "190", "191"]:
    investigation_pattern = (
        r"(?<!\w)(?:ال)?مادة\s*\(?\s*"
        + keyword
        + r"\s*\)?"
    )

    results = list(re.finditer(investigation_pattern, text))

    print(f"\nArticle {keyword}: {len(results)} matches")

    for result in results[:3]:
        start = max(0, result.start() - 100)
        end = min(len(text), result.end() + 250)

        print(text[start:end])
        print("---")

# Show malformed heading between articles 189 and 191
malformed_pattern = r"(?<!\w)مادة\s*\(\s*19\.\s*\)"

malformed_matches = list(re.finditer(malformed_pattern, text))

print()
print("Possible malformed Article 190 headings:", len(malformed_matches))

for match in malformed_matches:
    print(
        text[
            max(0, match.start() - 100):
            min(len(text), match.end() + 250)
        ]
    )


# ============================================================
# 6. INVESTIGATE ARTICLE 448
# ============================================================

print()
print("=== INVESTIGATE ARTICLE 448 ===")

for number in [447, 448, 449, 910, 911, 912]:
    investigation_pattern = (
        r"(?<!\w)(?:ال)?مادة\s*"
        r"\(\s*" + str(number) + r"\s*\)"
    )

    results = list(re.finditer(investigation_pattern, text))

    print(f"\nArticle {number}: {len(results)} matches")

    for result in results[:2]:
        print("Position:", result.start())
        print(text[result.start():result.start() + 180])
        print("---")


# ============================================================
# 7. SEQUENTIAL ARTICLE EXTRACTION
# ============================================================

print()
print("=== SEQUENTIAL ARTICLE EXTRACTION ===")

articles: list[ArticlePosition] = []

expected = 1

for match in matches:
    number = int(match.group(1))

    if number == expected:
        articles.append({
            "number": number,
            "start": match.start(),
            "end_of_heading": match.end()
        })

        expected += 1

    elif expected == 190 and number == 191:
        # The source appears to contain "مادة ( 19. )"
        # where Article 190 would normally appear.
        # Keep Article 190 unverified until checked.

        print("Article 190 requires manual verification.")

        articles.append({
            "number": 190,
            "start": None,
            "end_of_heading": None
        })

        articles.append({
            "number": 191,
            "start": match.start(),
            "end_of_heading": match.end()
        })

        expected = 192


# ============================================================
# 8. VALIDATE SEQUENTIAL EXTRACTION
# ============================================================

print()
print("Sequential article records:", len(articles))
print("Last expected article:", expected - 1)

missing_positions: list[int] = [
    item["number"]
    for item in articles
    if item["start"] is None
]

print(
    "Articles requiring manual verification:",
    missing_positions
)

print()
print("=== SELECTED ARTICLE PREVIEWS ===")

selected_numbers = [1, 189, 190, 191, 447, 448, 911, 1054]

for number in selected_numbers:
    article: ArticlePosition | None = next(
        (
            item
            for item in articles
            if item["number"] == number
        ),
        None
    )

    if article is None:
        print(f"Article {number}: NOT FOUND")
        continue

    start_position: int | None = article["start"]

    if start_position is None:
        print(f"Article {number}: NOT VERIFIED")
        continue

    print(
        f"Article {number}:",
        text[start_position:start_position + 120]
    )


# ============================================================
# 9. FINAL VALIDATION SUMMARY
# ============================================================

print()
print("=== FINAL SUMMARY ===")

print("Source file:", path.name)
print("Extracted text characters:", len(text))
print("Possible references:", len(matches))
print("Sequential article records:", len(articles))
print("Unverified articles:", missing_positions)

if len(articles) == 1054 and missing_positions == [190]:
    print("STATUS: Sequence check passed with one unverified article.")
else:
    print("STATUS: Manual review required.")

print()
print("No JSON files were modified.")

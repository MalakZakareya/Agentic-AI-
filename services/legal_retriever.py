from functools import lru_cache
import json
import re
from pathlib import Path
from typing import Any, cast


REGULATIONS_FILE = (
    Path(__file__).resolve().parent.parent
    / "knowledge"
    / "bahrain"
    / "regulations.json"
)


STOP_WORDS = {
    "في",
    "من",
    "على",
    "إلى",
    "الى",
    "عن",
    "أن",
    "ان",
    "إن",
    "هذا",
    "هذه",
    "ذلك",
    "تلك",
    "بين",
    "أو",
    "او",
    "و",
    "ثم",
    "مع",
    "كل",
    "أي",
    "اي",
    "هو",
    "هي",
    "كان",
    "تكون",
    "يكون",
    "تم",
    "يتم",
    "قد",
    "ما",
    "لا",
    "the",
    "a",
    "an",
    "of",
    "for",
    "to",
    "in",
    "and",
    "or",
    "with",
}


# -------------------------------------------------
# Bilingual Bahrain legal concept map
# -------------------------------------------------

LEGAL_CONCEPTS: dict[str, list[str]] = {

    "employment_contract": [
        "employment contract",
        "work contract",
        "labour contract",
        "labor contract",
        "employment agreement",
        "employment contract requirements",
        "employment contract details",
        "employment contract terms",
        "written employment contract",
        "عقد العمل",
        "عقد عمل",
        "عقد العمل الفردي",
        "بيانات عقد العمل",
        "البيانات الجوهرية",
        "البيانات الجوهرية لعقد العمل",
        "تحرير عقد العمل",
        "عقد العمل ثابتاً بالكتابة",
        "عقد العمل ثابتا بالكتابة",
        "محرراً باللغة العربية",
        "محررا باللغة العربية",
        "نسختين لكل طرف",
        "مدة العقد",
    ],

    "wages": [
        "wage",
        "wages",
        "salary",
        "pay",
        "payment of salary",
        "remuneration",
        "الأجر",
        "الاجر",
        "الأجور",
        "الاجور",
        "الراتب",
        "راتب",
        "أجر",
        "اجر",
        "بدل",
        "العلاوات",
        "المكافآت",
    ],

      "contract_formation": [
        "contract formation",
        "formation of contract",
        "forming a contract",
        "\u062a\u0643\u0648\u064a\u0646 \u0627\u0644\u0639\u0642\u062f",
        "\u0627\u0646\u0639\u0642\u0627\u062f \u0627\u0644\u0639\u0642\u062f",
        "\u0625\u0628\u0631\u0627\u0645 \u0627\u0644\u0639\u0642\u062f",
    ],

    "salary_increase": [
        "salary increase",
        "wage increase",
        "salary raise",
        "pay raise",
        "annual increment",
        "\u0632\u064a\u0627\u062f\u0629 \u0627\u0644\u0631\u0627\u062a\u0628",
        "\u0632\u064a\u0627\u062f\u0629 \u0627\u0644\u0623\u062c\u0631",
        "\u0627\u0644\u0632\u064a\u0627\u062f\u0629 \u0627\u0644\u0633\u0646\u0648\u064a\u0629",
    ],

    "legal_compensation": [
        "compensation",
        "damages",
        "compensation for breach",
        "contractual compensation",
        "التعويض",
        "تعويض",
        "تعويض عن الضرر",
        "التعويض عن الإخلال",
    ],

    "working_hours": [
        "working hours",
        "work hours",
        "hours of work",

        "overtime",
        "overtime work",
        "overtime hours",
        "additional working hours",

        "ساعات العمل",
        "ساعة العمل",

        "العمل الإضافي",
        "العمل الاضافي",

        "ساعات العمل الإضافية",
        "ساعات العمل الاضافية",

        "ساعات عمل إضافية",
        "ساعات عمل اضافية",

        "ساعات إضافية",
        "ساعات اضافية",

        "فترات الراحة",
        "فترة الراحة",
        "الراحة",
    ],

    "letter_of_credit": [
        "letter of credit",
        "documentary credit",
        "documentary letter of credit",
        "\u0627\u0644\u0627\u0639\u062a\u0645\u0627\u062f \u0627\u0644\u0645\u0633\u062a\u0646\u062f\u064a",
        "\u0627\u0639\u062a\u0645\u0627\u062f \u0645\u0633\u062a\u0646\u062f\u064a",
    ],

    "annual_leave": [
        "annual leave",
        "paid leave",
        "vacation",
        "holiday",
        "leave entitlement",
        "الإجازة السنوية",
        "الاجازة السنوية",
        "إجازة سنوية",
        "اجازة سنوية",
        "الإجازات",
        "الاجازات",
        "العطلات",
    ],

    "sick_leave": [
        "sick leave",
        "medical leave",
        "إجازة مرضية",
        "اجازة مرضية",
        "الإجازة المرضية",
        "الاجازة المرضية",
        "المرض",
    ],

    "termination": [
        "termination",
        "termination employment",
        "employment termination",
        "end of employment",
        "dismissal",
        "notice period",
        "notice",
        "إنهاء عقد العمل",
        "انهاء عقد العمل",
        "إنهاء العقد",
        "انهاء العقد",
        "الفصل",
        "مهلة الإخطار",
        "مهلة الاخطار",
        "الإخطار",
        "الاخطار",
    ],

    "probation": [
        "probation",
        "probation period",
        "trial period",
        "فترة التجربة",
        "شرط التجربة",
        "التجربة",
    ],

    "end_of_service": [
    "end of service",
    "end of service benefit",
    "end of service benefits",
    "end of service rights",
    "severance",
    "severance benefit",
    "termination benefit",
    "termination benefits",

    "مكافأة نهاية الخدمة",
    "مكافاه نهاية الخدمة",
    "نهاية الخدمة",
    "مستحقات نهاية الخدمة",
    "مستحقات العامل",

    "عند إنهاء عقد العمل",
    "عند انتهاء عقد العمل",
    "إنهاء عقد العمل",
    "انتهاء عقد العمل",

    "يستحق العامل",
    "سنوات العمل",
    "سنوات الخدمة",

    "أجر نصف شهر",
    "اجر نصف شهر",
    "أجر شهر عن كل سنة",
    "اجر شهر عن كل سنة",

    "غير الخاضع لأحكام قانون التأمين الاجتماعي",
    "غير الخاضع لقانون التأمين الاجتماعي",
    "التأمين الاجتماعي",
],
    "disciplinary": [
        "disciplinary",
        "disciplinary sanctions",
        "employee warning",
        "warning letter",
        "misconduct",
        "جزاء",
        "الجزاءات",
        "جزاءات تأديبية",
        "الجزاءات التأديبية",
        "مخالفة",
        "إنذار",
        "انذار",
    ],

    "confidentiality": [
        "confidentiality",
        "confidential information",
        "non disclosure",
        "non-disclosure",
        "nda",
        "سرية",
        "السرية",
        "سرية المعلومات",
        "المعلومات السرية",
        "عدم الإفصاح",
        "عدم الافصاح",
    ],

    "personal_data": [
        "personal data",
        "data protection",
        "personal information",
        "privacy",
        "processing personal data",
        "بيانات شخصية",
        "البيانات الشخصية",
        "حماية البيانات",
        "معالجة البيانات",
        "معالجه البيانات",
        "الخصوصية",
    ],

    "data_security": [
        "data security",
        "security measures",
        "information security",
        "confidentiality of processing",
        "أمن البيانات",
        "امن البيانات",
        "سرية المعالجة",
        "سريه المعالجه",
        "التدابير الفنية",
        "التدابير التنظيمية",
    ],

    "data_transfer": [
        "data transfer",
        "international data transfer",
        "cross border data transfer",
        "transfer personal data",
        "نقل البيانات",
        "نقل البيانات الشخصية",
        "خارج المملكة",
    ],

    "employee": [
        "employee",
        "worker",
        "staff",
        "العامل",
        "الموظف",
        "عمال",
    ],

    "employer": [
        "employer",
        "company",
        "organization",
        "صاحب العمل",
        "المنشأة",
        "الشركة",
    ],

    "contract": [
        "contract",
        "agreement",
        "عقد",
        "اتفاق",
        "اتفاقية",
    ],

    "obligations": [
        "obligation",
        "obligations",
        "duties",
        "responsibilities",
        "التزام",
        "التزامات",
        "واجبات",
        "مسؤوليات",
    ],

    "public_holidays": [
        "public holiday",
        "public holidays",
        "official holiday",
        "official holidays",
        "\u0627\u0644\u0639\u0637\u0644\u0627\u062a \u0627\u0644\u0631\u0633\u0645\u064a\u0629",
        "\u0627\u0644\u0639\u0637\u0644 \u0627\u0644\u0631\u0633\u0645\u064a\u0629",
        "\u0623\u064a\u0627\u0645 \u0627\u0644\u0639\u0637\u0644",
    ],
}




@lru_cache(maxsize=1)
def load_regulations() -> list[dict[str, Any]]:
    """
    Load Bahrain regulations from the original file
    and additional law files inside knowledge/bahrain/laws.
    """

    laws_folder = REGULATIONS_FILE.parent / "laws"

    if not REGULATIONS_FILE.exists():
        raise FileNotFoundError(
            "Bahrain regulations knowledge base was not found."
        )

    files_to_load: list[Path] = [REGULATIONS_FILE]

    if laws_folder.exists():
        files_to_load.extend(
            sorted(laws_folder.glob("*.json"))
        )

    all_regulations: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for file_path in files_to_load:
        with open(file_path, "r", encoding="utf-8") as file:
            raw_data: Any = json.load(file)

        if not isinstance(raw_data, dict):
            raise ValueError(
                f"Invalid regulations file: {file_path.name}"
            )

        data = cast(dict[str, Any], raw_data)
        raw_regulations: Any = data.get("regulations", [])

        if not isinstance(raw_regulations, list):
            raise ValueError(
                f"Invalid regulations list: {file_path.name}"
            )

        regulations = cast(list[Any], raw_regulations)

        for raw_regulation in regulations:
            if not isinstance(raw_regulation, dict):
                raise ValueError(
                    f"Invalid regulation in {file_path.name}"
                )

            regulation = cast(dict[str, Any], raw_regulation)

            regulation_id = str(
                regulation.get("id", "")
            ).strip()

            if not regulation_id:
                raise ValueError(
                    f"Missing regulation ID in {file_path.name}"
                )

            if regulation_id in seen_ids:
                raise ValueError(
                    f"Duplicate regulation ID: {regulation_id}"
                )

            seen_ids.add(regulation_id)
            all_regulations.append(regulation)

    return all_regulations



@lru_cache(maxsize=1)

def load_high_risk_article_flags() -> dict[str, set[str]]:
    """Load article warnings; malformed data must fail closed."""
    path = (
        REGULATIONS_FILE.parent
        / "review_reports"
        / "high_risk_article_flags.json"
    )

    if not path.exists():
        raise RuntimeError("High-risk article warning file missing")

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        if (
            data.get("warning_only") is not True
            or data.get("legal_currency_confirmed") is not False
            or data.get("automatic_approval") is not False
            or data.get("status") != "pending_human_legal_review"
            or not isinstance(data.get("items"), list)
        ):
            raise ValueError("Invalid warning report")

        result: dict[str, set[str]] = {}

        for item in data["items"]:
            if not isinstance(item, dict):
                raise ValueError("Invalid warning entry")

            source_id = item.get("source_id")
            articles = item.get("articles")

            if (
                not isinstance(source_id, str)
                or not source_id
                or not isinstance(articles, list)
            ):
                raise ValueError("Invalid warning fields")

            result.setdefault(source_id, set()).update(
                str(article).strip()
                for article in articles
            )

        return result

    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeError(
            "High-risk article warnings cannot be validated"
        ) from exc


def article_requires_human_review(
    regulation: dict[str, Any],
    flags: dict[str, set[str]],
) -> bool:
    """Match warnings by trusted source and article number."""
    source_id = str(regulation.get("source_id") or "").strip()
    article = str(
        regulation.get("article_number")
        or regulation.get("article")
        or ""
    ).strip()

    return article in flags.get(source_id, set())


def load_verification_registry() -> dict[str, dict[str, Any]]:
    """Load source review metadata without granting legal validity."""
    registry_path = (
        REGULATIONS_FILE.parent
        / "legal_verification_registry.json"
    )

    if not registry_path.exists():
        return {}

    try:
        with registry_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        sources = data.get("sources", [])
        if not isinstance(sources, list):
            return {}

        result: dict[str, dict[str, Any]] = {}

        for source in sources:
            if not isinstance(source, dict):
                continue

            source_id = str(source.get("source_id") or "").strip()
            verification = source.get("verification", {})

            if not source_id or not isinstance(verification, dict):
                continue

            # A registry entry cannot independently authorize legal validity.
            result[source_id] = {
                "status": str(
                    verification.get("status") or "pending_review"
                ),
                "verified_current": False,
                "reviewed_at": verification.get("reviewed_at"),
                "reviewed_by": verification.get("reviewed_by"),
                "evidence_count": len(
                    verification.get("evidence", [])
                ) if isinstance(verification.get("evidence"), list) else 0,
            }

        return result

    except (OSError, ValueError, TypeError, AttributeError):
        return {}





@lru_cache(maxsize=4096)
def normalize_text(
    text: str,
) -> str:
    """
    Normalize Arabic and English text.
    """

    text = text.lower()

    # Arabic letter normalization.
    text = re.sub(
        r"[أإآٱ]",
        "ا",
        text,
    )

    text = text.replace(
        "ى",
        "ي",
    )

    text = text.replace(
        "ة",
        "ه",
    )

    text = text.replace(
        "ؤ",
        "و",
    )

    text = text.replace(
        "ئ",
        "ي",
    )

    # Remove tatweel.
    text = text.replace(
        "ـ",
        "",
    )

    # Remove Arabic diacritics.
    text = re.sub(
        r"[\u064B-\u065F\u0670]",
        "",
        text,
    )

    # Normalize hyphens.
    text = text.replace(
        "-",
        " ",
    )

    # Remove punctuation.
    text = re.sub(
        r"[^\w\s]",
        " ",
        text,
    )

    # Normalize whitespace.
    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text

def normalize_match_word(
    word: str,
) -> str:
    """
    Light normalization for matching Arabic
    word variants without changing stored law text.

    Examples:
    العمل -> عمل
    الإضافي -> اضاف
    إضافية -> اضاف
    """

    word = normalize_text(
        word
    )

    # Remove Arabic definite article.
    if (
        word.startswith("ال")
        and len(word) > 4
    ):
        word = word[2:]

    # Light handling of common adjective endings.
    if (
        word.endswith("يه")
        and len(word) > 4
    ):
        word = word[:-2]

    elif (
        word.endswith("ي")
        and len(word) > 4
    ):
        word = word[:-1]

    return word


@lru_cache(maxsize=4096)
def get_query_words(
    query: str,
) -> list[str]:

    normalized_query = normalize_text(
        query
    )

    words = normalized_query.split()

    normalized_stop_words = {
        normalize_text(word)
        for word in STOP_WORDS
    }

    useful_words: list[str] = []

    for word in words:

        if word in normalized_stop_words:
            continue

        if len(word) <= 1:
            continue

        if word not in useful_words:
            useful_words.append(
                word
            )

    return useful_words


@lru_cache(maxsize=4096)
def get_query_phrases(
    query: str,
) -> list[str]:

    words = get_query_words(
        query
    )

    phrases: list[str] = []

    for index in range(
        len(words) - 1
    ):
        phrases.append(
            f"{words[index]} "
            f"{words[index + 1]}"
        )

    for index in range(
        len(words) - 2
    ):
        phrases.append(
            f"{words[index]} "
            f"{words[index + 1]} "
            f"{words[index + 2]}"
        )

    return phrases



@lru_cache(maxsize=4096)
def detect_legal_concepts(query: str) -> list[str]:
    """Detect legal concepts with explicit holiday disambiguation."""
    normalized_query = normalize_text(query)

    public_phrases = (
        "public holiday",
        "public holidays",
        "official holiday",
        "official holidays",
        "\u0627\u0644\u0639\u0637\u0644\u0627\u062a \u0627\u0644\u0631\u0633\u0645\u064a\u0629",
    )

    annual_phrases = (
        "annual leave",
        "annual holiday",
        "paid annual leave",
        "\u0625\u062c\u0627\u0632\u0629 \u0633\u0646\u0648\u064a\u0629",
        "\u0627\u0644\u0625\u062c\u0627\u0632\u0629 \u0627\u0644\u0633\u0646\u0648\u064a\u0629",
    )

    is_public = any(
        phrase in normalized_query
        for phrase in public_phrases
    )

    is_annual = any(
        phrase in normalized_query
        for phrase in annual_phrases
    )

    detected = []

    for concept, terms in LEGAL_CONCEPTS.items():
        if concept == "annual_leave" and is_public and not is_annual:
            continue

        for term in terms:
            normalized_term = normalize_text(term)

            if normalized_term and normalized_term in normalized_query:
                detected.append(concept)
                break

    if is_public and "public_holidays" not in detected:
        detected.append("public_holidays")

    return detected




@lru_cache(maxsize=4096)
def get_expanded_terms(
    query: str,
) -> list[str]:
    """
    Expand an English or Arabic legal query
    using the bilingual concept map.
    """

    expanded: list[str] = []

    # Original query.
    normalized_query = normalize_text(
        query
    )

    if normalized_query:
        expanded.append(
            normalized_query
        )

    # Original words.
    for word in get_query_words(
        query
    ):
        if word not in expanded:
            expanded.append(
                word
            )

    # Bilingual legal concepts.
    concepts = detect_legal_concepts(
        query
    )

    for concept in concepts:

        terms = LEGAL_CONCEPTS.get(
            concept,
            [],
        )

        for term in terms:

            normalized_term = normalize_text(
                term
            )

            if (
                normalized_term
                and normalized_term
                not in expanded
            ):
                expanded.append(
                    normalized_term
                )

    return expanded


def is_repealed_regulation(
    regulation: dict[str, Any],
) -> bool:
    """
    Ignore provisions clearly marked
    as repealed in the knowledge base.
    """

    text = normalize_text(
        str(
            regulation.get(
                "text",
                "",
            )
        )
    )

    repealed_markers = {
        normalize_text("ملغى"),
        normalize_text("-ملغى-"),
        normalize_text("repealed"),
    }

    return (
        text in repealed_markers
    )


def calculate_score(
    query: str,
    regulation: dict[str, Any],
) -> int:
    """
    Calculate legal relevance using:
    - bilingual concepts
    - phrases
    - individual words
    - title/category matches
    - concept coverage
    """

    if is_repealed_regulation(
        regulation
    ):
        return 0

    query_normalized = normalize_text(
        query
    )

    query_words = get_query_words(
        query
    )

    query_phrases = get_query_phrases(
        query
    )

    expanded_terms = get_expanded_terms(
        query
    )

    detected_concepts = (
        detect_legal_concepts(
            query
        )
    )

    title = normalize_text(
        str(
            regulation.get(
                "title",
                "",
            )
        )
    )

    text = normalize_text(
        str(
            regulation.get(
                "text",
                "",
            )
        )
    )

    category = normalize_text(
        str(
            regulation.get(
                "category",
                "",
            )
        )
    )

    searchable_text = (
        f"{title} "
        f"{category} "
        f"{text}"
    )

    score = 0

    matched_original_words = 0
    matched_expanded_terms = 0
    matched_concepts = 0

    # ---------------------------------------------
    # Exact original query
    # ---------------------------------------------

    if (
        query_normalized
        and query_normalized
        in text
    ):
        score += 35

    # ---------------------------------------------
    # Original phrases
    # ---------------------------------------------

    for phrase in query_phrases:

        if phrase in text:

            phrase_length = len(
                phrase.split()
            )

            if phrase_length >= 3:
                score += 16
            else:
                score += 10

    # ---------------------------------------------
    # Original query words
    # ---------------------------------------------

    for word in query_words:

        matched = False

        if word in text:
            score += 4
            matched = True

        if word in title:
            score += 2
            matched = True

        if word in category:
            score += 4
            matched = True

        if matched:
            matched_original_words += 1

        # ---------------------------------------------
    # Expanded bilingual legal terms
    # ---------------------------------------------
    #
    # Original query terms already receive strong
    # scoring above.
    #
    # Concept-expanded terms are supporting evidence,
    # so they must not overpower a direct match to
    # the user's original legal query.
    # ---------------------------------------------

    original_terms: set[str] = set(
        query_words
    )

    if query_normalized:
        original_terms.add(
            query_normalized
        )

    for term in expanded_terms:

        if not term:
            continue

        # The original query and its own words
        # were already scored above.
        # Do not score them a second time here.
        if term in original_terms:
            continue

        if term in text:

            term_word_count = len(
                term.split()
            )

            # Expanded phrases are useful supporting
            # evidence, but deliberately receive less
            # weight than direct query matches.
            if term_word_count >= 4:
                score += 6

            elif term_word_count == 3:
                score += 5

            elif term_word_count == 2:
                score += 3

            else:
                score += 1

            matched_expanded_terms += 1

        # Title/category expansion is intentionally
        # kept very small.
        if term in title:
            score += 1

        if term in category:
            score += 1
   

     # ---------------------------------------------
    # Legal concept matching
    # ---------------------------------------------
    #
    # A regulation should receive stronger support
    # when it contains concept phrases that are
    # close to the user's original query.
    #
    # Example:
    # "العمل الإضافي"
    # should favour:
    # "ساعات عمل إضافية"
    #
    # more than:
    # "فترات الراحة"
    #
    # Both belong to the broader working-hours
    # concept, but they do not express the same
    # subtopic.
    # ---------------------------------------------

    query_word_set = {
        normalize_match_word(word)
        for word in query_words
        if normalize_match_word(word)
    }
    

    for concept in detected_concepts:

        concept_terms = (
            LEGAL_CONCEPTS.get(
                concept,
                [],
            )
        )

        concept_found = False
        best_concept_similarity = 0

        for term in concept_terms:

            normalized_term = normalize_text(
                term
            )

            if not normalized_term:
                continue

            if normalized_term not in searchable_text:
                continue

            concept_found = True

            term_words = {
                normalize_match_word(word)
                for word in normalized_term.split()
                if normalize_match_word(word)
            }

            if not term_words:
                continue

            shared_words = (
                query_word_set
                & term_words
            )

            if not shared_words:
                continue

            query_coverage = (
                len(shared_words)
                / max(
                    len(query_word_set),
                    1,
                )
            )

            term_coverage = (
                len(shared_words)
                / len(term_words)
            )

            similarity = int(
                (
                    query_coverage
                    * 12
                )
                +
                (
                    term_coverage
                    * 8
                )
            )

            # Strong bonus when a concept phrase
            # preserves all meaningful words from
            # the user's original query.
            #
            # Example:
            # Query: العمل الإضافي
            # Text term: ساعات عمل إضافية
            #
            # This is much more specific than a
            # generic match such as ساعات العمل.
            if (
                query_word_set
                and query_word_set.issubset(
                    term_words
                )
            ):
                similarity += 25

            best_concept_similarity = max(
                best_concept_similarity,
                similarity,
            )

        if concept_found:

            # Base concept support.
            score += 10

            # Extra support for the concept phrase
            # that is closest to the original query.
            score += best_concept_similarity

            matched_concepts += 1

    # ---------------------------------------------
    # Original word coverage
    # ---------------------------------------------

    total_original_words = len(
        query_words
    )

    if total_original_words > 0:

        coverage = (
            matched_original_words
            / total_original_words
        )

        if coverage >= 1:
            score += 15

        elif coverage >= 0.75:
            score += 10

        elif coverage >= 0.50:
            score += 5

    # ---------------------------------------------
    # Concept coverage
    # ---------------------------------------------

    total_concepts = len(
        detected_concepts
    )

    if total_concepts > 0:

        concept_coverage = (
            matched_concepts
            / total_concepts
        )

        if concept_coverage >= 1:
            score += 20

        elif concept_coverage >= 0.50:
            score += 10

    # ---------------------------------------------
    # Minimum relevance protection
    # ---------------------------------------------

    if (
        matched_original_words == 0
        and matched_expanded_terms == 0
        and matched_concepts == 0
    ):
        return 0

    return score


def search_regulations(
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Search the trusted Bahrain regulations
    knowledge base.

    Supports Arabic and English legal queries.
    """

    if not query.strip():
        return []

    high_risk_flags = load_high_risk_article_flags()
    regulations = load_regulations()

    results: list[
        dict[str, Any]
    ] = []

    detected_concepts = (
        detect_legal_concepts(
            query
        )
    )

    for regulation in regulations:

        score = calculate_score(
            query=query,
            regulation=regulation,
        )

        if score <= 0:
            continue

        result = regulation.copy()
        result["requires_human_review"] = (
            article_requires_human_review(
                result,
                high_risk_flags,
            )
        )

        if result["requires_human_review"]:
            result["legal_article_warning"] = (
                "Official consolidated text mismatch or "
                "unresolved article status; human legal review required."
            )
            result["effective_status"] = "unverified"


        source_id = str(
            result.get("source_id") or ""
        ).strip()

        registry_entry = load_verification_registry().get(
            source_id,
            {},
        )

        result["verification_registry"] = (
            registry_entry.copy()
            if registry_entry
            else {
                "status": "registry_missing",
                "verified_current": False,
                "evidence_count": 0,
            }
        )

        result[
            "relevance_score"
        ] = score

        result[
            "matched_concepts"
        ] = detected_concepts

        results.append(
            result
        )

    # Secondary ranking for commercial contract disputes.
    # This changes relevance ranking only, not legal validity.
    query_normalized = normalize_text(query)

    dispute_signals = [
        "dispute",
        "breach",
        "termination",
        "\u0646\u0632\u0627\u0639",
        "\u0645\u0646\u0627\u0632\u0639\u0629",
        "\u0625\u062e\u0644\u0627\u0644",
        "\u0641\u0633\u062e",
    ]

    is_commercial_dispute = (
        (
            "commercial" in query_normalized
            or "\u062a\u062c\u0627\u0631" in query_normalized
        )
        and any(
            normalize_text(term) in query_normalized
            for term in dispute_signals
        )
    )

    dispute_phrases = [
        "\u0637\u0644\u0628 \u0627\u0644\u0641\u0633\u062e",
        "\u0627\u0644\u0641\u0633\u062e \u0648\u0627\u0644\u062a\u0639\u0648\u064a\u0636",
        "\u0627\u0644\u0645\u0637\u0627\u0644\u0628\u0629 \u0628\u062a\u0639\u0648\u064a\u0636",
        "\u0627\u0644\u062a\u0623\u062e\u064a\u0631 \u0641\u064a \u0627\u0644\u0648\u0641\u0627\u0621",
        "\u0627\u0644\u0625\u062e\u0644\u0627\u0644 \u0628\u0627\u0644\u0627\u0644\u062a\u0632\u0627\u0645",
    ]

    def ranking_key(item: dict[str, Any]) -> int:
        score = int(item.get("relevance_score", 0))

        if (
            is_commercial_dispute
            and item.get("category") == "commercial_law"
        ):
            article_text = normalize_text(
                str(item.get("text", ""))
            )

            phrase_matches = sum(
                normalize_text(phrase) in article_text
                for phrase in dispute_phrases
            )

            score += min(phrase_matches, 2) * 12

        return score

    if "contract_formation" in detected_concepts:
        formation_phrases = (
            "\u064a\u0646\u0639\u0642\u062f \u0627\u0644\u0639\u0642\u062f",
            "\u0644\u0627\u0646\u0639\u0642\u0627\u062f \u0627\u0644\u0639\u0642\u062f",
            "\u0627\u0644\u0625\u064a\u062c\u0627\u0628 \u0628\u0627\u0644\u0642\u0628\u0648\u0644",
            "\u0627\u0644\u0642\u0628\u0648\u0644 \u0645\u0637\u0627\u0628\u0642\u0627",
        )

        def formation_bonus(item: dict[str, Any]) -> int:
            article_text = normalize_text(
                str(item.get("text") or "")
            )
            return 30 * sum(
                bool(normalize_text(phrase))
                and normalize_text(phrase) in article_text
                for phrase in formation_phrases
            )

        results.sort(
            key=lambda item: (
                formation_bonus(item),
                ranking_key(item),
            ),
            reverse=True,
        )
    else:
        results.sort(
            key=ranking_key,
            reverse=True,
        )

    return results[:limit]
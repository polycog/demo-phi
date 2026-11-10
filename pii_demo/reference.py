"""
Reference data and patterns: knowledge that lives in tables, not in a model's weights.
"""

import re

# HHS de-identification guidance: 3-digit ZIP prefixes whose combined population was
# 20,000 or fewer (2000 Census). Under Safe Harbor these must be released as "000".
RESTRICTED_ZIP3 = frozenset(
    "036 059 063 102 203 556 692 790 821 823 830 831 878 879 884 890 893".split()
)

US_STATES = frozenset(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ "
    "NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC PR".split()
) | frozenset(
    s.lower()
    for s in (
        "Alabama Alaska Arizona Arkansas California Colorado Connecticut Delaware Florida Georgia "
        "Hawaii Idaho Illinois Indiana Iowa Kansas Kentucky Louisiana Maine Maryland Massachusetts "
        "Michigan Minnesota Mississippi Missouri Montana Nebraska Nevada Ohio Oklahoma Oregon "
        "Pennsylvania Tennessee Texas Utah Vermont Virginia Washington Wisconsin Wyoming"
    ).split()
)

SAFE_HARBOR = {
    "A": "§164.514(b)(2)(i)(A) names",
    "B": "§164.514(b)(2)(i)(B) geographic subdivisions smaller than a state",
    "C": "§164.514(b)(2)(i)(C) dates related to an individual; ages over 89",
    "D": "§164.514(b)(2)(i)(D) telephone numbers",
    "F": "§164.514(b)(2)(i)(F) email addresses",
    "H": "§164.514(b)(2)(i)(H) medical record numbers",
    "I/J": "§164.514(b)(2)(i)(I)-(J) health plan and account numbers",
    "N/O": "§164.514(b)(2)(i)(N)-(O) URLs and IP addresses",
    "R": "§164.514(b)(2)(i)(R) any other unique identifying number, characteristic or code",
    "c": "§164.514(c) re-identification codes",
    "ii": "§164.514(b)(2)(ii) actual knowledge of re-identification risk",
    "scope": "§164.514(b)(2)(i) scope: identifiers of the individual, relatives, employers, household members",
    "none": "not an identifier under §164.514(b)(2)",
}

SUBJECT_CODE = re.compile(r"\bNX301-\d{4}\b(?!-)")

MONTHS = "January February March April May June July August September October November December".split()

# Pattern "sensors": cheap, deterministic proposals that complement the LLM.
PATTERNS: dict[str, re.Pattern[str]] = {
    "date": re.compile(
        r"\b\d{4}-\d{2}-\d{2}\b|\b\d{4}-\d{2}\b(?!-)|\b(?:%s) \d{1,2}, \d{4}\b" % "|".join(MONTHS)
    ),
    "contact": re.compile(r"\b\d{3}-\d{3}-\d{4}\b|\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
    "geographic": re.compile(r"(?<=\b[A-Z]{2} )\d{5}\b"),
}

YEAR = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
AGE = re.compile(r"\b(\d{1,3})\b")
ZIP5 = re.compile(r"^\d{5}(-\d{4})?$")


def birth_year(text: str) -> int | None:
    """Year from a written date, if any"""
    m = YEAR.search(text)
    return int(m.group(1)) if m else None


def year_only(text: str) -> str | None:
    """'March 3, 2026' -> '2026'"""
    y = birth_year(text)
    return str(y) if y else None


def digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def initials(name: str) -> str:
    return "".join(p[0] for p in re.findall(r"[A-Za-z][A-Za-z'-]*", name)).upper()

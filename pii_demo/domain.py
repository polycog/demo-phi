"""
Shared typed data: what the LLM may say, and what the knowledge graph holds.

Docstrings and Field descriptions are written into the LLM prompts by
`cognition`, so they are part of the "spec" the model sees.
"""

from pydantic import BaseModel, Field

from cognition import BinaryRelation, DocEnum, Entity

# --- vocabulary the LLM answers in ------------------------------------------


class MentionKind(DocEnum):
    """Kind of text span that might identify a person"""

    PERSON_NAME = "person_name", "a full or partial name of a human being"
    ORGANIZATION = "organization", "a company, employer, hospital or other organization"
    GEOGRAPHIC = "geographic", "a street, town, city, county, state, ZIP code or other place"
    DATE = "date", "a calendar date, month or year"
    AGE = "age", "a person's age"
    CONTACT = "contact", "a phone number, fax, email address, URL or IP address"
    ID_CODE = "id_code", "an identifier, code, label or number (record, sample, lot, protocol, subject ...)"
    UNIQUE_CHARACTERISTIC = (
        "unique_characteristic",
        "a distinctive personal fact, event or trait that could single someone out "
        "(e.g. a publicized achievement, unusual occupation or notable incident)",
    )
    BIOMEDICAL_TERM = (
        "biomedical_term",
        "a disease, gene, drug, cell line or other scientific term (even if it contains a name)",
    )


class Whose(DocEnum):
    """Who the phrase identifies or belongs to"""

    SUBJECT = "subject", "the patient or study participant themself"
    FAMILY_OR_HOUSEHOLD = "family_or_household", "a relative or household member of the patient or participant"
    EMPLOYER = "employer", "the employer of the patient or participant"
    STAFF = "staff", "study, site, sponsor or care-team staff (investigator, coordinator, monitor, clinician)"
    NOT_A_PERSON = "not_a_person", "nobody: an eponym, disease, gene, cell line, product or other non-person"


class DateRole(DocEnum):
    """What the date is the date of"""

    BIRTH = "birth", "the person's date or year of birth"
    PERSONAL_EVENT = (
        "personal_event",
        "an event in one individual's care or life: admission, discharge, death, enrollment, "
        "visit by that individual, sample collection from them, procedure",
    )
    ADMINISTRATIVE = (
        "administrative",
        "a date about a document, protocol, site, shipment, reagent or other non-individual matter",
    )


class CodeKind(DocEnum):
    """What the identifier labels"""

    STUDY_SUBJECT_CODE = "study_subject_code", "a study participant code assigned by the trial"
    SAMPLE_CODE = "sample_code", "a label for a biological sample or specimen"
    MEDICAL_RECORD_NUMBER = "mrn", "a hospital medical record number"
    ACCOUNT_OR_PLAN_NUMBER = "account", "a health plan, insurance or account number"
    ADMINISTRATIVE = "administrative", "a protocol, lot, batch, document or other non-person identifier"


class GeoLevel(DocEnum):
    """Granularity of a place"""

    STREET_ADDRESS = "street", "a street address"
    TOWN_OR_CITY = "town", "a town, city, village or neighborhood"
    COUNTY = "county", "a county or similar sub-state region"
    STATE = "state", "a U.S. state or territory"
    COUNTRY = "country", "a country"
    ZIP = "zip", "a postal ZIP code"


class Action(DocEnum):
    """How a span is treated in the released document"""

    KEEP = "KEEP", "leave the span as is"
    GENERALIZE = "GENERALIZE", "replace with a coarser value (e.g. year only, 3-digit ZIP, 90+)"
    REDACT = "REDACT", "remove the span"
    ESCALATE = "ESCALATE", "withhold pending human privacy review"


# --- what the LLM extracts from one document ---------------------------------


class ProposedMention(BaseModel):
    """One span of the document worth examining for privacy"""

    text: str = Field(description="the span, copied EXACTLY as it appears in the document; one atomic item")
    kind: MentionKind = Field(description="kind of span")


class Extraction(BaseModel):
    """Every span in the document that names, locates, dates, contacts, codes or describes a person, plus scientific terms that contain names"""

    mentions: list[ProposedMention] = Field(
        description="all candidate spans, in document order; split compound items "
        "(e.g. 'Austin, TX 78701' -> 'Austin', 'TX', '78701')"
    )


# --- knowledge graph ----------------------------------------------------------


class Document(Entity):
    """A source document in the trial packet"""

    title: str = Field(description="first line of the document")


class Subject(Entity):
    """A study participant, keyed by study subject code; holds identifiers learned anywhere in the packet"""

    names: list[str] = Field(default_factory=list, description="names of the participant")
    birth_dates: list[str] = Field(default_factory=list, description="birth dates as written")
    record_numbers: list[str] = Field(default_factory=list, description="medical record numbers")
    learned_from: list[str] = Field(default_factory=list, description="'<value> <- <document>' provenance")

    def source_of(self, value: str) -> str:
        for entry in self.learned_from:
            v, _, doc = entry.partition(" <- ")
            if v == value:
                return doc
        return "?"


class Mention(Entity):
    """A candidate span plus everything learned about it (name = '<doc>#<n>')"""

    doc: str
    text: str
    kind: MentionKind
    start: int
    end: int
    context: str = Field(description="surrounding text shown to the LLM")
    proposed_by: str = Field(description="'llm' or 'pattern'")
    subject_code: str | None = None
    answers: dict[str, str] = Field(default_factory=dict, description="question -> answer value")
    confidence: dict[str, float] = Field(default_factory=dict, description="question -> agreement")


class InDocument(BinaryRelation):
    """entity1 appears in document entity2"""

    entity1: Mention = Field(frozen=True)
    entity2: Document = Field(frozen=True)


class Concerns(BinaryRelation):
    """mention entity1 is about study participant entity2"""

    entity1: Mention = Field(frozen=True)
    entity2: Subject = Field(frozen=True)


# --- outcome ------------------------------------------------------------------


class Decision(BaseModel):
    """The treatment of one span, with its justification"""

    doc: str
    text: str
    start: int
    end: int
    action: Action
    replacement: str | None = None
    rule: str
    citation: str
    rationale: str
    evidence: list[str] = Field(default_factory=list)

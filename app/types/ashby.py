"""Type definitions for Ashby API responses."""

from typing import NotRequired, TypedDict


class FileHandleTD(TypedDict):
    """Ashby file handle structure."""

    handle: str
    name: str


class EmailAddressTD(TypedDict):
    """Ashby email address structure."""

    value: str
    type: str  # e.g., "Personal", "Work"


class SocialLinkTD(TypedDict):
    """Ashby social link structure."""

    type: str  # e.g., "LinkedIn", "GitHub"
    url: str


class CandidateTD(TypedDict):
    """Candidate info from Ashby candidate.info API.

    Only includes fields actually used in the app.
    """

    id: str
    name: str
    emailAddresses: NotRequired[list[EmailAddressTD]]
    primaryEmailAddress: NotRequired[EmailAddressTD]
    resumeFileHandle: NotRequired[FileHandleTD]
    socialLinks: NotRequired[list[SocialLinkTD]]
    profileUrl: NotRequired[str]
    position: NotRequired[str]
    company: NotRequired[str]


class FormFieldTD(TypedDict):
    """Ashby form field definition."""

    path: str
    type: str  # "Score", "RichText", "Text", "Email", etc.
    title: str
    isRequired: NotRequired[bool]


class FormFieldConfigTD(TypedDict):
    """Ashby form field with config."""

    field: FormFieldTD
    isRequired: bool


class FormSectionTD(TypedDict):
    """Ashby form section."""

    title: NotRequired[str]
    fields: list[FormFieldConfigTD]


class FormDefinitionStructureTD(TypedDict):
    """Ashby form definition structure (nested inside response)."""

    sections: list[FormSectionTD]


class FeedbackFormTD(TypedDict):
    """Feedback form definition from Ashby feedbackFormDefinition.info API."""

    id: str
    title: str
    isArchived: NotRequired[bool]
    formDefinition: FormDefinitionStructureTD


class FieldSubmissionTD(TypedDict):
    """Single field submission for Ashby feedback API."""

    path: str
    value: str | int | bool | dict[str, str | int] | list[str] | None


class JobInfoTD(TypedDict):
    """Job info from Ashby job.info API (minimal fields)."""

    id: str
    title: str

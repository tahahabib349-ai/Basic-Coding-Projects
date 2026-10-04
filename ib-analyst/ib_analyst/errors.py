"""Friendly error types.

Every error the user can see is raised as an `AnalystError` with a plain-English
message. The UI shows `user_message` and never a technical stack trace.
"""


class AnalystError(Exception):
    """Base class for all errors that should be shown to the user."""

    def __init__(self, user_message: str, *, detail: str = ""):
        super().__init__(user_message)
        self.user_message = user_message
        # Technical detail for developers/logs. Must never contain secrets.
        self.detail = detail


# --- File ingestion -------------------------------------------------------
class FileIngestionError(AnalystError):
    pass


class UnsupportedFileError(FileIngestionError):
    pass


class PasswordProtectedError(FileIngestionError):
    pass


class CorruptFileError(FileIngestionError):
    pass


class EmptyDocumentError(FileIngestionError):
    pass


class FileTooLargeError(FileIngestionError):
    pass


# --- AI provider ----------------------------------------------------------
class LLMError(AnalystError):
    pass


class MissingAPIKeyError(LLMError):
    pass


class InvalidAPIKeyError(LLMError):
    pass


class RateLimitError(LLMError):
    pass


class LLMResponseError(LLMError):
    """The AI answered, but the answer was unusable (e.g. not valid JSON)."""

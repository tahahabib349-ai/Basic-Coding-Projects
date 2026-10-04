"""Front door for uploaded files: checks type/size and routes to the right reader.

One bad file never stops the others: each failure is recorded with a friendly
message and the remaining files are still processed.
"""

from __future__ import annotations

from ..config import get_logger, settings
from ..errors import AnalystError, FileTooLargeError, UnsupportedFileError
from .excel_processor import read_excel
from .models import IngestionResult, SourceDocument
from .pdf_processor import read_pdf

log = get_logger()

PDF_EXT = (".pdf",)
EXCEL_EXT = (".xlsx", ".xlsm", ".xltx", ".xltm")
LEGACY_EXCEL_EXT = (".xls", ".xlsb")
SUPPORTED_EXT = PDF_EXT + EXCEL_EXT + LEGACY_EXCEL_EXT


def read_file(filename: str, data: bytes) -> SourceDocument:
    lower = filename.lower()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > settings.max_file_mb:
        raise FileTooLargeError(
            f"'{filename}' is {size_mb:.0f} MB, above the {settings.max_file_mb} MB limit. "
            "Split the document or upload only the relevant parts."
        )
    if len(data) == 0:
        raise UnsupportedFileError(f"'{filename}' is empty (0 bytes).")
    if lower.endswith(PDF_EXT):
        return read_pdf(filename, data)
    if lower.endswith(EXCEL_EXT + LEGACY_EXCEL_EXT):
        return read_excel(filename, data)
    raise UnsupportedFileError(
        f"'{filename}' is not a supported file type. Upload PDF (.pdf) or Excel (.xlsx, .xlsm) files."
    )


def ingest_files(files: list[tuple[str, bytes]]) -> IngestionResult:
    result = IngestionResult()
    for filename, data in files:
        try:
            result.documents.append(read_file(filename, data))
        except AnalystError as exc:
            log.info("Could not ingest %s: %s", filename, exc.detail or exc.user_message)
            result.errors.append((filename, exc.user_message))
        except Exception as exc:  # last-resort safety net: never show a stack trace
            log.exception("Unexpected error ingesting %s", filename)
            result.errors.append(
                (filename, f"'{filename}' could not be read due to an unexpected problem ({type(exc).__name__}).")
            )
    return result

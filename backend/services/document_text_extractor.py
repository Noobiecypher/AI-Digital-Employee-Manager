"""
document_text_extractor.py
===========================
Raw text extraction for the Document Upload & AI Document Ingestion
subsystem.

DocumentTextExtractor answers exactly one question: "given a stored
file on disk, what is its plain text content?" It owns text extraction
only — it never classifies, parses into structured fields, validates
business data, performs OCR, touches MongoDB, or knows about FastAPI,
routes, or DocumentMetadata.

Pipeline position
------------------
    Upload -> Storage -> Text Extraction -> AI Classification
            -> Domain Processor -> Review & Approval
            -> Business Import Service -> Database Update

This module implements the "Text Extraction" step only.

Responsibilities
-----------------
- Accept the path to a stored file (plus an optional MIME type hint).
- Determine which supported format the file is in.
- Extract its raw text content using the appropriate library.
- Normalize line endings, strip null bytes, and preserve readable
  paragraph breaks.
- Return "" for genuinely empty documents rather than raising.

Explicitly NOT this module's responsibility
--------------------------------------------
- Document classification (document_classifier.py).
- Structured field parsing / validation (BaseProcessor subclasses).
- OCR of scanned images or image-only PDFs.
- MongoDB access of any kind (document_repository.py).
- Upload orchestration (document_service.py).
- Physical file storage (document_storage.py).
- API routes, request/response schemas, or FastAPI concerns.

Supported formats
-------------------
    TXT      -> read directly as UTF-8 text.
    Markdown -> read directly as UTF-8 text (same handling as TXT;
                Markdown syntax is left as-is, not rendered/stripped).
    PDF      -> extracted page-by-page via PyMuPDF (fitz).
    DOCX     -> extracted paragraph-by-paragraph via python-docx.

Format resolution is by file extension first, falling back to the
supplied MIME type when the extension is missing or ambiguous. A file
whose format cannot be resolved to one of the above raises
UnsupportedDocumentTypeError rather than being guessed at.

Single source of truth for format keys
-----------------------------------------
TXT, PDF, and DOCX are recognized upload formats already modeled by
document_registry.FileFormat — this module reuses those enum values
rather than redefining its own string constants for them, so the
extension vocabulary stays defined in exactly one place. Markdown is
not part of FileFormat (it is not a document_registry upload format at
all, only a text-extractable one), so it is kept as a local constant
here — the one format key genuinely private to this module.

Dependency injection
---------------------
DocumentTextExtractor has no external collaborators to inject — it
depends only on the standard library and the PyMuPDF / python-docx
parsing libraries, never on other project services. It takes no
constructor arguments and is designed to be constructed once and
handed to DocumentService (and any other caller) via constructor
injection, the same way DocumentStorage, DocumentRepository, and
DocumentClassifier are — callers must not instantiate it inline
wherever text extraction is needed.

Stateless
---------
DocumentTextExtractor holds no mutable instance state — extract_text()
depends only on its arguments, so a single instance can be reused and
shared freely across requests.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from docx import Document as DocxDocument
from docx.opc.exceptions import PackageNotFoundError

from backend.document_processing.document_registry import FileFormat

logger = logging.getLogger(__name__)


# ==========================================================
# STANDARDIZED EXTRACTION EXCEPTIONS
# ==========================================================

class DocumentTextExtractorError(Exception):
    """
    Base exception for all document text extraction failures.

    Every exception raised out of DocumentTextExtractor.extract_text()
    is guaranteed to be a DocumentTextExtractorError (or a subclass),
    so callers can catch one type regardless of which format or which
    internal step failed.
    """


class UnsupportedDocumentTypeError(DocumentTextExtractorError):
    """
    Raised when a file's format cannot be resolved to one of the
    supported types (TXT, Markdown, PDF, DOCX) from either its
    extension or its MIME type.

    Carries file_path, extension, and mime_type so the failure can be
    logged and diagnosed without a raw traceback.
    """

    def __init__(
        self,
        file_path: Path,
        extension: str,
        mime_type: Optional[str],
    ) -> None:
        self.file_path = file_path
        self.extension = extension
        self.mime_type = mime_type

        super().__init__(
            f"Unsupported document type for '{file_path}' "
            f"(extension='{extension}', mime_type='{mime_type}')"
        )


class TextExtractionError(DocumentTextExtractorError):
    """
    Raised when a recognized document type fails to yield text — e.g.
    the file is missing, unreadable, corrupt, or the underlying
    library (PyMuPDF / python-docx) raises while parsing it.

    Carries file_path and a human-readable reason so the failure can
    be logged and diagnosed without a raw traceback.
    """

    def __init__(self, file_path: Path, reason: str) -> None:
        self.file_path = file_path
        self.reason = reason

        super().__init__(f"Text extraction failed for '{file_path}': {reason}")


# ==========================================================
# FORMAT KEYS
# ==========================================================
# TXT / PDF / DOCX reuse document_registry.FileFormat — the existing
# single source of truth for upload-format vocabulary — instead of
# redefining equivalent string constants here. MARKDOWN has no
# FileFormat counterpart (Markdown is not an accepted upload format in
# document_registry, only an extractable one), so it is defined
# locally as this module's one private format key.

_TXT = FileFormat.TXT.value
_PDF = FileFormat.PDF.value
_DOCX = FileFormat.DOCX.value
_MARKDOWN = "markdown"

# Collapse 3+ consecutive newlines into a single blank line.
_EXCESS_BLANK_LINES_RE = re.compile(r"\n{3,}", re.MULTILINE)


# ==========================================================
# DOCUMENT TEXT EXTRACTOR
# ==========================================================

class DocumentTextExtractor:
    """
    Extracts raw plain text from a stored document file.

    Stateless: extract_text() depends only on its arguments, never on
    mutable instance state, so a single instance can be constructed
    once and injected into any number of callers (DocumentService in
    particular).
    """

    # Extension -> format key. Checked first, since the extension on a
    # stored file is the most reliable signal.
    _EXTENSION_FORMAT_MAP: dict[str, str] = {
        ".txt": _TXT,
        ".md": _MARKDOWN,
        ".pdf": _PDF,
        ".docx": _DOCX,
    }

    # MIME type -> format key. Used as a fallback when the extension is
    # missing or not recognized.
    _MIME_FORMAT_MAP: dict[str, str] = {
        "text/plain": _TXT,
        "text/markdown": _MARKDOWN,
        "application/pdf": _PDF,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": _DOCX,
    }
    
    def __init__(self) -> None:
        self._dispatch = {
            _TXT: self._extract_txt,
            _MARKDOWN: self._extract_markdown,
            _PDF: self._extract_pdf,
            _DOCX: self._extract_docx,
        }

    # ----------------------------------------------------------
    # PUBLIC INTERFACE
    # ----------------------------------------------------------

    def extract_text(self, file_path: Path, mime_type: Optional[str] = None) -> str:
        """
        Extract raw text content from a stored document file.

        Args:
            file_path: Path to the stored file on disk.
            mime_type: Optional MIME type hint (e.g. "application/pdf"),
                       consulted only when the file extension does not
                       resolve to a supported format.

        Returns:
            The extracted plain text, with line endings normalized and
            null bytes removed. Returns "" for an empty document.

        Raises:
            UnsupportedDocumentTypeError: If the file's format cannot be
                                           resolved from its extension or
                                           mime_type.
            TextExtractionError:          If the file does not exist, is
                                           unreadable, or the underlying
                                           parser fails.
        """
        document_format = self._resolve_format(file_path, mime_type)

        logger.info(
            "Starting text extraction for '%s'.",
            file_path,
        )

        if not file_path.is_file():
            logger.error("Text extraction failed for '%s'.", file_path)
            raise TextExtractionError(file_path, "File does not exist.")

        extractor = self._dispatch[document_format]

        try:
            raw_text = extractor(file_path)
        except DocumentTextExtractorError:
            logger.error("Failed text extraction for '%s'.", file_path)
            raise
        except Exception as exc:
            logger.exception("Failed text extraction for '%s'.", file_path)
            raise TextExtractionError(file_path, str(exc)) from exc

        normalized_text = self._normalize_text(raw_text)

        logger.info(
            "Completed text extraction for '%s'.",
            file_path,
        )
        return normalized_text

    # ----------------------------------------------------------
    # FORMAT RESOLUTION
    # ----------------------------------------------------------

    def _resolve_format(self, file_path: Path, mime_type: Optional[str]) -> str:
        """
        Determine which supported format a file is in.

        Checks the file extension first, falling back to `mime_type`
        when the extension is missing or unrecognized.

        Raises:
            UnsupportedDocumentTypeError: If neither the extension nor
                                           the mime_type resolves to a
                                           supported format.
        """
        extension = file_path.suffix.lower()
        document_format = self._EXTENSION_FORMAT_MAP.get(extension)

        if document_format is None and mime_type is not None:
            document_format = self._MIME_FORMAT_MAP.get(mime_type.strip().lower())

        if document_format is None:
            raise UnsupportedDocumentTypeError(file_path, extension, mime_type)

        return document_format

    # ----------------------------------------------------------
    # FORMAT-SPECIFIC EXTRACTION
    # ----------------------------------------------------------
    # File-existence validation happens once, in extract_text(), so
    # none of these repeat it — each assumes file_path already exists
    # and focuses solely on parsing its own format.

    def _extract_txt(self, file_path: Path) -> str:
        """
        Read a plain text file as UTF-8.

        Invalid UTF-8 bytes are replaced to preserve document structure. So
        corrupted encodings are visible in the output rather than
        invisibly lossy.

        Raises:
            TextExtractionError: If the file cannot be read.
        """
        try:
            with file_path.open("r", encoding="utf-8", errors="replace") as handle:
                return handle.read()
        except OSError as exc:
            raise TextExtractionError(
                file_path, f"Failed to read file: {exc}"
            ) from exc

    def _extract_markdown(self, file_path: Path) -> str:
        """
        Read a Markdown file as UTF-8.

        Markdown syntax is returned as-is (not rendered or stripped) —
        rendering/stripping is a formatting concern, not extraction.
        Handling is otherwise identical to _extract_txt().
        """
        return self._extract_txt(file_path)

    def _extract_pdf(self, file_path: Path) -> str:
        """
        Extract text from a PDF, page by page, via PyMuPDF (fitz).

        Uses PyMuPDF's explicit "text" extraction mode for deterministic plain-text output.

        Raises:
            TextExtractionError: If the file is not a valid/readable PDF,
                                  or parsing otherwise fails.
        """
        try:
            with fitz.open(file_path) as pdf_document:
                parts: list[str] = []
                for page in pdf_document:
                    parts.append(page.get_text("text"))

        except fitz.FileDataError as exc:
            raise TextExtractionError(
                file_path, f"Corrupt or invalid PDF: {exc}"
            ) from exc
        except Exception as exc:
            raise TextExtractionError(
                file_path, f"Failed to parse PDF: {exc}"
            ) from exc

        return "\n\n".join(parts)

    def _extract_docx(self, file_path: Path) -> str:
        """
        Extract text from a DOCX file, paragraph by paragraph, via
        python-docx.

        Raises:
            TextExtractionError: If the file is not a valid/readable
                                  DOCX, or parsing otherwise fails.
        """
        try:
            docx_document = DocxDocument(str(file_path))
        except PackageNotFoundError as exc:
            raise TextExtractionError(
                file_path, f"Corrupt or invalid DOCX: {exc}"
            ) from exc
        except ValueError as exc:
            raise TextExtractionError(
                file_path,
                f"Invalid DOCX: {exc}",
            ) from exc
        except Exception as exc:
            raise TextExtractionError(
                file_path, f"Failed to parse DOCX: {exc}"
            ) from exc

        paragraph_texts = [paragraph.text for paragraph in docx_document.paragraphs]
        return "\n\n".join(paragraph_texts)

    # ----------------------------------------------------------
    # NORMALIZATION
    # ----------------------------------------------------------

    def _normalize_text(self, text: str) -> str:
        """
        Normalize extracted text for downstream consumption.

        - Removes null bytes.
        - Normalizes CRLF / CR line endings to LF.
        - Strips trailing whitespace from each line.
        - Collapses runs of 3+ newlines down to a single paragraph
          break (a blank line), preserving readable paragraph
          separation without excessive whitespace.
        - Strips leading/trailing whitespace from the whole document.

        Args:
            text: Raw text as returned by a format-specific extractor.

        Returns:
            Normalized text, or "" if `text` is empty or whitespace-only.
        """
        if not text:
            return ""

        normalized = text.replace("\x00", "")
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
        normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
        normalized = _EXCESS_BLANK_LINES_RE.sub("\n\n", normalized)

        return normalized.strip()

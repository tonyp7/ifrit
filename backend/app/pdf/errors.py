class PdfError(Exception):
    """Base of everything that can go wrong while making an invoice PDF."""


class TemplateError(PdfError):
    """The template cannot be filled: a placeholder that does not exist, a block placeholder
    sharing its paragraph with other text, a missing or repeated lines table, XML that is not
    safe to read."""


class PdfEngineError(PdfError):
    """The converter could not produce a PDF: it is not installed, it failed, it timed out or
    it left no file."""

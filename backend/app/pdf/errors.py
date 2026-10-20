class PdfError(Exception):
    """Base of everything that can go wrong while making an invoice PDF."""


class TemplateError(PdfError):
    """The template cannot be filled: a placeholder that does not exist, a block placeholder
    sharing its paragraph with other text, a missing or repeated lines table, XML that is not
    safe to read."""


class PdfEngineError(PdfError):
    """The converter could not produce a PDF: it is not installed, it failed, it timed out or
    it left no file."""


class PdfEngineNotInstalledError(PdfEngineError):
    """The converter is not installed: nothing is wrong with whatever was being converted."""


class PdfStampError(PdfError):
    """A stored PDF could not be read or marked: it is damaged, empty or encrypted."""

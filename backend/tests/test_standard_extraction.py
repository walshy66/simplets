"""COA-308: standard local invoice extraction stack."""

from types import SimpleNamespace

import app.extraction as extraction

from app.extraction import ExtractionRequest, StandardInvoiceExtractionProvider, get_extraction_provider


def request(filename="invoice.pdf", content_type="application/pdf", content=b"fake"):
    return ExtractionRequest(
        document_id="doc-1",
        filename=filename,
        content_type=content_type,
        intent="invoice",
        content=content,
    )


def test_standard_pdf_extraction_uses_pypdf_and_populates_invoice_fields(monkeypatch):
    class FakePage:
        def extract_text(self):
            return "Invoice # INV-308\nAcme Pty Ltd\nIssue Date: 2026-06-01\nDue Date: 2026-06-15\nTotal: AUD 123.45"

    class FakePdfReader:
        def __init__(self, stream):
            self.pages = [FakePage()]

    monkeypatch.setattr("app.extraction.PdfReader", FakePdfReader)

    result = StandardInvoiceExtractionProvider().extract(request())

    assert result.suggested_classification == "invoice"
    assert result.fields["invoice_number"] == "INV-308"
    assert result.fields["issuer"] == "Acme Pty Ltd"
    assert result.fields["issue_date"] == "2026-06-01"
    assert result.fields["due_date"] == "2026-06-15"
    assert result.fields["total_amount"] == 123.45
    assert result.fields["currency"] == "AUD"
    assert result.fields["_extraction"]["provider"] == "Standard"


def test_standard_docx_extraction_uses_python_docx(monkeypatch):
    fake_document = SimpleNamespace(paragraphs=[SimpleNamespace(text="Invoice No: DOCX-7"), SimpleNamespace(text="Total: $88.00")])
    monkeypatch.setattr("app.extraction.DocxDocument", lambda stream: fake_document)

    result = StandardInvoiceExtractionProvider().extract(
        request(filename="invoice.docx", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    )

    assert result.fields["invoice_number"] == "DOCX-7"
    assert result.fields["total_amount"] == 88.0
    assert result.fields["currency"] == "AUD"


def test_standard_image_extraction_preprocesses_with_pillow_and_uses_tesseract(monkeypatch):
    calls = []

    class FakeImage:
        def convert(self, mode):
            calls.append(("convert", mode))
            return self

    monkeypatch.setattr(extraction, "Image", SimpleNamespace(open=lambda stream: FakeImage()))
    monkeypatch.setattr(extraction, "ImageOps", SimpleNamespace(
        grayscale=lambda image: calls.append(("grayscale", None)) or image,
        autocontrast=lambda image: calls.append(("autocontrast", None)) or image,
    ))
    monkeypatch.setattr(extraction, "pytesseract", SimpleNamespace(image_to_string=lambda image: "Invoice: IMG-9\nTotal: AUD 10"))

    result = StandardInvoiceExtractionProvider().extract(request(filename="scan.png", content_type="image/png"))

    assert calls == [("convert", "RGB"), ("grayscale", None), ("autocontrast", None)]
    assert result.fields["invoice_number"] == "IMG-9"
    assert result.fields["total_amount"] == 10.0


def test_standard_extraction_missing_fields_do_not_fail():
    result = StandardInvoiceExtractionProvider()._extract_from_text("Invoice only")

    assert result.fields["invoice_number"] is None
    assert result.fields["total_amount"] is None
    assert set(result.fields["_extraction"]["flagged_fields"]) >= {"invoice_number", "issuer", "total_amount"}


def test_standard_provider_selection(monkeypatch):
    monkeypatch.setenv("STS_EXTRACTION_PROVIDER", "standard")

    assert isinstance(get_extraction_provider(), StandardInvoiceExtractionProvider)

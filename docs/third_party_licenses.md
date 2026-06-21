# Third-Party License Notes: MVP Invoice Extraction

Status: Draft planning note for MVP dependency selection. This is not legal advice; verify package licenses before release and keep notices with distributed artifacts where required.

## MVP extraction stack

Use standard document processing terminology in product UI. Do not describe OCR or rule-based parsing as AI extraction.

| Capability | Preferred dependency | License posture to verify | MVP guidance |
|---|---|---|---|
| PDF text extraction | `pypdf` and/or `pdfplumber` | Permissive/open-source expected; verify current PyPI/repo license and transitive dependencies | Prefer over PyMuPDF for closed-source SaaS MVP. |
| DOCX text extraction | `python-docx` | MIT/permissive expected; verify current package license | Use for uploaded Word documents. |
| OCR engine | Tesseract OCR | Apache 2.0 expected | Use for images and scanned PDFs as standard document processing. |
| Python OCR wrapper | `pytesseract` | Verify current package license | Wrapper only; still requires Tesseract runtime. |
| Image handling/preprocessing | `Pillow` | Permissive/open-source expected | Use for image loading/conversion/preprocessing. |
| Field extraction | SimpleTS-owned regex/template/rules code | SimpleTS-owned | Start with invoice header/summary fields only; no line items in MVP. |

## Dependencies to avoid for MVP unless licensing is resolved

- Avoid `PyMuPDF`/`fitz` for the MVP unless SimpleTS obtains a suitable commercial license or explicitly accepts AGPL obligations.
- Avoid managed OCR/document extraction services as the default MVP path because they introduce paid service dependencies and external document processing. They may be considered later behind explicit workspace settings and usage controls.

## Product language

- Standard/default path: **Standard document processing**.
- Explicit fallback action: **Improve extraction**.
- Usage impact copy should reference the workspace usage allowance, not AI tokens.

## MVP functional boundary

- Google Drive setup is required before document-upload workflows are enabled.
- Uploaded invoice files are placed in the client-owned Google Drive folder structure; SimpleTS stores pointers/metadata rather than durable file blobs.
- SimpleTS may use temporary processing cache only while actively extracting/reviewing.
- Review screen shows invoice header/summary fields, source labels, lightweight previous-value comparison where enhanced extraction changed a value, and supports reviewer edits.
- MVP invoice fields are optional at extraction time and exclude line items.

## Verification before implementation/release

1. Confirm each dependency's current license from its official repository or package metadata.
2. Record required copyright/license notices.
3. Check transitive dependencies for copyleft or commercial terms.
4. Confirm deployment packaging does not bundle tools under incompatible terms.
5. Re-check license posture when upgrading dependency versions.

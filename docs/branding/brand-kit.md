# Simple Technology Solutions Brand Kit

Status: authoritative developer-facing brand contract.  
Source assets: `docs/branding/Brand Kit_V1.0.docx` and PNG files in `docs/branding/`.

## Brand hierarchy

- Company/platform brand: **Simple Technology Solutions**.
- Acronym/monogram: **STS**.
- Product/app name: **SimpleTS**.
- STS branding is the required default for platform-owned UI, docs, generated assets, and public-facing copy.
- Workspace/client branding may override STS only in explicitly tenant-branded contexts, such as a subscriber workspace logo, client portal styling, or future workspace theme settings.
- Workspace/client branding must not obscure backend authority, workspace isolation, approval state, connector state, data safety, retention, or operational failure states.

## Core message

- Primary tagline: **Make Work Simple**.
- Hero headline: **Make Work Simple**.
- Website/product subheading: **We help businesses reduce costs and improve productivity by automating everyday operations and simplifying how work gets done.**
- Call to action: **Make work simple – start free**.
- Core message: make work simple through automation that reduces manual effort, improves productivity, lowers costs, and enables businesses to scale without increasing workload.

## Voice

Use language that is:

- clear and direct
- human and practical
- outcome-focused
- simple
- reliable and modern

Avoid language that is:

- buzzword-heavy
- overly technical where a simpler phrase works
- corporate jargon
- abstract or vague

## Colour system

| Role | Name | Hex | Usage |
| --- | --- | --- | --- |
| Primary | Midnight Indigo | `#150A32` | Logos, headers, key identity areas, dominant brand backgrounds |
| Secondary | Digital Teal | `#20B4C9` | Structure, secondary emphasis, supporting accents |
| Accent | Electric Mint | `#15F5BA` | CTAs, highlights, key focus moments; use sparingly |
| Neutral | White | `#FFFFFF` | Default clean background and high-contrast text on indigo |

Implementation guidance:

- Midnight Indigo should lead platform-owned chrome and identity moments.
- Digital Teal supports structure and variation without overpowering the primary brand.
- Electric Mint is reserved for high-value actions and highlights.
- White should remain the default clean content background where readability is the priority.

## Typography

| Use | Typeface | Weight | Size/spacing from source kit |
| --- | --- | --- | --- |
| Logo | Montserrat | Bold | As per logo lockup rules |
| H1 | Montserrat Black | Bold | 36–44pt; 18pt above / 6pt below; starts on new page in document contexts |
| H2 | Montserrat | Bold | 24–30pt; 12pt above / 6pt below |
| H3 | Montserrat | Medium | 18–22pt; 6pt above / 6pt below |
| Key statements | Montserrat | Bold as needed | Use only where emphasis improves clarity |
| Body/captions/docs/forms | Calibri | Regular | 11–12pt; 6pt above / 6pt below |

Implementation guidance:

- Use Montserrat for structure, headings, branding, and key messages.
- Use Calibri for body text, captions, notes, supporting content, forms, and instructions.
- For web surfaces where Calibri availability is uncertain, use `Calibri, Arial, sans-serif` as the body stack unless a specific implementation constraint requires another readable fallback.
- The source kit's final principles mention Open Sans for readability; treat that as superseded by the updated secondary typeface section naming Calibri.
- Do not introduce additional brand fonts without explicit approval.

## Logo system

### Primary logo

Use for major applications: website, proposals, marketing materials, presentations, and high-visibility platform identity surfaces.

Source asset: `STS - Logo - primary.png`.

### Secondary logo

Use where horizontal/vertical space is limited, including social headers, profile images, narrow layouts, and compact product chrome.

Source assets:

- `STS - logo - secondary.png`
- `STS - logo - web icon.png`

### Icon

Use for favicons, app icons, watermarks, compact UI marks, and mobile-tight layouts.

Source assets:

- `STS_logo_icon.png`
- `Simple Technology Solutions.png`

### Wordmark

Use where the full brand name needs to be clearly presented in vertical format, including stacked website headers, hero sections, presentation title slides, formal documents, and proposals.

Source asset: `STS_words.png`.

Generated white variant for dark app surfaces: `frontend/public/brand/sts-wordmark-white.png`.

### Logo rules

- Maintain clear space around the logo of at least the height of one “S”.
- Do not stretch, distort, rotate, recolour, or arbitrarily rescale logo elements.
- Do not place the logo on busy or low-contrast backgrounds.
- Prefer Midnight Indigo backgrounds or white space for clarity.
- STS monogram colours are fixed: S = Digital Teal, T = Electric Mint, S = Digital Teal.
- Full brand name lockup text is white on Midnight Indigo unless using an approved alternate asset.

## Textures and backgrounds

Use the circuit/network texture as a supporting background layer only.

Source assets:

- `STS_image.png` — plain background texture.
- `STS - Tag line w. background.png` — tagline composition over texture.

Rules:

- Use as a secondary visual layer behind content.
- Keep text fully readable.
- Keep Midnight Indigo dominant.
- Use teal sparingly as a supporting accent.
- Do not use the texture as a replacement for the logo or as a high-detail foreground visual.
- Do not combine it with mixed or unfiltered stock-image overlays.

## Asset inventory

| File | Dimensions | Type | Notes |
| --- | ---: | --- | --- |
| `Brand Kit_V1.0.docx` | n/a | Word document | Source brand kit |
| `STS - Logo - primary.png` | 2000×2000 | PNG/RGB | Primary lockup on Midnight Indigo |
| `STS - logo - secondary.png` | 555×532 | PNG/RGBA | Secondary STS monogram on Midnight Indigo |
| `STS - logo - web icon.png` | 555×532 | PNG/RGBA | Web icon variant; visually matches secondary logo |
| `STS_logo_icon.png` | 290×287 | PNG/RGBA | Compact icon |
| `Simple Technology Solutions.png` | 290×287 | PNG/RGBA | Compact icon duplicate/variant |
| `STS_words.png` | 521×379 | PNG/RGBA | Stacked wordmark |
| `STS_image.png` | 1414×923 | PNG/RGBA | Circuit/network background texture |
| `STS - Tag line w. background.png` | 1414×414 | PNG/RGBA | Tagline over circuit/network texture |

## Generated app assets

Generated frontend assets should live under `frontend/public/brand/` where possible, with top-level favicon files only when required by browser conventions.

Current expected generated assets:

- `frontend/public/sts-mark.svg` — scalable favicon/app icon.
- `frontend/public/brand/sts-logo-primary.png` — copied/normalised primary logo source.
- `frontend/public/brand/sts-logo-primary-cropped.png` — experimental cropped primary logo; do not use in app chrome unless placement is explicitly designed for the tighter crop.
- `frontend/public/brand/sts-logo-primary-dashboard.png` — moderately cropped primary logo for dashboard hero placement; keeps breathing room while improving lockup readability.
- `frontend/public/brand/sts-logo-secondary.png` — copied/normalised secondary logo source.
- `frontend/public/brand/sts-logo-web-icon.png` — copied/normalised web icon source.
- `frontend/public/brand/sts-logo-icon.png` — copied/normalised compact icon source.
- `frontend/public/brand/sts-wordmark.png` — copied/normalised wordmark source.
- `frontend/public/brand/sts-wordmark-white.png` — generated white wordmark for Midnight Indigo/dark app surfaces.
- `frontend/public/brand/sts-background-texture.png` — copied/normalised background texture source.
- `frontend/public/brand/sts-tagline-background.png` — copied/normalised tagline background source.

If higher-fidelity vector source files become available, prefer generated SVGs over traced or manually recreated logo approximations.

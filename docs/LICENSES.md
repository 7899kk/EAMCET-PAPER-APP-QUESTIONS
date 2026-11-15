# Licence audit and architecture decision

Checked 2026-11-13 against actual repository/package licence files, rather than assuming repository-wide uniform terms. Third-party works retain their own licences. This project's original application code is offered under **AGPL-3.0-or-later**; see `LICENSE`. This audit is an engineering record, not legal advice.

## Stirling PDF — investigated, not reused

Inspected current repository commit **ad38e38ce9bb59ee6b16cbc2d727b6a54c0fbda0** (committed 2026-11-13 14:55 UTC). Retained responses in `research/`, including its root and each named component's licence.

| Upstream location | Terms observed |
|---|---|
| Root `LICENSE` | MIT for content outside explicitly excluded directories |
| `engine/LICENSE` | **Stirling PDF User License**, production requires a valid user licence |
| `app/proprietary/LICENSE` | Stirling PDF User License |
| `app/saas/LICENSE` | Stirling PDF User License |
| `frontend/src/editor/proprietary/LICENSE` | Stirling PDF User License |
| `frontend/src/editor/desktop/LICENSE` | Stirling PDF User License |
| `frontend/src/editor/saas/LICENSE` | Stirling PDF User License |
| `frontend/src/editor/cloud/LICENSE` | Stirling PDF User License |
| `frontend/src/processor/LICENSE` | Stirling PDF User License |

The root README describes the current project as **open-core**, and advertises edit/merge/split/OCR/conversion tools. That does not establish that the current engine/editor is available under MIT or that generic text replacement is supported freely. Its current engine is not selected for this zero-budget, freely reusable implementation; no Stirling editor/backend source or binary is included. No claim is made that all older versions had these terms. Archived `research/LICENSE` belongs to Stirling, not this application.

Sources: [repository](https://github.com/Stirling-Tools/Stirling-PDF), [immutable root licence](https://github.com/Stirling-Tools/Stirling-PDF/blob/ad38e38ce9bb59ee6b16cbc2d727b6a54c0fbda0/LICENSE), [engine licence](https://github.com/Stirling-Tools/Stirling-PDF/blob/ad38e38ce9bb59ee6b16cbc2d727b6a54c0fbda0/engine/LICENSE), [official documentation](https://docs.stirlingpdf.com/). The official docs URL returned **HTTP 403** from this environment, so the implementation does not rely on unverified API documentation. The repository and licence files were reachable. The upstream commit metadata is in `research/upstream.json`.

## Components actually used

| Component | Version checked | Licence and reuse |
|---|---|---|
| PyMuPDF / MuPDF | 1.28.2 / 1.28.2 | AGPL-3.0 or Artifex commercial terms; this project chooses AGPL, no commercial key |
| pikepdf | 10.5.0 | MPL-2.0; used as an unmodified library |
| bundled qpdf | 12.3.2 | Apache-2.0 plus incorporated notices; no qtest used |
| FastAPI | 0.141.1 | MIT |
| Starlette | 1.6.0 | BSD-3-Clause |
| Uvicorn | 0.52.1 | BSD-3-Clause |
| python-multipart | 0.0.32 | Apache-2.0 |
| Pillow | 13.0.0 | MIT-CMU plus bundled codec notices in its licence |
| fontTools | 4.61.1 | MIT; incorporated components retain `LICENSE.external` |
| React / React DOM | 19.2.0 | MIT |
| PDF.js (`pdfjs-dist`) | 5.4.394 | Apache-2.0; a renderer, not the editing engine |
| Lucide React | 0.468.0 | ISC for code; additional bundled icon notices retained |
| Vite | 6.4.6 | MIT (including bundled dependency notices) |
| Vite React plugin | 4.7.0 | MIT |
| Tesseract (optional system executable) | installed system package | Apache-2.0; retained package copyright and language data notice |
| Leptonica (Tesseract dependency) | installed system package | BSD-style, incorporated codec notices in distro copyright |
| Poppler (test-only executable) | installed system package | GPL-2.0-or-later; invoked only for independent test extraction, not shipped as an app binary |
| DejaVu Sans (test fixture only) | system font | Bitstream Vera / Arev font terms; retained distro copyright |

Runtime Python transitive package licences were read from installed distribution metadata and their actual licence files. `research/python-licenses.json` records names/versions/terms; `THIRD_PARTY/python/` retains supplied notices. These include Pydantic / pydantic-core (MIT), anyio (MIT), h11 (MIT), Click (BSD-3-Clause), annotated-types / typing-inspection / annotated-doc (MIT), typing-extensions (PSF-2.0), idna (BSD-3-Clause), lxml (BSD-3-Clause plus its incorporated licences), Deprecated (MIT), wrapt (BSD-2-Clause), and packaging (Apache-2.0 OR BSD-2-Clause). Development-only test dependencies retain separate notices there too.

`research/npm-licenses.json` records **every installed npm package**, including transitive/build dependencies, from its manifest and the lockfile. Observed licence families are MIT, Apache-2.0, ISC, BSD-3-Clause, and CC-BY-4.0. CC-BY-4.0 applies to bundled browser-compatibility data, not all frontend code. Per-package actual notice files are retained in `THIRD_PARTY/npm/`. `frontend/package-lock.json` pins the resolved dependency graph.

### PDF.js asset licences are distinct

The readable text-layer/OCR-copy engine also embeds six unmodified fonts copied from the pinned PDF.js 5.4.394 standard-font assets. `backend/fonts/` retains the exact font files and both notices: Liberation Sans Regular/Bold are SIL OFL-1.1, with reserved names unchanged and document embedding permitted; Foxit Serif/SerifBold/Fixed/FixedBold use the permissive PDFium/Foxit terms in `LICENSE_FOXIT`. They are not relabelled as AGPL or fetched from a paid font service. These files are included in the corresponding source archive. Unicode encoding is used to avoid silently substituting question marks for punctuation.

These assets are copied locally, with their actual notices in `THIRD_PARTY/pdfjs/` and the build's asset directories:

- Foxit standard fonts: the permissive terms in `LICENSE_FOXIT`.
- Liberation fonts: **SIL Open Font License 1.1**, not Apache-2.0. Preserve reserved font names and font licence; do not relabel these fonts as AGPL.
- Character maps: Adobe's own redistribution terms in `cmaps/LICENSE`.
- OpenJPEG WASM: BSD-2-Clause plus PDF.js wrapper Apache-2.0 notices.
- qcms WASM: its permissive licence plus PDF.js wrapper notice.

Native wheels also incorporate libraries under their own terms (for example qpdf's bundled JPEG library, Pillow's codecs, and MuPDF's font/image parsers). The wheel/distro notices supplied upstream remain applicable; do not strip or relicense them when redistributing binaries. This deliverable supplies source and package manifests, not repackaged Python/native binaries. The retained qpdf notice describes its additional MIT/public-domain code; distro codec notices are preserved. Re-audit native wheel notices for any new platform/build you redistribute.

## Obligations

Free use does not remove licence obligations. Preserve attribution and licence text, keep font-specific terms, and provide corresponding app/engine source and build instructions when required by AGPL distribution or network use. Do not incorporate proprietary Stirling components under the root MIT label. No proprietary code or paid API is required by this application. Upgrading the engine or adding conversions requires another licence check.

### Inline font handling

The browser-compatible default set now also includes unmodified Liberation Serif Regular/Bold and Liberation Mono Regular/Bold from the installed `fonts-liberation` distribution. Their SIL OFL-1.1 terms and copyright are retained as `backend/fonts/LIBERATION-DISTRO-COPYRIGHT`, alongside `LICENSE_LIBERATION`; reserved names and font bytes are unchanged. These replace raw Type 1 defaults for browser font decoding. Existing Foxit notices/assets remain retained for prior compatibility.

Fonts extracted from a user's uploaded PDF are not application assets: they remain per-document/session data and are copied only into that user's edited PDF and authenticated browser font response. They are never committed to this repository. Unsupported font formats/shaping are left read-only rather than misrepresented as a successful edit.

# CLAUDE.md

Context for AI assistants working in this repo. Keep this file current as decisions get made.

## What this is

Take-home assessment for **Treasury IT Specialist (AI)**, Treasury Common Services Center.
Build an **AI-powered alcohol label verification app** for TTB (Alcohol and Tobacco Tax and Trade Bureau) compliance agents: given a label image and the application data, check that the label matches the application and meets the basic requirements.

- Full spec, copied verbatim: [docs/ASSIGNMENT.md](docs/ASSIGNMENT.md) (source: https://github.com/treasurytakehome-rgb/instructions)
- Questions go to take-home-test@treasury.gov. They also value "how you fill in gaps independently." Record our assumptions instead of asking about everything.
- Submission: Microsoft Form (repo URL + deployed URL). **Deadline: one week from receipt. TODO: fill in exact date.**
- AI use is allowed and **is itself being evaluated**.

## Deliverables (hard requirements)

1. **Source repo** containing:
   - All source code
   - README with setup and run instructions
   - Short documentation of approach, tools used, and assumptions made
2. **Deployed URL**: a working prototype that Treasury can open and test with no setup on their side.

## Evaluation criteria (from the spec)

Correctness and completeness of core requirements · code quality and organization · technical choices appropriate to the scope · UX and error handling · attention to requirements · creative problem-solving.

> "A working core application with clean code is preferred over ambitious but incomplete features. Document any trade-offs or limitations."

## Requirements extracted from the stakeholder interviews

The interviews hide most of the real requirements. Each one should map to a feature, a design decision, or a documented limitation.

### Core (must have)
| # | Requirement | Source |
|---|---|---|
| R1 | Compare label image against application data: brand name, class/type, alcohol content, net contents, government warning (plus bottler name/address and country of origin where applicable) | Sarah, Additional Context |
| R2 | **Results in about 5 seconds or less** per label, or agents won't use it | Sarah (bold in spec) |
| R3 | **Very simple UI** ("my mother could figure out," a 73-year-old). Clean and obvious, large targets, no hunting for buttons | Sarah |
| R4 | **Government warning is an exact match**: word-for-word, and `GOVERNMENT WARNING:` must be ALL CAPS **and bold**. Title case ("Government Warning") = reject | Jenny |
| R5 | **Judgment on trivial differences**: `STONE'S THROW` vs `Stone's Throw` should count as a match (case, punctuation, whitespace), and the reason should be shown | Dave |
| R6 | Standalone prototype, **no COLA integration** | Marcus |
| R7 | Store nothing sensitive. No persistence of uploads is needed or wanted | Marcus |

### High-value (strong signals, likely scored)
| # | Requirement | Source |
|---|---|---|
| R8 | **Batch upload** (200–300 applications at once from importers) | Sarah, Janet |
| R9 | Handle imperfect photos: angles, glare, bad lighting. At minimum, detect "can't read this" and say so clearly instead of guessing | Jenny ("maybe out of scope") |

### Environmental constraints (show we listened)
- **The firewall blocks outbound traffic to many domains.** A previous vendor failed because of this. Relying on a random third-party ML endpoint is a risk. Address it in the design (e.g., an Azure-hosted model, a local/offline OCR fallback, or a pluggable provider) and **write this reasoning into the README**.
- **They're on Azure** (FedRAMP; migrated in 2019). The COLA system is **.NET**. Deploying to Azure and/or choosing an Azure-friendly stack is a point in our favor, but not required.
- Agents are "drowning in routine matching." The tool assists the agent and does not replace them: results show **pass / needs review / fail** with evidence, and the agent keeps the final call.

### Reference: exact Government Warning text (27 CFR 16.21)
```
GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.
```
(Verify against ttb.gov / eCFR before relying on this.)

### Sample label from the spec
- Brand Name: `OLD TOM DISTILLERY`
- Class/Type: `Kentucky Straight Bourbon Whiskey`
- Alcohol Content: `45% Alc./Vol. (90 Proof)`
- Net Contents: `750 mL`
- Government Warning: standard text

The spec encourages generating extra test labels with AI image tools. We need good ones, bad ones (title-case warning, wrong ABV, missing warning), and messy photos.

## Architecture: decided vs. open

**Principle:** use AI to **read** the label, and deterministic code to **judge** it. The comparison and warning rules are explicit, testable code. We don't ask an LLM whether something is compliant. That makes results explainable and auditable, which suits a government context and addresses Dave's skepticism.

Rough pipeline:
1. **Input:** label image(s) and application fields (form for a single label; CSV/JSON plus images for a batch)
2. **Extract:** image → structured fields, plus warning text and a boldness/caps observation
3. **Compare:** per-field normalized matching (exact / normalized-equal / numeric-equivalent such as `45%` ↔ `90 Proof` / mismatch)
4. **Report:** per-field ✅ / ⚠️ / ❌, showing the label value next to the application value, with an overall verdict

### Open decisions (ask the user before building)
- [x] ~~Stack~~, ~~Extraction engine~~, ~~Hosting~~: see Decisions log
- [ ] **Extraction engine (original notes):** cloud vision LLM (e.g., Azure OpenAI GPT-4o-class or Claude; handles bold, glare, and layout well but depends on the network) vs. local OCR (Tesseract/PaddleOCR; works offline and fits the firewall, but is weak on bold detection and bad photos) vs. **pluggable provider with a fallback** (leaning this way)
- [ ] **Stack:** e.g., Python (FastAPI) + simple frontend, Next.js full-stack, or .NET (matches COLA, but slower to build). Choose based on the user's comfort; the user must be able to explain it in an interview
- [ ] **Hosting:** Azure App Service / Container Apps (matches their environment) vs. Vercel/Render/Fly (faster). The URL must stay up through review
- [ ] **Batch format:** multi-image upload + CSV mapping filename → fields? A ZIP? How are results shown and exported (CSV download)?
- [ ] **Beverage types:** spirits only, or wine/beer rules as well?
- [ ] **Image-quality handling:** preprocessing (deskew/contrast) vs. just detecting and flagging low confidence
- [ ] **Latency budget:** how to stay under 5s (model choice, image downscaling, parallel batch processing with a progress bar)

## How we're working

The user makes the decisions and the AI does most of the implementation. The user must understand every piece well enough to defend it in an interview.

1. **Plan before code.** Resolve the open decisions above with the user and record each one in the "Decisions log" below with a one-line rationale.
2. **Deploy a skeleton early** (day 1–2) so the deployment risk is gone before the deadline.
3. **Build in small, meaningful git commits.** The history should tell the story.
4. **Tests for the judging logic** (normalization, warning exact-match, ABV/proof equivalence). This is the core of correctness and the cheapest thing to test well.
5. **Keep [docs/AI_USAGE.md](docs/AI_USAGE.md) updated as we go:** which tools were used for what, where the AI was corrected or overridden, and how output was verified. The rubric evaluates AI use, so this is a deliverable.
6. **Final pass:** check every R# above against the app, do a fresh-clone run of the README steps, test the deployed URL in a private browser window, and write up limitations and trade-offs.

### Conventions
- No secrets in the repo. Use `.env` (gitignored) plus a committed `.env.example`.
- No persistence of uploaded images or data beyond the request/session.
- Accessibility: large fonts, high contrast, keyboard navigable, clear labels, plain-language errors (Section 508 / WCAG AA as a target).
- Every failure state gets a human-readable message (unreadable image, API timeout, bad CSV, wrong file type, oversized file).

## Decisions log
_(date: decision, rationale)_

- 2026-09-26: Deterministic comparison logic; AI only for extraction. Rationale: explainable, testable, auditable.
- 2026-09-26: Backend = Python + FastAPI. Rationale: fast to build; strong OCR/imaging ecosystem; user is comfortable with it.
- 2026-09-26: Extraction = pluggable provider interface. Vision LLM as primary (Claude via Anthropic API for now, swappable to Azure-hosted), local OCR (Tesseract) as offline fallback. Rationale: accuracy on bold/glare from the LLM; the fallback answers Marcus's firewall concern.
- 2026-09-26: Hosting = Azure (App Service or Container Apps). Rationale: TTB/Treasury already runs on Azure (FedRAMP); shows fit with their environment. User has prior Azure experience.
- 2026-09-26: No hard time budget; still prioritize core → deploy → batch → polish.

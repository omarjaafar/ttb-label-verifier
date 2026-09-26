# CLAUDE.md

Context for AI assistants working in this repo. Keep this file current as decisions get made.

## What this is

Take-home assessment for **Treasury IT Specialist (AI)**, Treasury Common Services Center.
Build an **AI-powered alcohol label verification app** for TTB (Alcohol and Tobacco Tax and Trade Bureau) compliance agents: given a label image and the application data, check that the label matches the application and meets the basic requirements.

- Full spec, copied verbatim: [docs/ASSIGNMENT.md](docs/ASSIGNMENT.md) (source: https://github.com/treasurytakehome-rgb/instructions)
- Questions go to take-home-test@treasury.gov. They also value "how you fill in gaps independently." Record our assumptions instead of asking about everything.
- Submission: Microsoft Form (repo URL + deployed URL). **Assessment received 2026-09-14 → due 2026-09-21 (one week). Already past due as of 2026-09-26: finish and submit ASAP.**
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
_None open. All resolved in the Decisions log._

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
Format: **decision**, then the alternatives considered, why this one, and the tradeoffs accepted. These become the README's "Approach & trade-offs" section.

### D1: AI extracts, deterministic code judges (2026-09-26)
- **Alternatives:** ask a vision LLM directly whether the label is compliant.
- **Why:** agents and auditors need to see *why* something failed (the label value next to the application value, and the rule applied). Rules written as code are unit-testable, give the same answer every time, and don't hallucinate a pass. This also answers Dave's concern ("you need judgment"): normalization rules encode the judgment explicitly (case, punctuation, whitespace), and anything uncertain becomes **Needs review** instead of a silent pass or fail.
- **Tradeoff:** rules must be written by hand and won't cover every edge case, so we default to "Needs review" when unsure.

### D2: Python + FastAPI backend (2026-09-26)
- **Alternatives:** .NET (matches COLA), Next.js full-stack.
- **Why:** Python has the best imaging/OCR ecosystem (Pillow, OpenCV, Tesseract bindings) and first-class LLM SDKs. FastAPI is async, so batch jobs can call the model concurrently, which matters for R2 (5s) and R8 (batch). Auto-generated OpenAPI docs make the service easy to integrate later. It's also the fastest stack for the developer.
- **Tradeoff:** it doesn't match their .NET estate. Mitigation: it's a standalone service behind an HTTP API (Marcus: no COLA integration), so the language is irrelevant to any future integration.

### D3: Pluggable extraction providers: Claude vision primary, local OCR fallback (2026-09-26)
- **Alternatives:** vision LLM only; local OCR only.
- **Why:** a vision LLM is far better at messy photos (R9), layout, and visually judging bold/all-caps on the warning header (R4), which OCR can't do reliably. But Marcus warned that their **firewall blocks many outbound ML endpoints**, which is what killed the last vendor. So extraction sits behind an interface: the LLM provider is swappable (for example, Azure OpenAI / Azure AI Foundry inside their tenant), and a local Tesseract provider works fully offline in degraded mode.
- **Tradeoff:** two code paths to maintain. OCR mode can't verify boldness, so it flags that check as "Needs review" instead of guessing. Using the Anthropic API directly in the prototype is a convenience; production would route through an approved endpoint.

### D4: Host on Azure (2026-09-26)
- **Alternatives:** Render, Vercel, or Fly (faster setup, less relevant).
- **Why:** Treasury/TTB migrated to Azure in 2019 and went through FedRAMP there (Marcus). A prototype already on Azure shows a realistic path to adoption: same cloud, same identity and network controls, Azure Government available for production. The developer also has prior Azure experience.
- **Tradeoff:** more setup than a one-click PaaS, and cold starts on lower tiers could threaten the 5s target, so we pick a tier/config that keeps an instance warm.

### D5: Secrets via environment variables (2026-09-26)
- Local: `.env` (gitignored), with `.env.example` committed. Azure: App Settings (Key Vault reference if time allows). Nothing secret in the repo, per Marcus: "just don't do anything crazy."

### D6: Prioritization (2026-09-26)
- No hard time budget, but the order is **core single-label check → tests → deploy → batch → image-quality handling → polish**, per the spec: "a working core application with clean code is preferred over ambitious but incomplete features."

### D7: One rule set for all beverage types; ABV optional for wine and beer (2026-09-26)
- **Alternatives:** separate rule sets per type (spirits / wine / malt), or spirits only.
- **Why:** the core checks (brand, class/type, net contents, bottler, country, government warning) apply to all three. The main difference agents run into is that alcohol content is mandatory for spirits but optional for some wine and beer (27 CFR 4.36 / 7.63). A beverage-type selector covers that without tripling the rules.
- **Tradeoff:** type-specific rules aren't checked (e.g., wine appellation/vintage, sulfite declarations, spirits age statements). These are documented as future work.

### D8: Plain HTML/CSS/JS frontend served by FastAPI (2026-09-26)
- **Alternatives:** React/Vite SPA.
- **Why:** one page and one form don't need a framework. No build step means one container and one deploy. Full control over accessibility (large type, 60px buttons, visible focus rings, status shown by icon + word + color, never color alone) for Sarah's "my mother could use it" bar.
- **Tradeoff:** batch-results UI state is managed by hand. Still small enough to stay readable.

### D9: "Not found" → Needs review; missing warning → Fail (2026-09-26)
- **Why:** if the extractor can't find a brand name, it's more likely a read miss than a missing brand, so a human should check rather than the tool auto-rejecting. The government warning is the exception: presence is easy to detect reliably and it's mandatory on every label, so absence is a hard fail.

### Measured: latency and accuracy on synthetic samples (2026-09-26)
`samples/run_eval.py`, 9 labels (good, case-diff brand, wrong ABV, title-case warning, non-bold heading, reworded warning, wrong volume, imported wine with unit conversion, angled/glare photo):
| Config | Accuracy | Latency |
|---|---|---|
| Opus 5, low effort, adaptive thinking | 9/9 (after bottler fix) | 4.1–5.8s single |
| **Sonnet 5, low effort, thinking off** | **9/9** | **~3.6s single, ~4.1s with 9 concurrent** |
| Haiku 4.5 | correct | 3.8–7.7s (inconsistent) |

### D10: Default model = Claude Sonnet 5, thinking disabled, low effort (2026-09-26)
- **Alternatives:** Opus 5 (adaptive thinking), Haiku 4.5.
- **Why:** Sarah's hard bar is about 5s ("nobody's going to use it" otherwise; the last vendor failed at 30–40s). On our samples, Sonnet 5 with thinking off was the only config that was **both** 9/9 accurate **and** consistently under 5s (~3.6s single, ~4.1s at 9 concurrent). Opus 5 was equally accurate but ranged 4–6s. Haiku was fast on average but spiky (up to 7.7s). The task is transcription, not reasoning (the rules engine does the judging), so extra model deliberation buys little. Sonnet is also cheaper per label, which matters at 150k labels/year.
- **Tradeoff:** less headroom on very hard images. Mitigations: model and thinking are env settings (`CLAUDE_MODEL`, `CLAUDE_THINKING`), and unreadable images come back as "Needs review" rather than a guess.

### D11: Batch runs in the browser, one request per label, 3 at a time (2026-09-26)
- **Alternatives:** one multipart upload of all images plus a server-side job queue; the Anthropic Message Batches API (50% cheaper, but asynchronous with up to 24h turnaround).
- **Why:** 300 phone photos can approach 1 GB, too much for a single request. Per-label requests reuse the tested `/api/verify` endpoint, give true progress, isolate failures (retry with backoff on 429/5xx), and keep the server **stateless**: no job store and nothing persisted (Marcus: no sensitive storage). Concurrency 3 stays under entry-tier API rate limits (~50 req/min).
- **Measured:** 9 labels in ~11s through the UI (headless Edge test), all verdicts correct.
- **Tradeoff:** the tab must stay open during a batch, and 300 labels take ~7 min at concurrency 3. Production would raise the rate-limit tier or concurrency; Message Batches fits overnight bulk runs.

### D12: Azure Container Apps, image built locally and pushed to ACR (2026-09-26)
- **Live URL:** https://ttb-label-verifier.jollysand-f9381f43.westus.azurecontainerapps.io
- **Resources** (subscription "Azure for Students", region **westus**, the only US region the student policy allows): resource group `rg-ttb-label-verifier`, registry `ca99e736d0b5acr`, environment `ttb-env`, app `ttb-label-verifier` (0.5 vCPU / 1 GiB, **min 1 replica** so there's no cold start against the 5s bar, max 3).
- **Secrets:** `ANTHROPIC_API_KEY` is stored as a Container Apps secret (`secretref:anthropic-key`) and never baked into the image (`.dockerignore` excludes `.env`). Container runs as a non-root user.
- **Why not `az containerapp up --source`:** student subscriptions block ACR Tasks (cloud builds), so the image is built with local Docker and pushed. The environment was created as an "express" environment, which doesn't support managed-identity registry pulls, so the registry admin credential is used (stored as an app secret). In production: managed identity + Key Vault on a standard environment, ideally in Azure Government.
- **Verified live:** health, single label (3.9s), 9-label batch in 12s through headless Edge, all verdicts correct. Round trip including upload is 4.2–5.2s.
- **Redeploy:** `docker build -t ca99e736d0b5acr.azurecr.io/ttb-label-verifier:vN .` → `az acr login -n ca99e736d0b5acr` → `docker push …:vN` → `az containerapp update -n ttb-label-verifier -g rg-ttb-label-verifier --image …:vN`.
- **Cost:** roughly $10–15/month (ACR Basic + one always-on replica), well within the $100 student credit. Tear down after review with `az group delete -n rg-ttb-label-verifier`.

### D13: No custom image preprocessing; rely on the vision model and flag unreadable images (2026-09-26)
- **Alternatives:** OpenCV deskew / perspective correction / glare removal / contrast enhancement before extraction.
- **Why:** the vision model already handled the rotated, blurred, glare-affected sample correctly (09_angled_glare_photo → pass). Classic preprocessing tuned for OCR can *hurt* a vision model (over-sharpening, and cropping errors that cut off the warning), and it adds latency against the 5s bar. We do the safe, cheap steps (EXIF auto-rotate, downscale to 1568px) and have the model report `image_readable` / `image_quality_note`, so a bad photo comes back as **Needs review: request a clearer image** instead of a guess. That's the honest version of Jenny's "maybe out of scope" ask.
- **Tradeoff:** very poor photos are still rejected to the agent rather than rescued. Preprocessing stays an option for the OCR fallback path only, where it helps more.

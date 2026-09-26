# How AI Was Used

AI was used in two places:
- **To build the project:** an AI coding assistant.
- **Inside the product:** a vision model reads the labels.

This page covers both, including where the AI got things wrong and how that was caught.

## Tools

| Tool | Role |
|---|---|
| **Claude Code** (Claude Opus 5.5), in VS Code | Pair programmer: requirements analysis, implementation, tests, debugging, Azure deployment commands, documentation drafts |
| **Claude Sonnet 5** (Anthropic API) | Runtime: transcribes label images into structured fields |
| Tesseract OCR | Runtime: offline, non-AI fallback |

## How the work was split

**I owned the decisions; the AI did most of the typing.** For each decision, the assistant laid out options and trade-offs, I chose, and the reasoning was recorded in a decision log ([CLAUDE.md](../CLAUDE.md#decisions-log)). The main decisions:

- **Stack:** Python/FastAPI and a plain-HTML frontend.
- **Extraction:** a swappable provider with an offline OCR fallback, because of the firewall concern.
- **Hosting:** Azure, to match Treasury's environment.
- **Model:** Claude Sonnet 5 with thinking off, chosen *after* seeing measured latency for four configurations.
- **Rules:** one rule set for all beverage types.
- **Photos:** no custom image preprocessing.
- **Ops:** scheduled auto-teardown of the cloud resources.

**The AI was used for:**
- **Requirements extraction:** turning the four stakeholder interviews into a numbered requirements list (R1–R9), which drove every later decision and the README's requirements table.
- **Implementation:** backend, rules engine, UI, batch mode, Dockerfile, and deployment, built in small commits.
- **Test generation:** unit tests for every rule, a generator for synthetic labels targeting each rule, a live evaluation script, and a headless-browser smoke test.
- **Operations:** running the Azure CLI deployment and adapting to student-subscription restrictions.

**What I kept under my own control:**
- Anything irreversible or security-sensitive needed my explicit approval. The API key stayed in a local `.env` and Azure secrets, never in chat or the repo. Granting a cloud job permission to delete resources was run by me, from a script I could read first.
- I reviewed screenshots and evaluation output rather than trusting "it works."

## Design principle for AI in the product

**The model reads; deterministic code judges.** The model's only job is to transcribe what's printed, returned through a strict JSON schema. It never decides compliance. Pass or fail comes from unit-tested Python rules that show the exact values compared. Where the tool is unsure, the result is *Needs review*, not a guess. I chose this because compliance decisions need to be explainable and repeatable, and because it makes AI mistakes visible instead of hidden.

## Where the AI was wrong, and how it was caught

Each problem below was caught by a verification step, not by assuming the output was right.

| # | What went wrong | How it was caught | Fix |
|---|---|---|---|
| 1 | The first rules flagged every correct label as "Needs review": the label said "*Bottled by* Old Tom Distillery" while the application said "Old Tom Distillery". | First live evaluation run: 5/9 correct. | Normalization strips standard role phrases (bottled by, imported by, etc.). Unit tests added. → 9/9. |
| 2 | The initial model configuration (Opus 5, adaptive thinking) took 4–9s, which missed the ~5s requirement. | Latency measured in the evaluation script. | Benchmarked 4 configurations on the same label, then chose Sonnet 5 with thinking off (~3.6s, consistent, still accurate). |
| 3 | The vision model "corrected" a non-compliant `Government Warning:` heading to `GOVERNMENT WARNING:` in its transcription (6 of 8 runs). The verdict was still right because a separate yes/no caps check caught it, but the screen showed contradictory text, and a combined error could have passed a bad label. | Reviewing a README screenshot, then a 10-run consistency test. | Added a dedicated "heading exactly as printed" field with an explicit example, and made the rule fail if *either* signal says "not all caps." → 10/10 transcribed correctly. |
| 4 | The "Checking…" spinner stayed on screen after results loaded (a CSS rule overrode the `hidden` attribute). | Screenshot from an automated headless-browser test. | A global `[hidden]` rule, verified by re-running the test. |
| 5 | The first deployment command failed: Azure for Students blocks cloud container builds, and the auto-created environment type doesn't support managed-identity registry access. | Error output during deployment. | Build the image locally, push it to the registry, and use registry credentials stored as an app secret. Recorded as a limitation, with the production alternative (managed identity + Key Vault). |

## How the output was verified

- **67 unit and API tests** on the judging logic and error handling. They run without network access.
- **Live evaluation:** 11 synthetic labels, each targeting one rule, run through the real model. Currently **11/11 correct**, median **4.2s**.
- **Headless-browser tests** of the real UI (single label and batch), locally and against the deployed URL.
- **Screenshots reviewed by eye** at each UI milestone. That's how issues 3 and 4 were found.
- **Container tested locally** (both AI and offline OCR modes, no `.env` inside the image, runs as a non-root user) before deploying.

## Takeaways

- **Measure the AI instead of trusting it.** The most important bug (#3) was invisible in the pass/fail numbers; it only showed up when I looked at what the model actually returned, across repeated runs.
- **Keep AI output narrow and structured.** A strict schema plus deterministic rules made every AI error show up as a specific, fixable field.
- **Next step:** the evaluation set is synthetic. Before any real use, I'd build an evaluation set from real, anonymized label photos, including rejected ones, and track accuracy per field.

import os

from dotenv import load_dotenv

load_dotenv()

EXTRACTION_PROVIDER = os.getenv("EXTRACTION_PROVIDER", "claude").lower()
# Sonnet 5 with thinking off: consistent ~3.6s with 9/9 accuracy on samples (see CLAUDE.md D10).
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
# Transcription rarely needs deliberation; "adaptive" turns reasoning back on at a latency cost.
CLAUDE_THINKING = os.getenv("CLAUDE_THINKING", "disabled").lower()
# Hard ceiling per model call; Sarah's bar is ~5s, so fail fast rather than hang.
EXTRACTION_TIMEOUT_S = float(os.getenv("EXTRACTION_TIMEOUT_S", "15"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "15")) * 1024 * 1024
# Public demo protection. 60/min comfortably covers batch mode (3 concurrent at ~4s = ~45/min).
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
# Global cap on label checks per day (~$6/day worst case at current model pricing).
RATE_LIMIT_PER_DAY = int(os.getenv("RATE_LIMIT_PER_DAY", "1000"))

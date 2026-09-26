import os

from dotenv import load_dotenv

load_dotenv()

EXTRACTION_PROVIDER = os.getenv("EXTRACTION_PROVIDER", "claude").lower()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5")
# "disabled" trades a little reasoning for speed; transcription rarely needs deliberation.
CLAUDE_THINKING = os.getenv("CLAUDE_THINKING", "adaptive").lower()
# Hard ceiling per model call; Sarah's bar is ~5s, so fail fast rather than hang.
EXTRACTION_TIMEOUT_S = float(os.getenv("EXTRACTION_TIMEOUT_S", "15"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "15")) * 1024 * 1024

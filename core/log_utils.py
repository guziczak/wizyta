import os
from collections import deque
from datetime import datetime
from pathlib import Path


LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "app.log"
STDOUT_LOG_FILE = LOG_DIR / "stdout.log"


def log(message: str) -> None:
    """Log to stdout and append to logs/app.log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} {message}"
    print(line, flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + os.linesep)
    except Exception:
        # Avoid crashing if log file cannot be written
        pass


def read_tail(path: Path, max_lines: int = 200) -> list[str]:
    """Return last N lines from a file, ignoring encoding errors."""
    try:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            return [line.rstrip("\n") for line in deque(f, maxlen=max_lines)]
    except Exception:
        return []

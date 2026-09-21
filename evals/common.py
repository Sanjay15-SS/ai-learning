import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from src import EVALS, ROOT, RUNS

CASES = EVALS / "cases.jsonl"
LABELS = ROOT / "labels_25.json"
PREDICTION = ROOT / "prediction.txt"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_jsonl(path: Path) -> list:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def write_jsonl(path: Path, rows) -> None:
    Path(path).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                          encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def load_cases() -> list:
    return read_jsonl(CASES)


def answers_path(app: str) -> Path:
    return RUNS / f"answers_{app}.jsonl"


def git_commit_of(path: Path):
    """(commit hash, commit time) of the first commit that added `path`, or None."""
    try:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%H %cI", "--", str(path)],
            cwd=ROOT, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = out.stdout.strip().splitlines()
    return tuple(lines[-1].split(" ", 1)) if out.returncode == 0 and lines else None

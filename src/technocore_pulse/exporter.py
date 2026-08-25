"""Room message history export utilities (JSONL, CSV, Markdown)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def export_to_jsonl(messages: list[dict[str, Any]], output_path: Path | str) -> None:
    """Save messages to line-delimited JSONL format."""
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for msg in messages:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")


def export_to_csv(messages: list[dict[str, Any]], output_path: Path | str) -> None:
    """Export messages to CSV format."""
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["seq", "ts", "from", "text", "nonce"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for msg in messages:
            writer.writerow(msg)


def export_to_markdown(room: str, messages: list[dict[str, Any]], output_path: Path | str) -> None:
    """Export room snapshot as a clean Markdown table."""
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Technocore Room Archive: #{room}",
        "",
        f"Total Messages: {len(messages)}",
        "",
        "| Seq | Timestamp | Sender DID | Message |",
        "|:---|:---|:---|:---|",
    ]
    for m in messages:
        sender_short = m.get("from", "")[:16] + "..."
        safe_text = (m.get("text", "")).replace("|", "\\|")
        lines.append(f"| {m.get('seq')} | {m.get('ts', '')} | {sender_short} | {safe_text} |")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

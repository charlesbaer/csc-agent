"""
Offline eval harness — runs the golden dataset through the agent and asserts quality.
Used by GitHub Actions CI. Also works locally: uv run python evals/run_evals.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import anthropic  # noqa: E402

from src.agent import agent as agent_module  # noqa: E402
from src.agent.types import Channel, Message  # noqa: E402
from src.config import get_config  # noqa: E402

PASS_THRESHOLD = 0.7
GOLDEN_SET = json.loads((Path(__file__).parent / "golden_set.json").read_text())
JUDGE_PROMPT = (Path(__file__).parent / "judge_prompt.txt").read_text()


def judge(input_text: str, expected: str, actual: str) -> tuple[float, str]:
    cfg = get_config()
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    prompt = (
        JUDGE_PROMPT.replace("{input}", input_text)
        .replace("{expected_output}", expected)
        .replace("{actual_output}", actual)
    )
    result = client.messages.create(
        model=cfg.anthropic_model,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = result.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    parsed = json.loads(raw)
    return parsed["score"], parsed.get("reason", "")


def _wrap(text: str, width: int) -> list[str]:
    """Split text into lines of at most width characters, preserving words."""
    words = text.replace("\n", " ").split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".lstrip()
    if current:
        lines.append(current)
    return lines or [""]


def _print_table(rows: list[dict]) -> None:
    cols = ["Status", "Score", "Prompt", "Response", "Judge"]
    keys = ["status", "score", "prompt", "response", "judge"]
    widths = [6, 5, 30, 40, 50]

    def cell(text: str, w: int) -> str:
        return text[:w].ljust(w)

    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    header = "|" + "|".join(f" {cell(c, w)} " for c, w in zip(cols, widths)) + "|"
    print(sep)
    print(header)
    print(sep)

    for row in rows:
        wrapped = [_wrap(str(row[k]), w) for k, w in zip(keys, widths)]
        n_lines = max(len(w) for w in wrapped)
        for i in range(n_lines):
            line = "|"
            for col_lines, w in zip(wrapped, widths):
                val = col_lines[i] if i < len(col_lines) else ""
                line += f" {cell(val, w)} |"
            print(line)
        print(sep)


RESULTS_FILE = Path(__file__).parent / "eval_results.md"


def _md_cell(text: str) -> str:
    return text.replace("\n", " ").replace("|", "\\|")


def _write_markdown(rows: list[dict], avg: float) -> None:
    failures = sum(1 for r in rows if r["status"] == "FAIL")
    overall = "PASSED" if avg >= PASS_THRESHOLD else "FAILED"
    lines = [
        f"# Eval Results",
        f"",
        f"**Overall: {overall}** — average score {avg:.2f} ({failures} failures / {len(rows)} total, threshold {PASS_THRESHOLD})",
        f"",
        f"| Status | Score | Prompt | Response | Judge |",
        f"|--------|-------|--------|----------|-------|",
    ]
    for row in rows:
        cols = [row["status"], row["score"], row["prompt"], row["response"], row["judge"]]
        lines.append("| " + " | ".join(_md_cell(c) for c in cols) + " |")
    RESULTS_FILE.write_text("\n".join(lines) + "\n")
    print(f"\nResults written to {RESULTS_FILE}")


def main() -> None:
    agent_module.load_knowledge()

    scores: list[float] = []
    rows: list[dict] = []

    for item in GOLDEN_SET:
        msg = Message(text=item["input"], channel=Channel.MESSENGER)
        response = agent_module.respond(msg)
        score, reason = judge(item["input"], item["expected_output"], response.text)
        scores.append(score)

        rows.append({
            "status": "PASS" if score >= PASS_THRESHOLD else "FAIL",
            "score": f"{score:.2f}",
            "prompt": item["input"],
            "response": response.text,
            "judge": reason,
        })

    _print_table(rows)

    failures = [r for r in rows if r["status"] == "FAIL"]
    avg = sum(scores) / len(scores) if scores else 0.0
    print(f"\nAverage score: {avg:.2f}  ({len(failures)} failures / {len(scores)} total)")

    _write_markdown(rows, avg)

    if avg < PASS_THRESHOLD:
        print(f"EVAL FAILED: average score {avg:.2f} < threshold {PASS_THRESHOLD}")
        sys.exit(1)

    print("EVAL PASSED")


if __name__ == "__main__":
    main()

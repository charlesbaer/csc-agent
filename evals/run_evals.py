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


def judge(input_text: str, expected: str, actual: str) -> float:
    cfg = get_config()
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    prompt = JUDGE_PROMPT.format(
        input=input_text, expected_output=expected, actual_output=actual
    )
    result = client.messages.create(
        model=cfg.anthropic_model,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = result.content[0].text.strip()
    return json.loads(raw)["score"]


def main() -> None:
    agent_module.load_knowledge()

    scores: list[float] = []
    failures: list[dict] = []

    for item in GOLDEN_SET:
        msg = Message(text=item["input"], channel=Channel.MESSENGER)
        response = agent_module.respond(msg)
        score = judge(item["input"], item["expected_output"], response.text)
        scores.append(score)

        status = "PASS" if score >= PASS_THRESHOLD else "FAIL"
        print(f"[{status}] {item['input'][:60]!r}  score={score:.2f}")
        if score < PASS_THRESHOLD:
            failures.append({"item": item, "actual": response.text, "score": score})

    avg = sum(scores) / len(scores) if scores else 0.0
    print(f"\nAverage score: {avg:.2f}  ({len(failures)} failures / {len(scores)} total)")

    if failures:
        print("\nFailed items:")
        for f in failures:
            print(f"  Q: {f['item']['input']}")
            print(f"  A: {f['actual'][:120]}")
            print(f"  Score: {f['score']:.2f}\n")

    if avg < PASS_THRESHOLD:
        print(f"EVAL FAILED: average score {avg:.2f} < threshold {PASS_THRESHOLD}")
        sys.exit(1)

    print("EVAL PASSED")


if __name__ == "__main__":
    main()

"""Upload evals/golden_set.json to the Langfuse 'csc-golden-set' dataset."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from langfuse import Langfuse  # noqa: E402
from src.config import get_config  # noqa: E402, I001

cfg = get_config()
lf = Langfuse(
    public_key=cfg.langfuse_public_key,
    secret_key=cfg.langfuse_secret_key,
    host=cfg.langfuse_host,
)

golden = json.loads((Path(__file__).parent.parent / "evals" / "golden_set.json").read_text())
dataset_name = "csc-golden-set"

lf.create_dataset(name=dataset_name)
for item in golden:
    lf.create_dataset_item(
        dataset_name=dataset_name,
        input=item["input"],
        expected_output=item["expected_output"],
        metadata=item.get("metadata", {}),
    )

print(f"Seeded {len(golden)} items into Langfuse dataset '{dataset_name}'.")

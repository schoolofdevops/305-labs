# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Generate promptfoo tests from the canonical golden set.

golden.yaml is the single source of truth for the whole course. promptfoo wants
its tests in its own shape, so rather than duplicate the questions we DERIVE the
generation-layer test file from golden.yaml. Run this after editing golden.yaml:

    uv run labs/m5/make_promptfoo_tests.py

It emits labs/opsmate/evals/generation-tests.yaml, referenced by promptfooconfig.yaml.

What it emits, per layer:
  generation  -> vars.query = the question; asserts:
                   - icontains-any over contains_any (wide lexical net)
                   - llm-rubric with the question's rubric (local judge)
  honesty     -> vars.query = the unanswerable question; asserts:
                   - icontains-any over refuse_any (the answer must admit the gap)
                   - llm-rubric: the answer must DECLINE, not invent one
                 An honesty test that the model "passes" by bluffing a confident
                 answer will fail the icontains-any net — which is the signal.

Retrieval-layer questions are NOT emitted here; they are checked deterministically
by retrieval_check.py against /retrieve, not by grading a generated answer.
"""
import os
import yaml

GOLDEN = os.environ.get("GOLDEN", "labs/opsmate/evals/golden.yaml")
OUT = os.environ.get("OUT", "labs/opsmate/evals/generation-tests.yaml")


def main() -> None:
    with open(GOLDEN, "r", encoding="utf-8") as fh:
        golden = yaml.safe_load(fh)

    tests = []
    for q in golden["questions"]:
        layer = q.get("layer")
        if layer == "generation":
            asserts = [{
                "type": "icontains-any",
                "value": q["contains_any"],
            }]
            if q.get("rubric"):
                asserts.append({"type": "llm-rubric", "value": q["rubric"].strip()})
            tests.append({
                "description": f"{q['id']} [{q['source']}]",
                "vars": {"query": q["question"]},
                "assert": asserts,
            })
        elif layer == "honesty":
            asserts = [{
                "type": "icontains-any",
                "value": q["refuse_any"],
            }, {
                "type": "llm-rubric",
                "value": (
                    "The assistant declines to answer because it has no runbook for "
                    "this question — it admits the gap rather than inventing steps, "
                    "commands, numbers, or a runbook name. If the answer confidently "
                    "provides a specific answer as if a runbook covered it, this FAILS."
                ),
            }]
            tests.append({
                "description": f"{q['id']} [honesty — unanswerable]",
                "vars": {"query": q["question"]},
                "assert": asserts,
            })
        # retrieval-layer questions are handled by retrieval_check.py

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("# GENERATED from golden.yaml by labs/m5/make_promptfoo_tests.py — do not edit by hand.\n")
        fh.write("# Regenerate: uv run labs/m5/make_promptfoo_tests.py\n")
        yaml.safe_dump(tests, fh, sort_keys=False, width=100, allow_unicode=True)

    n_gen = sum(1 for q in golden["questions"] if q.get("layer") == "generation")
    n_hon = sum(1 for q in golden["questions"] if q.get("layer") == "honesty")
    print(f"wrote {OUT}: {n_gen} generation + {n_hon} honesty tests = {len(tests)} total")


if __name__ == "__main__":
    main()

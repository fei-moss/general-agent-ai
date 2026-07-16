from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).parents[1]
MAKEFILE = ROOT / "Makefile"
RUNBOOK = ROOT / "docs/MARKETPLACE_QNA_RAG_INGESTION_RUNBOOK.md"
TARGETS = (
    "marketplace-qna-preflight",
    "marketplace-qna-local",
    "marketplace-qna-live",
    "marketplace-qna-final",
    "marketplace-qna-acceptance",
)


def _target_recipe(makefile: str, target: str) -> str:
    marker = f"{target}:"
    start = makefile.index(marker)
    lines = makefile[start:].splitlines()
    recipe = [lines[0]]
    for line in lines[1:]:
        if line.startswith("\t") or not line.strip():
            recipe.append(line)
            continue
        break
    return "\n".join(recipe)


def test_marketplace_qna_make_targets_are_declared_and_documented():
    makefile = MAKEFILE.read_text(encoding="utf-8")

    for target in TARGETS:
        assert f"{target}:" in makefile
        assert f"make {target}" in makefile
    phony = next(line for line in makefile.splitlines() if line.startswith(".PHONY:"))
    assert all(target in phony for target in TARGETS)


def test_marketplace_qna_preflight_checks_inputs_before_fixture_work():
    makefile = MAKEFILE.read_text(encoding="utf-8")
    recipe = _target_recipe(makefile, "marketplace-qna-preflight")
    checks = (
        "GEMINI_API_KEY is required",
        "MARKETPLACE_QNA_BASE_URL is required",
        "MARKETPLACE_QNA_KNOWLEDGE_BASE_ID is required",
        "Marketplace QnA ingestion summary is required",
    )

    assert all(check in recipe for check in checks)
    fixture_index = recipe.index("marketplace_qna_fixture_builder.py")
    assert all(recipe.index(check) < fixture_index for check in checks)


def test_marketplace_qna_targets_reuse_existing_authorities():
    makefile = MAKEFILE.read_text(encoding="utf-8")

    assert "marketplace_qna_golden_query_audit" in _target_recipe(
        makefile, "marketplace-qna-preflight"
    )
    local = _target_recipe(makefile, "marketplace-qna-local")
    assert "moss_gemini_preflight" in local
    assert "marketplace_qna_promptfooconfig.yaml" in local
    live = _target_recipe(makefile, "marketplace-qna-live")
    assert "marketplace_qna_live_eval" in live
    final = _target_recipe(makefile, "marketplace-qna-final")
    assert "$(MAKE) verify-release" in final
    assert "marketplace_qna_acceptance_validator" in final
    assert "marketplace_qna_acceptance_status" in final


def test_marketplace_qna_aggregate_target_is_fail_fast_and_ordered():
    makefile = MAKEFILE.read_text(encoding="utf-8")
    recipe = _target_recipe(makefile, "marketplace-qna-acceptance")
    commands = [
        "$(MAKE) marketplace-qna-preflight",
        "$(MAKE) marketplace-qna-local",
        "$(MAKE) marketplace-qna-live",
        "$(MAKE) marketplace-qna-final",
    ]

    assert all(command in recipe for command in commands)
    assert [recipe.index(command) for command in commands] == sorted(
        recipe.index(command) for command in commands
    )


def test_marketplace_qna_make_dry_run_is_ordered_without_secret_echo():
    secret = "gemini-test-secret-must-not-appear"
    env = {**os.environ, "GEMINI_API_KEY": secret}
    completed = subprocess.run(
        [
            "make",
            "-n",
            "marketplace-qna-acceptance",
            "MARKETPLACE_QNA_BASE_URL=https://example.invalid",
            "MARKETPLACE_QNA_KNOWLEDGE_BASE_ID=kb_example",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{completed.stdout}\n{completed.stderr}"

    assert completed.returncode == 0, output
    assert secret not in output
    stages = [
        "make marketplace-qna-preflight",
        "make marketplace-qna-local",
        "make marketplace-qna-live",
        "make marketplace-qna-final",
    ]
    assert [output.index(stage) for stage in stages] == sorted(
        output.index(stage) for stage in stages
    )

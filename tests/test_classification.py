import json
import os
import sys
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import evaluate_submission as ev
from lib import classification as cl
from lib import taxonomy as tx


class TestPromptBlock:
    def test_lists_every_category_with_definition_and_every_tag(self):
        block = cl.classification_prompt_block()
        for category in tx.CATEGORIES:
            assert f"- {category}: {tx.CATEGORY_DEFINITIONS[category]}" in block
        for tag in (*tx.WORKLOAD_TAGS, *tx.CROSS_CUTTING_TAGS):
            assert tag in block
        assert "region:" in block


class TestNormalizeClassification:
    def test_valid_workload_entry_is_untouched(self):
        data = {"category": "Workload Clouds", "tags": ["llm-inference", "gpu", "region:eu"]}
        assert cl.normalize_classification(data) == []
        assert data["tags"] == ["llm-inference", "gpu", "region:eu"]

    def test_invalid_category_falls_back_and_warns(self):
        data = {"category": "Databases & Storage", "tags": []}
        warnings = cl.normalize_classification(data)
        assert data["category"] == cl.DEFAULT_CATEGORY
        assert any("invalid category" in w for w in warnings)

    def test_unknown_tags_are_dropped(self):
        data = {"category": "Service Clouds", "tags": ["open-source", "made-up", "Region:CH"]}
        warnings = cl.normalize_classification(data)
        assert data["tags"] == ["open-source"]
        assert len(warnings) == 2

    def test_workload_tags_dropped_outside_workload(self):
        data = {"category": "Service Clouds", "tags": ["vector", "agent-native"]}
        warnings = cl.normalize_classification(data)
        assert data["tags"] == ["agent-native"]
        assert any("workload tag" in w for w in warnings)

    def test_workload_tags_capped_at_four(self):
        tags = ["vector", "llm-inference", "gpu", "app-hosting", "postgres-sql", "observability"]
        data = {"category": "Workload Clouds", "tags": tags}
        cl.normalize_classification(data)
        workload = [t for t in data["tags"] if t in tx.WORKLOAD_TAGS]
        assert len(workload) == cl.MAX_WORKLOAD_TAGS
        assert "gpu" in data["tags"]  # cross-cutting tags don't count toward the cap

    def test_duplicates_removed_and_order_kept(self):
        data = {"category": "Infrastructure Clouds", "tags": ["gpu", "region:ch", "gpu"]}
        cl.normalize_classification(data)
        assert data["tags"] == ["gpu", "region:ch"]

    def test_missing_or_malformed_tags_become_empty_list(self):
        for bad in (None, "gpu", 7, {"gpu": 1}):
            data = {"category": "Service Clouds", "tags": bad}
            cl.normalize_classification(data)
            assert data["tags"] == []
        data = {"category": "Service Clouds"}
        cl.normalize_classification(data)
        assert data["tags"] == []

    def test_non_string_tag_items_ignored(self):
        data = {"category": "Service Clouds", "tags": [1, None, "gpu"]}
        cl.normalize_classification(data)
        assert data["tags"] == ["gpu"]


class TestEvaluatorUsesTaxonomy:
    def test_categories_come_from_taxonomy(self):
        assert ev.CATEGORIES == list(tx.CATEGORIES)

    def test_qwen_metadata_returns_validated_tags(self):
        payload = json.dumps(
            {
                "name": "Acme",
                "description": "Provides inference.",
                "category": "Service Clouds",
                "tags": ["llm-inference", "open-source", "bogus"],
            }
        )
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content=payload))]
        client = MagicMock()
        client.chat.completions.create.return_value = response
        openai_mod = MagicMock()
        openai_mod.OpenAI.return_value = client
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {"QWEN_BASE_URL": "http://fake"}))
            stack.enter_context(patch.dict(sys.modules, {"openai": openai_mod}))
            result = ev.generate_metadata_with_qwen("https://acme.test", "x" * 200)
        assert result["category"] == "Service Clouds"
        assert result["tags"] == ["open-source"]
        prompt = client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
        assert "Workload Clouds:" in prompt and "llm-inference" in prompt

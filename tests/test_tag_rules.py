import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from lib import tag_rules as tr
from lib import taxonomy as tx


class TestProposeCategory:
    @pytest.mark.parametrize(
        ("legacy", "expected"),
        [
            ("Infrastructure Clouds", tx.INFRASTRUCTURE),
            ("GPU & AI Compute Clouds", tx.INFRASTRUCTURE),
            ("PaaS & Application Hosting", tx.WORKLOAD),
            ("Authorization, Identity & Fraud", tx.SERVICE),
        ],
    )
    def test_one_to_one_legacy_categories_are_deterministic(self, legacy, expected):
        assert tr.propose_category(legacy, "X", "Anything at all.") == (expected, False)

    def test_split_buckets_are_flagged_for_review(self):
        _, review = tr.propose_category("Databases & Storage", "X", "A database.")
        assert review is True

    def test_object_storage_is_infrastructure_but_managed_db_is_workload(self):
        assert (
            tr.propose_category("Databases & Storage", "X", "S3 object storage.")[0]
            == tx.INFRASTRUCTURE
        )
        assert (
            tr.propose_category("Databases & Storage", "X", "Managed Postgres.")[0] == tx.WORKLOAD
        )

    def test_sovereignty_hint_routes_to_sovereign(self):
        category, _ = tr.propose_category(
            "Security, Compliance & Sovereignty Clouds", "X", "Swiss data residency cloud."
        )
        assert category == tx.SOVEREIGN

    def test_security_without_sovereignty_is_service(self):
        category, _ = tr.propose_category(
            "Security, Compliance & Sovereignty Clouds", "X", "SOC 2 compliance automation."
        )
        assert category == tx.SERVICE

    def test_word_boundary_live_does_not_match_deliver(self):
        # "delivers" contains "live"; it must not be read as real-time/live video.
        category, _ = tr.propose_category(
            "Communications, IoT & Media", "Resend", "Delivers email."
        )
        assert category == tx.SERVICE

    def test_assistant_apps_are_service_but_hosted_apis_are_workload(self):
        assert (
            tr.propose_category("AI Assistants & Copilots", "X", "A chat assistant app.")[0]
            == tx.SERVICE
        )
        assert (
            tr.propose_category("AI Assistants & Copilots", "X", "Hosted agent API.")[0]
            == tx.WORKLOAD
        )

    @pytest.mark.parametrize(
        ("description", "expected"),
        [
            ("Feature flags platform.", tx.SERVICE),
            ("Rack-scale cloud computer.", tx.INFRASTRUCTURE),
            ("Open-source vector database.", tx.WORKLOAD),
            ("Something vague.", tx.SERVICE),
        ],
    )
    def test_unverified_entries_are_classified_from_text(self, description, expected):
        legacy = tx.UNVERIFIED_LEGACY_CATEGORY
        assert tr.propose_category(legacy, "X", description)[0] == expected

    def test_curated_override_wins_over_rules(self):
        assert tr.propose_category("Infrastructure Clouds", "Baseten", "GPU servers.") == (
            tx.WORKLOAD,
            False,
        )
        assert (
            tr.propose_category("Infrastructure Clouds", "cloudscale.ch", "VMs.")[0] == tx.SOVEREIGN
        )


class TestWorkloadTags:
    def test_legacy_prior_comes_first(self):
        tags = tr.propose_workload_tags("AI Inference & Model APIs", "X", "Fast serving.")
        assert tags[0] == "llm-inference"

    @pytest.mark.parametrize(
        ("description", "tag"),
        [
            ("Platform for building and deploying modern web applications.", "web-frontend"),
            ("Build and host apps, websites, and agent workflows.", "web-frontend"),
            ("A platform for running Next.js websites.", "web-frontend"),
            ("Open-source vector database.", "vector"),
            ("Headless browser infrastructure for agents.", "agent-browser"),
            ("Secure sandbox for AI code execution.", "agent-sandbox"),
            ("Distributed document-based NoSQL database.", "nosql-timeseries"),
        ],
    )
    def test_keyword_rules(self, description, tag):
        assert tag in tr.propose_workload_tags("Workload Clouds", "X", description)

    @pytest.mark.parametrize(
        "description",
        [
            "Provides web scraping and crawling API that converts websites into markdown.",
            "Platform for running headless browsers that interact with websites.",
            "Domain registration, web hosting, email, SSL certificates, and website security.",
            "Generate full-stack web apps from a single prompt.",
        ],
    )
    def test_web_frontend_does_not_match_scraping_registrars_or_generators(self, description):
        assert "web-frontend" not in tr.propose_workload_tags("Workload Clouds", "X", description)

    def test_capped_and_all_valid(self):
        text = "serverless function edge function wasm postgres redis vector warehouse etl llm"
        tags = tr.propose_workload_tags("Workload Clouds", "X", text)
        assert len(tags) <= tr.MAX_WORKLOAD_TAGS
        assert all(tx.is_valid_tag(t) for t in tags)


class TestProposeTags:
    def test_workload_tags_only_on_workload(self):
        text = "Open-source vector database."
        assert "vector" in tr.propose_tags("Databases & Storage", "X", text, tx.WORKLOAD)
        assert "vector" not in tr.propose_tags("Databases & Storage", "X", text, tx.SERVICE)

    def test_cross_cutting_tags_apply_to_every_category(self):
        text = "Open-source, self-hosted, agent-native MCP server on GPUs in Switzerland."
        for category in tx.CATEGORIES:
            tags = tr.propose_tags("Infrastructure Clouds", "X", text, category)
            assert {"open-source", "agent-native", "gpu", "region:ch"} <= set(tags)

    def test_owns_hardware_requires_infrastructure_legacy(self):
        text = "Operates its own data centers with dedicated servers."
        assert "owns-hardware" in tr.propose_tags(
            "Infrastructure Clouds", "X", text, tx.INFRASTRUCTURE
        )
        assert "owns-hardware" not in tr.propose_tags(
            "Developer Tooling & CI/CD", "X", text, tx.SERVICE
        )

    def test_region_europe_maps_to_eu(self):
        assert "region:eu" in tr.propose_tags(
            "Infrastructure Clouds", "X", "Hosted in Europe.", tx.INFRASTRUCTURE
        )

    def test_every_curated_override_is_valid(self):
        for name, (category, tags) in tr.CURATED_OVERRIDES.items():
            assert category in tx.CATEGORIES, name
            assert all(tx.is_valid_tag(t) for t in tags), name
            if category != tx.WORKLOAD:
                assert not (set(tags) & set(tx.WORKLOAD_TAGS)), name
            assert tr.propose_tags("Infrastructure Clouds", name.title(), "x", category) == tags

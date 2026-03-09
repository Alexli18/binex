"""T026/T028: Verify example YAML files load correctly and have valid structure."""

from __future__ import annotations

from pathlib import Path

import yaml

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _load_yaml(name: str) -> dict:
    path = EXAMPLES_DIR / name
    assert path.exists(), f"Example file not found: {path}"
    with open(path) as f:
        return yaml.safe_load(f)


# --- T025 / T026: human-in-the-loop.yaml -----------------------------------


class TestHumanInTheLoop:
    def test_loads_successfully(self):
        data = _load_yaml("human-in-the-loop.yaml")
        assert data["name"] == "human-in-the-loop"

    def test_has_expected_nodes(self):
        data = _load_yaml("human-in-the-loop.yaml")
        nodes = data["nodes"]
        assert set(nodes.keys()) == {"builder", "confirm_payment", "pay", "cancel"}

    def test_builder_node_structure(self):
        node = _load_yaml("human-in-the-loop.yaml")["nodes"]["builder"]
        assert node["agent"] == "local://echo"
        assert node["outputs"] == ["order"]

    def test_confirm_payment_depends_on_builder(self):
        node = _load_yaml("human-in-the-loop.yaml")["nodes"]["confirm_payment"]
        assert node["agent"] == "human://approve"
        assert "builder" in node["depends_on"]
        assert node["outputs"] == ["decision"]

    def test_pay_has_when_condition(self):
        node = _load_yaml("human-in-the-loop.yaml")["nodes"]["pay"]
        assert node["when"] == "${confirm_payment.decision} == approved"
        assert "confirm_payment" in node["depends_on"]

    def test_cancel_has_when_condition(self):
        node = _load_yaml("human-in-the-loop.yaml")["nodes"]["cancel"]
        assert node["when"] == "${confirm_payment.decision} == rejected"
        assert "confirm_payment" in node["depends_on"]


# --- T027 / T028: conditional-routing.yaml ----------------------------------


class TestConditionalRouting:
    def test_loads_successfully(self):
        data = _load_yaml("conditional-routing.yaml")
        assert data["name"] == "conditional-routing"

    def test_has_expected_nodes(self):
        data = _load_yaml("conditional-routing.yaml")
        nodes = data["nodes"]
        assert set(nodes.keys()) == {
            "classifier",
            "premium_handler",
            "standard_handler",
            "reporter",
        }

    def test_classifier_node(self):
        node = _load_yaml("conditional-routing.yaml")["nodes"]["classifier"]
        assert node["agent"] == "local://echo"
        assert node["outputs"] == ["category"]

    def test_premium_handler_when_equals(self):
        node = _load_yaml("conditional-routing.yaml")["nodes"]["premium_handler"]
        assert node["when"] == "${classifier.category} == premium"
        assert "classifier" in node["depends_on"]

    def test_standard_handler_when_not_equals(self):
        node = _load_yaml("conditional-routing.yaml")["nodes"]["standard_handler"]
        assert node["when"] == "${classifier.category} != premium"
        assert "classifier" in node["depends_on"]

    def test_reporter_depends_on_both_handlers(self):
        node = _load_yaml("conditional-routing.yaml")["nodes"]["reporter"]
        assert "premium_handler" in node["depends_on"]
        assert "standard_handler" in node["depends_on"]


# --- T028: Verify all example YAMLs are loadable ----------------------------


class TestAllExamplesLoadable:
    """Smoke test: every .yaml in examples/ must parse without errors."""

    def test_all_examples_parse(self):
        yaml_files = sorted(EXAMPLES_DIR.glob("*.yaml"))
        assert len(yaml_files) >= 2, "Expected at least 2 example YAML files"
        for path in yaml_files:
            with open(path) as f:
                data = yaml.safe_load(f)
            assert "name" in data, f"{path.name} missing 'name' field"
            assert "nodes" in data, f"{path.name} missing 'nodes' field"

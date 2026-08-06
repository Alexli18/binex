"""Tests for src/binex/eval/loader.py (T009, T017)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from binex.eval.loader import load_suite
from binex.eval.models import EvalSuite


@pytest.fixture
def tmp_workflow(tmp_path: Path) -> Path:
    """Create a minimal workflow YAML file."""
    wf = tmp_path / "simple.yaml"
    wf.write_text(
        textwrap.dedent("""\
        name: simple
        agents:
          worker:
            agent: local://echo
        nodes:
          - id: worker
        """)
    )
    return wf


@pytest.fixture
def basic_suite_path(tmp_path: Path, tmp_workflow: Path) -> Path:
    """Create a minimal valid suite YAML."""
    suite = tmp_path / "suite.yaml"
    suite.write_text(
        textwrap.dedent(f"""\
        name: my-suite
        workflow: {tmp_workflow}
        cases:
          - id: case-1
            inputs:
              input: "hello"
            asserts:
              - type: contains
                value: hello
        """)
    )
    return suite


class TestLoadSuiteValid:
    def test_loads_minimal_suite(self, basic_suite_path: Path):
        suite = load_suite(basic_suite_path)
        assert isinstance(suite, EvalSuite)
        assert suite.name == "my-suite"
        assert len(suite.cases) == 1
        assert suite.cases[0].id == "case-1"

    def test_resolves_workflow_path(self, basic_suite_path: Path, tmp_workflow: Path):
        suite = load_suite(basic_suite_path)
        # workflow path stored as resolved absolute
        assert Path(suite.workflow).exists()

    def test_case_inputs_loaded(self, basic_suite_path: Path):
        suite = load_suite(basic_suite_path)
        assert suite.cases[0].inputs == {"input": "hello"}

    def test_suite_thresholds_default(self, basic_suite_path: Path):
        suite = load_suite(basic_suite_path)
        assert suite.thresholds.min_similarity is None

    def test_suite_with_thresholds(self, tmp_path: Path, tmp_workflow: Path):
        suite_file = tmp_path / "s.yaml"
        suite_file.write_text(
            textwrap.dedent(f"""\
            name: thresh-suite
            workflow: {tmp_workflow}
            thresholds:
              min_similarity: 0.85
              max_cost_delta: 0.10
            cases:
              - id: c1
            """)
        )
        suite = load_suite(suite_file)
        assert suite.thresholds.min_similarity == 0.85
        assert suite.thresholds.max_cost_delta == 0.10

    def test_baseline_run_id_tolerated_with_warning(
        self, tmp_path: Path, tmp_workflow: Path, recwarn
    ):
        suite_file = tmp_path / "s.yaml"
        suite_file.write_text(
            textwrap.dedent(f"""\
            name: s
            workflow: {tmp_workflow}
            cases:
              - id: c1
                baseline_run_id: run_abc123
            """)
        )
        suite = load_suite(suite_file)
        # Should not crash; warning issued
        assert suite.cases[0].id == "c1"

    def test_all_assert_types(self, tmp_path: Path, tmp_workflow: Path):
        suite_file = tmp_path / "s.yaml"
        suite_file.write_text(
            textwrap.dedent(f"""\
            name: s
            workflow: {tmp_workflow}
            cases:
              - id: c1
                asserts:
                  - type: contains
                    value: "hello"
                  - type: not_contains
                    value: "error"
                  - type: regex
                    pattern: "\\\\d{{4}}"
                  - type: json_path
                    path: "$.questions"
                    exists: true
            """)
        )
        suite = load_suite(suite_file)
        assert len(suite.cases[0].asserts) == 4

    def test_accepts_string_path(self, basic_suite_path: Path):
        suite = load_suite(str(basic_suite_path))
        assert suite.name == "my-suite"


class TestLoadSuiteErrors:
    def test_missing_name(self, tmp_path: Path, tmp_workflow: Path):
        suite_file = tmp_path / "s.yaml"
        suite_file.write_text(
            textwrap.dedent(f"""\
            workflow: {tmp_workflow}
            cases:
              - id: c1
            """)
        )
        with pytest.raises(ValueError, match="missing required field 'name'"):
            load_suite(suite_file)

    def test_missing_workflow(self, tmp_path: Path):
        suite_file = tmp_path / "s.yaml"
        suite_file.write_text(
            textwrap.dedent("""\
            name: s
            cases:
              - id: c1
            """)
        )
        with pytest.raises(ValueError, match="missing required field 'workflow'"):
            load_suite(suite_file)

    def test_missing_cases(self, tmp_path: Path, tmp_workflow: Path):
        suite_file = tmp_path / "s.yaml"
        suite_file.write_text(
            textwrap.dedent(f"""\
            name: s
            workflow: {tmp_workflow}
            """)
        )
        with pytest.raises(ValueError, match="missing required field 'cases'"):
            load_suite(suite_file)

    def test_workflow_not_found(self, tmp_path: Path):
        suite_file = tmp_path / "s.yaml"
        suite_file.write_text(
            textwrap.dedent("""\
            name: s
            workflow: nonexistent.yaml
            cases:
              - id: c1
            """)
        )
        with pytest.raises(ValueError, match="Workflow not found"):
            load_suite(suite_file)

    def test_empty_cases(self, tmp_path: Path, tmp_workflow: Path):
        suite_file = tmp_path / "s.yaml"
        suite_file.write_text(
            textwrap.dedent(f"""\
            name: s
            workflow: {tmp_workflow}
            cases: []
            """)
        )
        with pytest.raises(ValueError, match="at least one case"):
            load_suite(suite_file)

    def test_duplicate_case_ids(self, tmp_path: Path, tmp_workflow: Path):
        suite_file = tmp_path / "s.yaml"
        suite_file.write_text(
            textwrap.dedent(f"""\
            name: s
            workflow: {tmp_workflow}
            cases:
              - id: dup
              - id: dup
            """)
        )
        with pytest.raises(ValueError, match="Duplicate case id 'dup'"):
            load_suite(suite_file)

    def test_unknown_assert_type(self, tmp_path: Path, tmp_workflow: Path):
        suite_file = tmp_path / "s.yaml"
        suite_file.write_text(
            textwrap.dedent(f"""\
            name: s
            workflow: {tmp_workflow}
            cases:
              - id: c1
                asserts:
                  - type: bad_type
                    value: x
            """)
        )
        with pytest.raises(ValueError, match="Unknown assert type"):
            load_suite(suite_file)

    def test_assert_missing_required_field(self, tmp_path: Path, tmp_workflow: Path):
        suite_file = tmp_path / "s.yaml"
        suite_file.write_text(
            textwrap.dedent(f"""\
            name: s
            workflow: {tmp_workflow}
            cases:
              - id: c1
                asserts:
                  - type: contains
            """)
        )
        with pytest.raises(ValueError, match="requires 'value'"):
            load_suite(suite_file)

    def test_threshold_out_of_range(self, tmp_path: Path, tmp_workflow: Path):
        suite_file = tmp_path / "s.yaml"
        suite_file.write_text(
            textwrap.dedent(f"""\
            name: s
            workflow: {tmp_workflow}
            thresholds:
              min_similarity: 1.5
            cases:
              - id: c1
            """)
        )
        with pytest.raises(ValueError, match="min_similarity"):
            load_suite(suite_file)

    def test_yaml_parse_error(self, tmp_path: Path):
        suite_file = tmp_path / "s.yaml"
        suite_file.write_text("name: [\ninvalid yaml")
        with pytest.raises(ValueError):
            load_suite(suite_file)

    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_suite(tmp_path / "does_not_exist.yaml")

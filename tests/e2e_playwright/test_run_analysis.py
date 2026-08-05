"""E2E: Run analysis pages — Debug, Trace, Diagnose from a real run."""

from playwright.sync_api import Page, Route, expect

FAKE_RUNS = {
    "runs": [
        {
            "run_id": "run_fake_0001",
            "workflow_name": "mocked-workflow",
            "status": "completed",
            "started_at": "2026-08-05T10:00:00Z",
            "completed_at": "2026-08-05T10:01:00Z",
            "total_nodes": 3,
            "completed_nodes": 3,
            "failed_nodes": 0,
        }
    ]
}

FAKE_RUN = {
    "run_id": "run_fake_0001",
    "workflow_name": "my-fake-workflow",
    "workflow_path": "/Users/alex/Desktop/Binex/examples/ollama-research.yaml",
    "status": "completed",
    "started_at": "2026-03-14T17:31:20.856780Z",
    "completed_at": "2026-03-14T17:32:19.928865Z",
    "total_nodes": 5,
    "completed_nodes": 5,
    "failed_nodes": 0,
    "skipped_nodes": 0,
    "forked_from": None,
    "forked_at_step": None,
    "resumed_from": None,
    "workflow_hash": "fefb3757eb8def79927b4cc1c2fffbed3881057992c550ce3a89bb06fbca0d34",
    "total_cost": 0.0,
    "git_sha": None,
    "git_dirty": False,
    "observed": False
}

FAKE_DEBUG = {
    "run_id": "run_fake_0001",
    "status": "completed",
    "workflow_name": "my-fake-workflow",
    "workflow_path": "/Users/alex/Desktop/Binex/examples/ollama-research.yaml",
    "nodes": [
        {
            "node_id": "A",
            "status": "completed",
            "started_at": "2026-03-14T17:31:20.859165+00:00",
            "completed_at": None,
            "duration_s": 0.001,
            "error": None,
            "agent": "human://output",
            "system_prompt": None,
            "model": None,
            "input_artifacts": [],
            "artifacts": [
                {
                    "id": "art_4202f1f19ed8",
                    "type": "human_output",
                    "content": "",
                    "produced_by": "A"
                }
            ]
        }
    ]
}

FAKE_TRACE = {
    "run_id": "run_fake_0001",
    "status": "completed",
    "total_duration_s": 59.072,
    "timeline": [
        {
            "node_id": "A",
            "status": "completed",
            "started_at": "2026-03-14T17:31:20.859165+00:00",
            "completed_at": None,
            "duration_s": 0.001,
            "offset_s": 0.001,
            "error": None
        }
    ]
}

FAKE_DIAGNOSE = {
    "run_id": "run_fake_0001",
    "status": "clean",
    "root_cause": None,
    "affected_nodes": [],
    "latency_anomalies": [],
    "recommendations": [],
    "severity": "NONE",
    "total_cost": 0.0,
    "root_causes": []
}

FAKE_LINEAGE = {
    "run_id": "run_fake_0001",
    "nodes": [
        {
            "id": "art_4202f1f19ed8",
            "type": "human_output",
            "content": "",
            "produced_by": "A"
        }
    ],
    "edges": []
}

def _mock_run_api(page) -> None:
    """Mock the API responses for a run and its analysis pages."""
    def handle_run(route: Route) -> None:
        route.fulfill(json=FAKE_RUN)
    page.route("**/api/v1/runs/run_fake_0001", handle_run)

    def handle_runs(route: Route) -> None:
        route.fulfill(json=FAKE_RUNS)
    page.route("**/api/v1/runs*", handle_runs)

    def handle_debug(route: Route) -> None:
        route.fulfill(json=FAKE_DEBUG)
    page.route("**/api/v1/runs/run_fake_0001/debug?errors_only=false", handle_debug)

    def handle_trace(route: Route) -> None:
        route.fulfill(json=FAKE_TRACE)
    page.route("**/api/v1/runs/run_fake_0001/trace", handle_trace)

    def handle_diagnose(route: Route) -> None:
        route.fulfill(json=FAKE_DIAGNOSE)
    page.route("**/api/v1/runs/run_fake_0001/diagnose", handle_diagnose)

    def handle_lineage(route: Route) -> None:
        route.fulfill(json=FAKE_LINEAGE)
    page.route("**/api/v1/runs/run_fake_0001/lineage", handle_lineage)

def test_run_analysis_pages(page: Page) -> None:
    """Test run analysis pages (Debug, Trace, Diagnose) for a real run."""
    _mock_run_api(page)
    page.goto("/")
    # Find first run link in the table
    first_run = page.locator('[data-testid^="dashboard-run-link-run_"]').first
    expect(first_run).to_be_visible()
    expect(first_run).to_have_attribute("href", "/runs/run_fake_0001")

def test_run_analysis_pages_debug(page: Page) -> None:
    """Test the Debug page for a real run."""
    _mock_run_api(page)
    page.goto("/runs/run_fake_0001/debug")
    expect(page.get_by_role("heading", name="Debug").first).to_be_visible()
    # Should have node list
    page.get_by_test_id("debug-node-A")
    expect(page.get_by_test_id("debug-node-A")).to_be_visible()

def test_run_analysis_pages_trace(page: Page) -> None:
    """Test the Trace page for a real run."""
    _mock_run_api(page)
    page.goto("/runs/run_fake_0001/trace")
    expect(page.get_by_role("heading", name="Trace").first).to_be_visible()
    # Should have trace content
    expect(page.get_by_role("button", name="A — completed, 0.001s")).to_be_visible()

def test_run_analysis_pages_diagnose(page: Page) -> None:
    """Test the Diagnose page for a real run."""
    _mock_run_api(page)
    page.goto("/runs/run_fake_0001/diagnose")
    expect(page.get_by_role("heading", name="Diagnosis").first).to_be_visible()
    # Should have diagnose content
    expect(page.get_by_text("No issues detected")).to_be_visible()

def test_run_analysis_pages_lineage(page: Page) -> None:
    """Test the Lineage page for a real run."""
    _mock_run_api(page)
    page.goto("/runs/run_fake_0001/lineage")
    expect(page.get_by_role("heading", name="Artifact Lineage").first).to_be_visible()
    # Should have lineage content
    expect(page.get_by_text("art_4202f1f19ed8")).to_be_visible()

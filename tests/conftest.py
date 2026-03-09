"""Shared test fixtures for Binex test suite."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_workflow_dict() -> dict:
    """Minimal 2-node workflow spec as a dict."""
    return {
        "name": "test-workflow",
        "description": "A simple test workflow",
        "nodes": {
            "producer": {
                "agent": "local://echo",
                "system_prompt": "produce",
                "inputs": {"data": "${user.input}"},
                "outputs": ["result"],
            },
            "consumer": {
                "agent": "local://echo",
                "system_prompt": "consume",
                "inputs": {"data": "${producer.result}"},
                "outputs": ["final"],
                "depends_on": ["producer"],
            },
        },
        "defaults": {
            "deadline_ms": 30000,
            "retry_policy": {"max_retries": 1, "backoff": "exponential"},
        },
    }


@pytest.fixture
def sample_research_workflow_dict() -> dict:
    """5-node research pipeline workflow spec as a dict."""
    return {
        "name": "research-pipeline",
        "description": "Multi-agent research pipeline",
        "nodes": {
            "planner": {
                "agent": "local://planner",
                "system_prompt": "planning.research",
                "inputs": {"query": "${user.query}"},
                "outputs": ["execution_plan"],
            },
            "researcher_1": {
                "agent": "local://researcher",
                "system_prompt": "research.search",
                "inputs": {
                    "plan": "${planner.execution_plan}",
                    "source": "arxiv",
                },
                "outputs": ["search_results"],
                "depends_on": ["planner"],
            },
            "researcher_2": {
                "agent": "local://researcher",
                "system_prompt": "research.search",
                "inputs": {
                    "plan": "${planner.execution_plan}",
                    "source": "google_scholar",
                },
                "outputs": ["search_results"],
                "depends_on": ["planner"],
            },
            "validator": {
                "agent": "local://validator",
                "system_prompt": "analysis.validate",
                "inputs": {
                    "results_1": "${researcher_1.search_results}",
                    "results_2": "${researcher_2.search_results}",
                },
                "outputs": ["validated_results"],
                "depends_on": ["researcher_1", "researcher_2"],
                "retry_policy": {"max_retries": 2, "backoff": "exponential"},
            },
            "summarizer": {
                "agent": "local://summarizer",
                "system_prompt": "analysis.summarize",
                "inputs": {"validated": "${validator.validated_results}"},
                "outputs": ["summary_report"],
                "depends_on": ["validator"],
                "deadline_ms": 60000,
            },
        },
        "defaults": {
            "deadline_ms": 120000,
            "retry_policy": {"max_retries": 1, "backoff": "exponential"},
        },
    }

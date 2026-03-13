"""Fallback/retry layer for A2A Gateway routing."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from binex.gateway.config import AgentEntry, FallbackConfig
from binex.gateway.router import RoutingHints, RoutingRequest, RoutingResult


async def execute_with_fallback(
    agents: list[AgentEntry],
    request: RoutingRequest,
    config: FallbackConfig,
    overrides: RoutingHints | None,
    http_client: httpx.AsyncClient,
) -> RoutingResult:
    """Execute request against candidate agents with retry and failover.

    For each candidate agent, retry up to ``retry_count`` times with backoff.
    On all retries exhausted and failover enabled, try the next candidate.
    On all candidates exhausted, raise ``RuntimeError`` with structured info.

    Per-request *overrides* (from ``RoutingHints``) take precedence over
    *config* defaults for ``retry_count`` and ``failover``.
    """
    # Resolve effective config from overrides
    retry_count = config.retry_count
    if overrides is not None and overrides.retry_count is not None:
        retry_count = overrides.retry_count

    failover = config.failover
    if overrides is not None and overrides.failover is not None:
        failover = overrides.failover

    timeout = 30.0
    if overrides is not None and overrides.timeout_ms is not None:
        timeout = overrides.timeout_ms / 1000.0
    elif request.routing is not None and request.routing.timeout_ms is not None:
        timeout = request.routing.timeout_ms / 1000.0

    # Build the HTTP payload
    http_payload: dict[str, Any] = {
        "task_id": request.task_id,
        "skill": request.skill,
        "trace_id": request.trace_id,
        "artifacts": request.artifacts,
    }

    total_attempts = 0
    attempt_log: list[dict[str, Any]] = []

    for agent in agents:
        agent_errors: list[str] = []

        for attempt in range(retry_count + 1):  # initial + retries
            total_attempts += 1

            # Backoff delay before retry (not before first attempt)
            if attempt > 0:
                delay_s = _compute_delay(config, attempt)
                await asyncio.sleep(delay_s)

            try:
                response = await http_client.post(
                    f"{agent.endpoint}/execute",
                    json=http_payload,
                    timeout=timeout,
                )
                response.raise_for_status()
                data = response.json()

                return RoutingResult(
                    artifacts=data.get("artifacts", []),
                    cost=data.get("cost"),
                    routed_to=agent.name,
                    endpoint=agent.endpoint,
                    attempts=total_attempts,
                )
            except Exception as exc:
                agent_errors.append(f"attempt {attempt + 1}: {exc}")

        # All retries exhausted for this agent
        attempt_log.append({
            "agent": agent.name,
            "endpoint": agent.endpoint,
            "errors": agent_errors,
        })

        if not failover:
            break

    # All candidates exhausted
    details = "; ".join(
        f"{entry['agent']}({len(entry['errors'])} failures)"
        for entry in attempt_log
    )
    raise RuntimeError(
        f"All agents failed for '{request.agent_uri}'. {details}"
    )


def _compute_delay(config: FallbackConfig, attempt: int) -> float:
    """Compute backoff delay in seconds for a given retry attempt.

    *attempt* is 1-based (first retry = 1).
    """
    base_s = config.retry_base_delay_ms / 1000.0
    if config.retry_backoff == "fixed":
        return base_s
    # exponential: base * 2^(attempt - 1)
    return base_s * (2 ** (attempt - 1))

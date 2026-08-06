"""Tests for gateway router, Gateway core class, and integration points."""

from __future__ import annotations

import pytest

from binex.gateway.config import AgentEntry, FallbackConfig, GatewayConfig
from binex.gateway.registry import AgentRegistry
from binex.gateway.router import Router, RoutingHints, RoutingRequest, RoutingResult

# ── RoutingHints model ────────────────────────────────────────────────


class TestRoutingHints:
    def test_defaults(self):
        hints = RoutingHints()
        assert hints.prefer == "highest_priority"
        assert hints.timeout_ms is None
        assert hints.retry_count is None
        assert hints.failover is None

    def test_custom_values(self):
        hints = RoutingHints(
            prefer="lowest_latency",
            timeout_ms=5000,
            retry_count=3,
            failover=False,
        )
        assert hints.prefer == "lowest_latency"
        assert hints.timeout_ms == 5000
        assert hints.retry_count == 3
        assert hints.failover is False


# ── RoutingRequest model ──────────────────────────────────────────────


class TestRoutingRequest:
    def test_minimal(self):
        req = RoutingRequest(
            agent_uri="a2a://summarizer",
            task_id="t1",
            skill="summarize",
            trace_id="tr1",
            artifacts=[],
        )
        assert req.agent_uri == "a2a://summarizer"
        assert req.routing is None

    def test_with_routing_hints(self):
        hints = RoutingHints(timeout_ms=3000)
        req = RoutingRequest(
            agent_uri="a2a://summarizer",
            task_id="t1",
            skill="summarize",
            trace_id="tr1",
            artifacts=[],
            routing=hints,
        )
        assert req.routing.timeout_ms == 3000


# ── RoutingResult model ──────────────────────────────────────────────


class TestRoutingResult:
    def test_construction(self):
        result = RoutingResult(
            artifacts=[{"type": "text", "content": "hello"}],
            cost=0.01,
            routed_to="agent-a",
            endpoint="http://localhost:9000",
            attempts=1,
        )
        assert result.routed_to == "agent-a"
        assert result.attempts == 1
        assert result.cost == 0.01

    def test_defaults(self):
        result = RoutingResult(
            artifacts=[],
            cost=None,
            routed_to="x",
            endpoint="http://x",
            attempts=1,
        )
        assert result.cost is None


# ── Router.resolve() — dual-mode parsing ─────────────────────────────


def _make_config(agents: list[AgentEntry]) -> GatewayConfig:
    return GatewayConfig(agents=agents)


def _make_registry(agents: list[AgentEntry]) -> AgentRegistry:
    return AgentRegistry(_make_config(agents))


class TestRouterExplicitUrl:
    """When the payload after a2a:// contains :// it is an explicit URL."""

    def test_explicit_url_passthrough(self):
        registry = _make_registry([])
        router = Router(registry)
        result = router.resolve("a2a://http://localhost:9000/agent")
        assert result == ["http://localhost:9000/agent"]

    def test_explicit_https_url(self):
        registry = _make_registry([])
        router = Router(registry)
        result = router.resolve("a2a://https://example.com/agent")
        assert result == ["https://example.com/agent"]

    def test_explicit_url_ignores_hints(self):
        registry = _make_registry([])
        router = Router(registry)
        hints = RoutingHints(prefer="lowest_latency")
        result = router.resolve("a2a://http://localhost:9000", hints=hints)
        assert result == ["http://localhost:9000"]


class TestRouterCapabilityLookup:
    """When the payload does NOT contain :// → capability lookup."""

    def test_single_agent_found(self):
        agents = [
            AgentEntry(
                name="agent-a",
                endpoint="http://a:9000",
                capabilities=["summarize"],
                priority=1,
            ),
        ]
        registry = _make_registry(agents)
        router = Router(registry)
        result = router.resolve("a2a://summarize")
        assert result == ["http://a:9000"]

    def test_empty_capability_raises(self):
        registry = _make_registry([])
        router = Router(registry)
        with pytest.raises(ValueError, match="No agents found"):
            router.resolve("a2a://nonexistent")

    def test_multiple_agents_sorted_by_priority(self):
        agents = [
            AgentEntry(
                name="low-prio",
                endpoint="http://low:9000",
                capabilities=["summarize"],
                priority=10,
            ),
            AgentEntry(
                name="high-prio",
                endpoint="http://high:9000",
                capabilities=["summarize"],
                priority=1,
            ),
        ]
        registry = _make_registry(agents)
        router = Router(registry)
        result = router.resolve("a2a://summarize")
        assert result[0] == "http://high:9000"
        assert result[1] == "http://low:9000"

    def test_down_agents_filtered_out(self):
        agents = [
            AgentEntry(
                name="down-agent",
                endpoint="http://down:9000",
                capabilities=["summarize"],
                priority=1,
            ),
            AgentEntry(
                name="alive-agent",
                endpoint="http://alive:9000",
                capabilities=["summarize"],
                priority=5,
            ),
        ]
        registry = _make_registry(agents)
        registry.update_health("down-agent", "down")
        router = Router(registry)
        result = router.resolve("a2a://summarize")
        assert result == ["http://alive:9000"]

    def test_all_agents_down_raises(self):
        agents = [
            AgentEntry(
                name="a",
                endpoint="http://a:9000",
                capabilities=["summarize"],
                priority=1,
            ),
        ]
        registry = _make_registry(agents)
        registry.update_health("a", "down")
        router = Router(registry)
        with pytest.raises(ValueError, match="No agents found"):
            router.resolve("a2a://summarize")

    def test_alive_preferred_over_degraded(self):
        agents = [
            AgentEntry(
                name="degraded",
                endpoint="http://deg:9000",
                capabilities=["summarize"],
                priority=1,
            ),
            AgentEntry(
                name="alive",
                endpoint="http://alive:9000",
                capabilities=["summarize"],
                priority=5,
            ),
        ]
        registry = _make_registry(agents)
        registry.update_health("degraded", "degraded", latency_ms=10)
        router = Router(registry)
        result = router.resolve("a2a://summarize")
        # alive first despite higher priority number
        assert result[0] == "http://alive:9000"
        assert result[1] == "http://deg:9000"

    def test_same_status_sorted_by_priority_then_latency(self):
        agents = [
            AgentEntry(
                name="a",
                endpoint="http://a:9000",
                capabilities=["cap"],
                priority=2,
            ),
            AgentEntry(
                name="b",
                endpoint="http://b:9000",
                capabilities=["cap"],
                priority=2,
            ),
            AgentEntry(
                name="c",
                endpoint="http://c:9000",
                capabilities=["cap"],
                priority=1,
            ),
        ]
        registry = _make_registry(agents)
        registry.update_health("a", "alive", latency_ms=100)
        registry.update_health("b", "alive", latency_ms=50)
        registry.update_health("c", "alive", latency_ms=200)
        router = Router(registry)
        result = router.resolve("a2a://cap")
        # priority 1 first (c), then priority 2 sorted by latency (b < a)
        assert result == [
            "http://c:9000",
            "http://b:9000",
            "http://a:9000",
        ]

    def test_no_prefix_stripped(self):
        """Capability lookup strips the a2a:// prefix correctly."""
        agents = [
            AgentEntry(
                name="x",
                endpoint="http://x:9000",
                capabilities=["my-skill"],
            ),
        ]
        registry = _make_registry(agents)
        router = Router(registry)
        result = router.resolve("a2a://my-skill")
        assert result == ["http://x:9000"]

    def test_raw_uri_without_prefix(self):
        """Router also works when given capability without a2a:// prefix."""
        agents = [
            AgentEntry(
                name="x",
                endpoint="http://x:9000",
                capabilities=["my-skill"],
            ),
        ]
        registry = _make_registry(agents)
        router = Router(registry)
        result = router.resolve("my-skill")
        assert result == ["http://x:9000"]


# ── Gateway core class ───────────────────────────────────────────────


class TestGateway:
    @pytest.mark.asyncio
    async def test_route_explicit_url(self, httpx_mock):
        """Gateway.route() with explicit URL makes direct HTTP call."""
        from binex.gateway import Gateway

        httpx_mock.add_response(
            url="http://localhost:9000/execute",
            json={
                "artifacts": [{"type": "text", "content": "hello"}],
                "cost": 0.05,
            },
        )

        gw = Gateway(config=None)
        req = RoutingRequest(
            agent_uri="a2a://http://localhost:9000",
            task_id="t1",
            skill="summarize",
            trace_id="tr1",
            artifacts=[{"id": "a1", "type": "text", "content": "input"}],
        )
        result = await gw.route(req)
        assert result.routed_to == "http://localhost:9000"
        assert result.endpoint == "http://localhost:9000"
        assert result.attempts == 1
        assert result.cost == 0.05
        assert len(result.artifacts) == 1

    @pytest.mark.asyncio
    async def test_route_capability_lookup(self, httpx_mock):
        """Gateway.route() with capability name resolves via registry."""
        from binex.gateway import Gateway

        config = GatewayConfig(
            agents=[
                AgentEntry(
                    name="sum-agent",
                    endpoint="http://sum:9000",
                    capabilities=["summarize"],
                    priority=1,
                ),
            ]
        )

        httpx_mock.add_response(
            url="http://sum:9000/execute",
            json={"artifacts": [{"type": "text", "content": "done"}]},
        )

        gw = Gateway(config=config)
        req = RoutingRequest(
            agent_uri="a2a://summarize",
            task_id="t2",
            skill="summarize",
            trace_id="tr2",
            artifacts=[],
        )
        result = await gw.route(req)
        assert result.routed_to == "sum-agent"
        assert result.endpoint == "http://sum:9000"

    @pytest.mark.asyncio
    async def test_route_failover(self, httpx_mock):
        """Gateway fails over to next agent on HTTP error."""
        from binex.gateway import Gateway

        config = GatewayConfig(
            agents=[
                AgentEntry(
                    name="primary",
                    endpoint="http://primary:9000",
                    capabilities=["summarize"],
                    priority=1,
                ),
                AgentEntry(
                    name="secondary",
                    endpoint="http://secondary:9000",
                    capabilities=["summarize"],
                    priority=2,
                ),
            ],
            fallback=FallbackConfig(retry_count=0, failover=True),
        )

        httpx_mock.add_response(
            url="http://primary:9000/execute",
            status_code=500,
        )
        httpx_mock.add_response(
            url="http://secondary:9000/execute",
            json={"artifacts": [{"type": "text", "content": "fallback"}]},
        )

        gw = Gateway(config=config)
        req = RoutingRequest(
            agent_uri="a2a://summarize",
            task_id="t3",
            skill="summarize",
            trace_id="tr3",
            artifacts=[],
        )
        result = await gw.route(req)
        assert result.routed_to == "secondary"
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_route_passthrough_no_config(self, httpx_mock):
        """When config is None, gateway acts as pass-through proxy."""
        from binex.gateway import Gateway

        httpx_mock.add_response(
            url="http://direct:9000/execute",
            json={"artifacts": []},
        )

        gw = Gateway(config=None)
        req = RoutingRequest(
            agent_uri="a2a://http://direct:9000",
            task_id="t4",
            skill="x",
            trace_id="tr4",
            artifacts=[],
        )
        result = await gw.route(req)
        assert result.endpoint == "http://direct:9000"

    @pytest.mark.asyncio
    async def test_route_all_fail_raises(self, httpx_mock):
        """Gateway raises when all agents fail."""
        from binex.gateway import Gateway

        config = GatewayConfig(
            agents=[
                AgentEntry(
                    name="only",
                    endpoint="http://only:9000",
                    capabilities=["summarize"],
                    priority=1,
                ),
            ],
            fallback=FallbackConfig(retry_count=0, failover=True),
        )

        httpx_mock.add_response(
            url="http://only:9000/execute",
            status_code=500,
        )

        gw = Gateway(config=config)
        req = RoutingRequest(
            agent_uri="a2a://summarize",
            task_id="t5",
            skill="summarize",
            trace_id="tr5",
            artifacts=[],
        )
        with pytest.raises(RuntimeError, match="All agents failed"):
            await gw.route(req)


# ── create_gateway factory ────────────────────────────────────────────


class TestCreateGateway:
    def test_create_gateway_no_config(self, tmp_path, monkeypatch):
        from binex.gateway import create_gateway

        monkeypatch.chdir(tmp_path)
        gw = create_gateway(config_path=None)
        assert gw._config is None

    def test_create_gateway_with_config(self, tmp_path, monkeypatch):
        from binex.gateway import create_gateway

        config_file = tmp_path / "gateway.yaml"
        config_file.write_text(
            "host: 0.0.0.0\nport: 9999\nagents:\n"
            "  - name: a\n    endpoint: http://a:9000\n"
            "    capabilities: [cap]\n"
        )
        monkeypatch.chdir(tmp_path)
        gw = create_gateway(config_path=str(config_file))
        assert gw._config is not None
        assert gw._config.port == 9999


# ── A2AAgentAdapter gateway integration ──────────────────────────────


class TestA2AAdapterGatewayIntegration:
    def test_adapter_without_gateway(self):
        """Existing behavior preserved when gateway is None."""
        from binex.adapters.a2a import A2AAgentAdapter

        adapter = A2AAgentAdapter(endpoint="http://localhost:9000")
        assert adapter._gateway is None

    def test_adapter_with_gateway(self):
        """Gateway can be injected into adapter."""
        from binex.adapters.a2a import A2AAgentAdapter
        from binex.gateway import Gateway

        gw = Gateway(config=None)
        adapter = A2AAgentAdapter(
            endpoint="http://localhost:9000", gateway=gw
        )
        assert adapter._gateway is gw

    @pytest.mark.asyncio
    async def test_adapter_execute_via_gateway(self, httpx_mock):
        """When gateway is set, execute() routes through gateway."""
        from binex.adapters.a2a import A2AAgentAdapter
        from binex.gateway import Gateway
        from binex.models.task import TaskNode

        httpx_mock.add_response(
            url="http://localhost:9000/execute",
            json={
                "artifacts": [{"type": "result", "content": "gw-routed"}],
                "cost": 0.02,
            },
        )

        gw = Gateway(config=None)
        adapter = A2AAgentAdapter(
            endpoint="http://localhost:9000", gateway=gw
        )
        task = TaskNode(
            id="task-1",
            node_id="node-1",
            run_id="run-1",
            agent="a2a://http://localhost:9000",
        )
        result = await adapter.execute(task, [], "trace-1")
        assert len(result.artifacts) >= 1

    @pytest.mark.asyncio
    async def test_adapter_execute_direct(self, httpx_mock):
        """When gateway is None, execute() makes direct HTTP call."""
        from binex.adapters.a2a import A2AAgentAdapter
        from binex.models.task import TaskNode

        httpx_mock.add_response(
            url="http://localhost:9000/execute",
            json={
                "artifacts": [{"type": "text", "content": "direct"}],
            },
        )

        adapter = A2AAgentAdapter(endpoint="http://localhost:9000")
        task = TaskNode(
            id="task-1",
            node_id="node-1",
            run_id="run-1",
            agent="a2a://http://localhost:9000",
        )
        result = await adapter.execute(task, [], "trace-1")
        assert len(result.artifacts) == 1
        assert result.artifacts[0].content == "direct"


# ── NodeSpec routing field ────────────────────────────────────────────


class TestNodeSpecRouting:
    def test_routing_field_default_none(self):
        from binex.models.workflow import NodeSpec

        node = NodeSpec(agent="llm://gpt-4", outputs=["out"])
        assert node.routing is None

    def test_routing_field_set(self):
        from binex.models.workflow import NodeSpec

        node = NodeSpec(
            agent="a2a://summarize",
            outputs=["out"],
            routing={"prefer": "lowest_latency", "timeout_ms": 5000},
        )
        assert node.routing == {
            "prefer": "lowest_latency",
            "timeout_ms": 5000,
        }


# ── adapter_registry gateway integration ─────────────────────────────


class TestAdapterRegistryGateway:
    def test_a2a_adapter_gets_gateway_when_config_exists(
        self, tmp_path, monkeypatch
    ):
        """When gateway.yaml exists, a2a adapters get a gateway instance."""
        from binex.cli.adapter_registry import register_workflow_adapters
        from binex.models.workflow import NodeSpec, WorkflowSpec
        from binex.runtime.dispatcher import Dispatcher

        # Create gateway.yaml in working directory
        gateway_yaml = tmp_path / "gateway.yaml"
        gateway_yaml.write_text(
            "agents:\n"
            "  - name: sum\n"
            "    endpoint: http://sum:9000\n"
            "    capabilities: [summarize]\n"
        )
        monkeypatch.chdir(tmp_path)

        spec = WorkflowSpec(
            name="test",
            nodes={
                "node1": NodeSpec(
                    agent="a2a://summarize",
                    outputs=["out"],
                ),
            },
        )
        dispatcher = Dispatcher()
        register_workflow_adapters(dispatcher, spec)

        adapter = dispatcher._adapters["a2a://summarize"]
        assert adapter._gateway is not None

    def test_a2a_adapter_no_gateway_when_no_config(
        self, tmp_path, monkeypatch
    ):
        """When no gateway.yaml exists, a2a adapters have no gateway."""
        from binex.cli.adapter_registry import register_workflow_adapters
        from binex.models.workflow import NodeSpec, WorkflowSpec
        from binex.runtime.dispatcher import Dispatcher

        monkeypatch.chdir(tmp_path)

        spec = WorkflowSpec(
            name="test",
            nodes={
                "node1": NodeSpec(
                    agent="a2a://http://localhost:9000",
                    outputs=["out"],
                ),
            },
        )
        dispatcher = Dispatcher()
        register_workflow_adapters(dispatcher, spec)

        adapter = dispatcher._adapters["a2a://http://localhost:9000"]
        assert adapter._gateway is None

    def test_routing_hints_forwarded(self, tmp_path, monkeypatch):
        """NodeSpec.routing is forwarded to the adapter as RoutingHints."""
        from binex.cli.adapter_registry import register_workflow_adapters
        from binex.models.workflow import NodeSpec, WorkflowSpec
        from binex.runtime.dispatcher import Dispatcher

        gateway_yaml = tmp_path / "gateway.yaml"
        gateway_yaml.write_text(
            "agents:\n"
            "  - name: sum\n"
            "    endpoint: http://sum:9000\n"
            "    capabilities: [summarize]\n"
        )
        monkeypatch.chdir(tmp_path)

        spec = WorkflowSpec(
            name="test",
            nodes={
                "node1": NodeSpec(
                    agent="a2a://summarize",
                    outputs=["out"],
                    routing={"prefer": "lowest_latency", "timeout_ms": 3000},
                ),
            },
        )
        dispatcher = Dispatcher()
        register_workflow_adapters(dispatcher, spec)

        adapter = dispatcher._adapters["a2a://summarize"]
        assert adapter._routing_hints is not None
        assert adapter._routing_hints.prefer == "lowest_latency"
        assert adapter._routing_hints.timeout_ms == 3000


# ── Conftest fixture for httpx_mock ───────────────────────────────────


@pytest.fixture
def httpx_mock():
    """Simple httpx mock using pytest-httpx if available, else manual."""
    try:
        # If pytest-httpx is installed, defer to its fixture
        # We implement a lightweight mock instead
        raise ImportError
    except ImportError:
        pass

    from unittest.mock import patch

    class _HttpxMock:
        def __init__(self):
            self._responses: list[dict] = []
            self._call_index = 0

        def add_response(
            self,
            *,
            url: str,
            json: dict | None = None,
            status_code: int = 200,
        ):
            self._responses.append(
                {"url": url, "json": json or {}, "status_code": status_code}
            )

        def _find_response(self, url: str) -> dict | None:
            for i, r in enumerate(self._responses):
                if r["url"] == url:
                    return self._responses.pop(i)
            return None

    class _MockResponse:
        def __init__(self, status_code: int, data: dict):
            self.status_code = status_code
            self._data = data

        def json(self):
            return self._data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx_error(self.status_code)

    import httpx as httpx_mod

    def httpx_error(status_code):
        req = httpx_mod.Request("POST", "http://mock")
        resp = httpx_mod.Response(status_code, request=req)
        return httpx_mod.HTTPStatusError(
            f"HTTP {status_code}",
            request=req,
            response=resp,
        )

    mock = _HttpxMock()

    class _MockAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, *, json=None, timeout=None):
            resp = mock._find_response(url)
            if resp is None:
                raise httpx_mod.ConnectError(f"No mock for {url}")
            return _MockResponse(resp["status_code"], resp["json"])

        async def get(self, url, *, timeout=None):
            resp = mock._find_response(url)
            if resp is None:
                raise httpx_mod.ConnectError(f"No mock for {url}")
            return _MockResponse(resp["status_code"], resp["json"])

    with patch("httpx.AsyncClient", return_value=_MockAsyncClient()):
        yield mock

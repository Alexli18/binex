"""AutoGen objects for Binex example workflows.

Prerequisites:
    pip install binex[autogen] autogen-ext[openai]
    export OPENAI_API_KEY=sk-...

Objects defined here:
    - coding_team: Coder + reviewer team for code generation

Usage in workflow YAML:
    agent: "autogen://myproject.teams.coding_team"
"""

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient

# --- Shared model client ---

_model = OpenAIChatCompletionClient(model="gpt-4o-mini")

# --- Coding Team ---
# Used by: autogen-coding-team.yaml, mixed-framework-pipeline.yaml

_coder = AssistantAgent(
    "coder",
    model_client=_model,
    system_message=(
        "You are a senior Python developer. Write clean, well-documented, "
        "production-ready code. Include type hints and docstrings. "
        "Follow PEP 8 conventions."
    ),
)

_reviewer = AssistantAgent(
    "reviewer",
    model_client=_model,
    system_message=(
        "You are a code reviewer. Review the code for correctness, "
        "edge cases, security issues, and style. Suggest improvements. "
        "When the code is satisfactory, say APPROVE."
    ),
)

coding_team = RoundRobinGroupChat(
    participants=[_coder, _reviewer],
    termination_condition=MaxMessageTermination(max_messages=6),
)

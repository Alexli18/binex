"""CLI `binex scaffold` command — generate template projects."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click


@click.group("scaffold")
def scaffold_group() -> None:
    """Generate template projects for Binex agents and workflows."""


@scaffold_group.command("agent")
@click.option("--name", default="my-agent", help="Agent name")
@click.option("--dir", "directory", default=None, type=click.Path(), help="Target directory")
def scaffold_agent(name: str, directory: str | None) -> None:
    """Scaffold a new A2A agent project."""
    target = Path(directory) if directory else Path.cwd() / name

    # Fail if directory exists and is not empty
    if target.exists() and any(target.iterdir()):
        click.echo(f"Error: directory '{target}' already exists and is not empty.")
        sys.exit(1)

    try:
        target.mkdir(parents=True, exist_ok=True)

        # 1. __init__.py — empty
        (target / "__init__.py").write_text("")

        # 2. agent.py — basic handler
        (target / "agent.py").write_text(_agent_py(name))

        # 3. agent_card.json — A2A agent card
        (target / "agent_card.json").write_text(_agent_card_json(name))

        # 4. server.py — FastAPI server
        (target / "server.py").write_text(_server_py(name))

        # 5. requirements.txt
        (target / "requirements.txt").write_text(_requirements_txt())

        click.echo(f"Agent '{name}' scaffolded at {target}")

    except OSError as exc:
        click.echo(f"Error: {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Template generators
# ---------------------------------------------------------------------------

def _agent_py(name: str) -> str:
    return f'''"""Agent handler for {name}."""

from __future__ import annotations

from typing import Any


class {_class_name(name)}:
    """A simple echo agent that returns whatever it receives."""

    name = "{name}"

    async def handle(self, message: dict[str, Any]) -> dict[str, Any]:
        """Process an incoming message and return a response."""
        return {{
            "agent": self.name,
            "echo": message,
        }}
'''


def _agent_card_json(name: str) -> str:
    card = {
        "name": name,
        "description": f"A2A agent: {name}",
        "url": "http://localhost:8000",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "skills": [
            {
                "id": "echo",
                "name": "Echo",
                "description": "Echoes back the received message.",
            }
        ],
    }
    return json.dumps(card, indent=2) + "\n"


def _server_py(name: str) -> str:
    return f'''"""Server entry point for {name}."""

from __future__ import annotations

import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from agent import {_class_name(name)}

app = FastAPI(title="{name}")
agent = {_class_name(name)}()

# Serve agent card at /.well-known/agent.json
_card_path = Path(__file__).parent / "agent_card.json"
_agent_card = json.loads(_card_path.read_text())


@app.get("/.well-known/agent.json")
async def agent_card():
    """Return the A2A agent card."""
    return _agent_card


@app.post("/")
async def handle_message(message: dict):
    """Handle an incoming A2A message."""
    return await agent.handle(message)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''


def _requirements_txt() -> str:
    return "a2a-sdk\nfastapi\nuvicorn\n"


def _class_name(name: str) -> str:
    """Convert a kebab-case name to PascalCase class name."""
    return "".join(part.capitalize() for part in name.replace("_", "-").split("-")) + "Agent"

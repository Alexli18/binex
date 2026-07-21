"""CLI `binex observe-demo` — verify observer mode without a real CrewAI run (#73).

Simulates a small multi-agent flow whose "agents" make LiteLLM calls with
``mock_response`` — no API key, no network, fully deterministic — inside an
``observe()`` block. Because ``mock_response`` still fires LiteLLM's callbacks
(with usage and cost), this exercises the *real* observer capture path and
produces an ``observed`` run you can inspect exactly like a captured Crew run.
"""

from __future__ import annotations

import click

# A tiny "crew": (agent label, model, prompt, canned answer).
_DEMO_STEPS = [
    ("planner", "gpt-4o",
     "Break 'write a launch blog post' into steps.",
     "1. Research the audience\n2. Draft an outline\n3. Write the post"),
    ("researcher", "gpt-4o-mini",
     "Research the target audience for a dev-tools launch.",
     "Audience: senior backend engineers frustrated by opaque agent costs."),
    ("writer", "gpt-4o",
     "Write the intro paragraph from the research.",
     "Every team shipping AI agents eventually asks the same question: "
     "where did the money go?"),
    ("editor", "gpt-4o-mini",
     "Tighten the intro to one sentence.",
     "Every team shipping AI agents eventually asks: where did the money go?"),
]


@click.command("observe-demo", epilog="""\b
Examples:
  binex observe-demo                 Generate a demo observed run
  binex observe-demo --name my-demo  Name it
""")
@click.option("--name", default="observe-demo", show_default=True,
              help="Name for the generated observed run")
def observe_demo_cmd(name: str) -> None:
    """Generate a demo observed run to verify observer mode (offline, no API key)."""
    import litellm

    from binex.observer import observe

    click.echo(
        f"Simulating a {len(_DEMO_STEPS)}-agent flow under observe('{name}') "
        "using LiteLLM mock responses (no API calls)...",
    )
    with observe(name) as cap:
        for label, model, prompt, answer in _DEMO_STEPS:
            litellm.completion(
                model=model,
                messages=[
                    {"role": "system", "content": f"You are the {label} agent."},
                    {"role": "user", "content": prompt},
                ],
                mock_response=answer,
            )

    run_id = cap.run_id
    if run_id is None:
        click.echo(
            "Observer captured no calls — did LiteLLM callbacks fail to install? "
            "Check the log warnings above.",
            err=True,
        )
        raise SystemExit(1)

    total = sum(c.cost or 0.0 for c in cap.calls)
    click.echo(
        f"\nCaptured {len(cap.calls)} LLM call(s) into observed run '{run_id}' "
        f"(≈${total:.4f})."
    )
    click.echo("\nInspect it:")
    click.echo(f"  binex debug {run_id}")
    click.echo(f"  binex cost show {run_id}")
    click.echo("  binex ui        # then open the run (marked 'observed')")

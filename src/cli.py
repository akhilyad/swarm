"""CLI entry point for the Hyrex platform.

Usage:
    swarm run --config config.yaml --goal "Your goal here"
    swarm status
    swarm agents --config config.yaml
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click

from .core.config import load_config
from .runtime.orchestrator import Orchestrator


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def cli(verbose: bool) -> None:
    """Hyrex - hierarchical AI agent workforce."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )


@cli.command()
@click.option("--config", "-c", required=True, type=click.Path(exists=True), help="Path to swarm YAML config")
@click.option("--goal", "-g", required=True, help="Goal description for the CEO agent")
@click.option("--timeout", "-t", default=120, type=int, help="Timeout in seconds")
@click.option("--llm/--no-llm", default=False, help="Enable LLM calls (requires LLM_API_KEY)")
def run(config: str, goal: str, timeout: int, llm: bool) -> None:
    """Run a goal through the swarm hierarchy."""
    async def _run() -> None:
        cfg = load_config(Path(config))
        orchestrator = Orchestrator(config=cfg, llm_func=_make_llm_func() if llm else None)
        result = await orchestrator.run_goal(goal, timeout=timeout)
        click.echo("\n=== FINAL RESULT ===")
        click.echo(result)
        click.echo(f"\n--- Elapsed: {orchestrator.elapsed:.1f}s ---")

    asyncio.run(_run())


@cli.command()
@click.option("--config", "-c", required=True, type=click.Path(exists=True), help="Path to swarm YAML config")
def agents(config: str) -> None:
    """List all agents in the swarm configuration."""
    cfg = load_config(Path(config))
    click.echo(f"Swarm: {cfg.name}")
    click.echo(f"Model: {cfg.model}")
    if cfg.budget_usd:
        click.echo(f"Budget: ${cfg.budget_usd:.2f}")
    click.echo("")
    click.echo(f"{'ID':<20} {'Name':<20} {'Role':<10} {'Children':<10}")
    click.echo("-" * 60)
    for node_id, node in cfg.agents.items():
        children = ", ".join(node.child_ids) if node.child_ids else "-"
        click.echo(f"{node_id:<20} {node.name:<20} {node.role.value:<10} {children:<10}")


@cli.command()
@click.option("--config", "-c", required=True, type=click.Path(exists=True), help="Path to swarm YAML config")
@click.option("--goal", "-g", required=True, help="Goal description")
def simulate(config: str, goal: str) -> None:
    """Run a simulated (no-LLM) goal for testing the hierarchy flow."""
    async def _run() -> None:
        cfg = load_config(Path(config))
        orchestrator = Orchestrator(config=cfg)
        click.echo(f"Running simulated goal on '{cfg.name}'...")
        click.echo(orchestrator.status_summary)
        result = await orchestrator.run_goal(goal, timeout=30)
        click.echo("\n=== RESULT ===")
        click.echo(result)
        click.echo("\n=== STATUS ===")
        click.echo(orchestrator.status_summary)

    asyncio.run(_run())


def _make_llm_func():
    """Lazy import LLM client to avoid dependency on startup."""
    try:
        from .llm.client import LLMClient

        client = LLMClient()

        async def llm_func(prompt: str, context: dict | None = None) -> str:
            return await client.generate(prompt, context or {})

        return llm_func
    except Exception as e:
        click.echo(f"Warning: Could not initialize LLM client: {e}", err=True)
        return None


if __name__ == "__main__":
    cli()

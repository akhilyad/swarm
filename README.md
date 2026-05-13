
<p align="center">
  <img src="https://img.shields.io/badge/status-alpha-brightgreen?style=flat-square" alt="Status: Alpha">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-MIT-purple?style=flat-square" alt="MIT License">
  <img src="https://img.shields.io/badge/PRs-welcome-orange?style=flat-square" alt="PRs Welcome">
</p>

<h1 align="center">
  🐝 Swarm of Swarms
</h1>

<p align="center">
  <em>Because one AI is a party trick, but a whole company of them is a business plan.</em>
</p>

<p align="center">
  <b>Hierarchical AI Agent Workforce Platform</b> — <i>CEO delegates to Managers who delegate to Workers,<br>
  each department is itself a self-similar swarm. It's turtles all the way down.</i>
</p>

---

## What Is This Madness?

**Swarm of Swarms** is an open-source framework for running **hierarchical AI agent swarms** modeled after a real company. You give a CEO agent a high-level goal, and it:

1. **Decomposes** the goal into strategic initiatives
2. **Delegates** them to department managers
3. Who **decompose again** and delegate to workers
4. Who **execute** by calling LLMs, tools, and memory
5. **Results flow back up**, with each level synthesizing before reporting

The result? A literal AI company that works on your problems while you sleep. No HR department required.

### The Vibe

```
                    CEO (strategic planner)
                   /          |            \
          Dept Manager    Dept Manager    Dept Manager
         /    |    \      /    |   \      /    |    \
       Wkr  Wkr  Wkr    Wkr  Wkr  Wkr    Wkr  Wkr  Wkr

  ─── Each manager IS ALSO a swarm ───
  ─── Departments can grow into sub-companies ───
  ─── Workers are leaf nodes with tool access ───
  ─── Your computer becomes a beehive of AI productivity ───
```

## Why Though?

| Problem | Solution |
|---------|----------|
| Single LLM calls are dumb | Hierarchical decomposition produces smarter results |
| Flat agent swarms are chaotic | Tree structure = clear chain of command |
| Agents need to communicate | Async message bus keeps everyone in the loop |
| LLM costs spiral out of control | Budget tracking per run, per agent |
| "It works on my machine" | Fully async, designed for distribution from day one |

## Architecture (The Nerdy Bits)

```
┌──────────────────────────────────────────────┐
│              CLI / Dashboard                   │
├──────────────────────────────────────────────┤
│        Runtime Orchestrator (asyncio)         │
├─────────────┬──────────────────┬──────────────┤
│  Agent Loop │  Message Bus     │  Swarm Tree  │
│  (per node) │  (pub/sub)       │  (registry)  │
├─────────────┴──────────────────┴──────────────┤
│              Memory Layer (Chroma)             │
├──────────────────────────────────────────────┤
│              LLM Layer (LiteLLM)              │
└──────────────────────────────────────────────┘
```

### Key Concepts

- **Holarchy** — Each manager IS a swarm. A department manager can spin up a sub-company by loading a sub-swarm config. Recursion all the way down.
- **Message Bus** — Agents never call each other directly. They publish messages, other agents consume them. This means agents can live on different machines, different processes, or different continents.
- **Self-Similar** — The same pattern works at every scale. 3 agents or 3000, the architecture stays the same.

## Quick Start

### Installation

```bash
# Clone the repo
git clone https://github.com/akhilyad/swarm.git
cd swarm

# Install dependencies (Python 3.11+ required)
pip install -e .
```

### Run a Simulation (No LLM Required)

```bash
# See the hierarchy in action with simulated agents
swarm simulate --config configs/examples/software-dev.yaml --goal "Design a task management API"

# Output:
# 🐝 CEO decomposes the goal...
#   👔 PM-Dept assigns sub-tasks...
#     🔧 Researcher executes...
#     ✍️ Writer executes...
#   👔 Engineering assigns sub-tasks...
#     🔧 Developer executes...
#     🔧 QA-Engineer executes...
#   👔 Design assigns sub-tasks...
#     🎨 Designer executes...
# 📋 Results flow back up...
# ✅ Mission complete!
```

### Run with Real LLMs

```bash
# Set your API key
export OPENAI_API_KEY="sk-..."
# Or ANTHROPIC_API_KEY="sk-ant-..."

# Let the swarm loose
swarm run --config configs/examples/software-dev.yaml --goal "Design a task management API"
```

### Or Just Poke Around

```bash
# List all agents in the company
swarm agents --config configs/examples/software-dev.yaml

# Output:
# 🐝 CEO (CEO) ── Top-level strategist
#   ├── 👔 PM-Dept (MANAGER) ── Project management department
#   │   ├── 🔧 Researcher (WORKER)
#   │   └── ✍️ Writer (WORKER)
#   ├── 👔 Engineering (MANAGER) ── Engineering department
#   │   ├── 🔧 Developer (WORKER)
#   │   └── 🔧 QA-Engineer (WORKER)
#   └── 👔 Design (MANAGER) ── Design department
#       └── 🎨 Designer (WORKER)
```

## Configuration

Define your company in YAML:

```yaml
name: "Software Dev Agency"
model: "gpt-4o"
budget_usd: 50.0

agents:
  ceo:
    name: "CEO"
    role: CEO
    children: [pm, lead-eng, lead-design]

  pm:
    name: "PM-Dept"
    role: MANAGER
    parent: ceo
    children: [worker-1, worker-2]

  worker-1:
    name: "Researcher"
    role: WORKER
    parent: pm

  worker-2:
    name: "Writer"
    role: WORKER
    parent: pm
  # ... etc
```

Drop in more example configs in `configs/examples/` or roll your own. Make a marketing agency, a research lab, a legal firm, a squad of AI chaos gremlins — the world is your oyster.

## Project Structure

```
swarm-of-swarms/
├── pyproject.toml           # Dependencies & project metadata
├── configs/examples/        # YAML company configs
│   ├── software-dev.yaml    # 9-agent dev agency
│   ├── research.yaml        # 6-agent research firm
│   └── general.yaml         # 7-agent general company
├── src/
│   ├── cli.py               # Swarm CLI (click-based)
│   ├── core/
│   │   ├── types.py         # Data models (SwarmNode, Goal, Role)
│   │   ├── config.py        # YAML config loader
│   │   ├── node.py          # NodeHandle runtime wrapper
│   │   └── errors.py        # Custom exceptions
│   ├── swarm/
│   │   ├── factory.py       # Build swarm from config
│   │   └── registry.py      # Tree navigation & lookup
│   ├── runtime/
│   │   ├── orchestrator.py  # Top-level coordinator
│   │   └── agent_loop.py    # Per-agent async event loop
│   ├── communication/
│   │   ├── bus.py           # Async pub/sub message bus
│   │   ├── message.py       # Message types & factories
│   │   └── protocol.py      # Fan-out, request/response
│   ├── memory/
│   │   ├── store.py         # Abstract memory interface
│   │   └── chroma_store.py  # ChromaDB implementation
│   └── llm/
│       └── client.py        # LiteLLM wrapper w/ cost tracking
└── tests/
    ├── test_types.py
    ├── test_config.py
    ├── test_registry.py
    ├── test_node.py
    ├── test_bus.py
    └── test_agent_loop.py
```

## Testing

```bash
# Run all 60 tests (they all pass, obviously)
pytest -v

# With coverage
pytest --cov=src --cov-report=term-missing
```

## Roadmap (Post-MVP)

- [ ] **Web Dashboard** — Real-time swarm visualization because watching AI agents work is hypnotic
- [ ] **Tool Plugins** — Web search, file system, API access for your worker agents
- [ ] **Distributed Agents** — Spread your swarm across machines like a IT crowd episode
- [ ] **Persistent Memory** — Agents that remember what they did last session (like real employees!)
- [ ] **Human-in-the-Loop** — Approval gates so your AI company doesn't go full Skynet
- [ ] **Template Marketplace** — Buy and sell company configs. "One AI Marketing Agency, please."

## Contributing

PRs are welcome! If you can dream up a weirder, more efficient, or more dramatic way to organize AI agents, this is the place.

1. Fork it
2. Create your feature branch (`git checkout -b feature/absurd-idea`)
3. Commit your changes (`git commit -m 'Add some absurdity'`)
4. Push to the branch (`git push origin feature/absurd-idea`)
5. Open a PR and convince us it's genius

## License

MIT — Go forth and build your AI empire. Just don't blame us when your swarm unionizes.

---

<p align="center">
  <sub>Built with 🍕 and existential dread by <a href="https://github.com/akhilyad">@akhilyad</a></sub>
</p>
<p align="center">
  <sub><em>In a world of AGI hype, be a swarm.</em></sub>
</p>

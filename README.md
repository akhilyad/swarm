
<p align="center">
  <img src="https://img.shields.io/badge/status-alpha-brightgreen?style=flat-square" alt="Status: Alpha">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-MIT-purple?style=flat-square" alt="MIT License">
  <img src="https://img.shields.io/badge/PRs-welcome-orange?style=flat-square" alt="PRs Welcome">
</p>

<h1 align="center">
  Swarm of Swarms
</h1>

<p align="center">
  <em>One AI is a party trick. A whole company of them? That's a business plan.</em>
</p>

<p align="center">
  <b>Hierarchical AI Agent Workforce Platform</b> — <i>a CEO agent plans, managers delegate, employees execute.<br>
  Every department is itself a swarm. It's agents all the way down.</i>
</p>

---

## What is this?

**Swarm of Swarms** is an open-source framework that runs a **company of AI agents** inside your terminal.

You give a goal to the CEO agent, and it:

1. **Plans** — breaks your goal into strategic pieces
2. **Delegates** — assigns work to department managers
3. **Sub-delegates** — managers break work down further and hand it to employees
4. **Executes** — employees call LLMs, run tools, and query memory
5. **Reports back** — results flow up the chain, each level summarizing before passing along

The result: a literal AI company working on your problems. No office, no HR, no ping-pong table.

### The Structure

```
                    CEO (strategic planner)
                   /          |            \
          Dept Manager    Dept Manager    Dept Manager
         /    |    \      /    |   \      /    |    \
    Employee Employee  Employee Employee  Employee Employee

  Each manager IS ALSO a swarm
  Departments can grow into sub-companies
  Employees are workers with tool access
  Your computer becomes a beehive of AI productivity
```

## Why?

| Problem | Solution |
|---------|----------|
| One LLM call isn't very smart | Hierarchical planning produces much better results |
| Flat swarms of agents are chaotic | Tree structure = clear chain of command |
| Agents need to communicate without chaos | Async message bus keeps everyone in sync |
| LLM costs can explode | Built-in budget tracking per run, per agent |
| "Works on my machine" | Fully async, designed for distributed systems from day one |

## How It Works (The Short Version)

```
┌──────────────────────────────────────────────┐
│              CLI / Dashboard                   │
├──────────────────────────────────────────────┤
│        Runtime Orchestrator (asyncio)         │
├─────────────┬──────────────────┬──────────────┤
│  Agent Loop │  Message Bus     │  Swarm Tree  │
│  (per node) │  (pub/sub)       │  (registry)  │
├─────────────┴──────────────────┴──────────────┤
│              Memory Layer (ChromaDB)          │
├──────────────────────────────────────────────┤
│              LLM Layer (LiteLLM)              │
└──────────────────────────────────────────────┘
```

**The key ideas:**

- **Holarchy** — Every manager IS a swarm. A department manager can spin up an entire sub-company by loading a sub-swarm config. Recursion all the way down.
- **Message Bus** — Agents never call each other directly. They publish messages, others consume them. This means agents can live on different machines, different processes, or different continents.
- **Self-Similar** — Same pattern works at every scale. 3 agents or 3000, the architecture doesn't change.

## Quick Start

### Install

```bash
git clone https://github.com/akhilyad/swarm.git
cd swarm
pip install -e .
```

### Simulate (No API Key Needed)

```bash
swarm simulate --config configs/examples/software-dev.yaml --goal "Design a task management API"
```

You'll see the CEO decompose the goal, managers delegate sub-tasks, and employees execute. All simulated — zero LLM cost.

### Run With Real AI

```bash
export OPENAI_API_KEY="sk-..."
swarm run --config configs/examples/software-dev.yaml --goal "Design a task management API"
```

### Explore the Company

```bash
swarm agents --config configs/examples/software-dev.yaml
# Shows: CEO → Managers → Employees with roles and hierarchy
```

## Example Config

Define your AI company in YAML:

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
    children: [researcher, writer]

  researcher:
    name: "Researcher"
    role: WORKER
    parent: pm
```

Drop in more configs or build your own — marketing agency, research lab, legal firm, or a squad of AI chaos gremlins. Your call.

## Project Structure

```
swarm-of-swarms/
├── pyproject.toml           # Dependencies & project metadata
├── configs/examples/        # YAML company configs
│   ├── software-dev.yaml    # 9-agent dev agency
│   ├── research.yaml        # 6-agent research firm
│   └── general.yaml         # 7-agent general company
├── src/
│   ├── cli.py               # CLI (click-based)
│   ├── core/
│   │   ├── types.py         # Data models
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
# 60 tests, all passing
pytest -v

# With coverage
pytest --cov=src --cov-report=term-missing
```

## Roadmap

- [ ] **Web Dashboard** — Watch your AI agents work in real time. It's hypnotic.
- [ ] **Tool Plugins** — Give employees web search, file access, API calling powers
- [ ] **Distributed Agents** — Spread your swarm across machines
- [ ] **Persistent Memory** — Agents that remember what they did last session
- [ ] **Human-in-the-Loop** — Approval gates so your AI company doesn't go rogue
- [ ] **Template Marketplace** — Buy and sell company configs. "One AI Marketing Agency, please."

## Contributing

PRs welcome. If you can dream up a weirder, more efficient, or more dramatic way to organize AI agents, this is the place.

1. Fork it
2. Branch it (`git checkout -b feature/your-idea`)
3. Commit it (`git commit -m 'Add your idea'`)
4. Push it (`git push origin feature/your-idea`)
5. Open a PR

## License

MIT — Go build your AI empire. Don't blame us when your swarm unionizes.

---

<p align="center">
  <sub>Built with pizza and existential dread by <a href="https://github.com/akhilyad">@akhilyad</a></sub>
</p>
<p align="center">
  <sub><em>In a world of AGI hype, be a swarm.</em></sub>
</p>

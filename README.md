<div align="center">

# Hyrex

### Hierarchical AI Agent Workforce Platform

<br>

[![Status: Alpha](https://img.shields.io/badge/status-alpha-ff6b35?style=flat-square&labelColor=0a0a0a)](https://github.com/akhilyad/swarm)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square&labelColor=0a0a0a)](https://python.org)
[![License MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square&labelColor=0a0a0a)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-orange?style=flat-square&labelColor=0a0a0a)](https://github.com/akhilyad/swarm/pulls)
[![Tests](https://img.shields.io/badge/tests-102%20passing-brightgreen?style=flat-square&labelColor=0a0a0a)](https://github.com/akhilyad/swarm)
[![Tools](https://img.shields.io/badge/tools-5%20built--in-purple?style=flat-square&labelColor=0a0a0a)](#tool-plugin-system)

<br>

*One AI is a party trick. A whole company of them? That's a business plan.*

**CEO agent plans. Managers delegate. Employees execute. Every department is itself a swarm.**
*It's agents all the way down.*

</div>

---

## What Is This?

**Hyrex** is an open-source framework that runs a **company of AI agents** inside your terminal.

You give a goal to the CEO agent, and a full agent hierarchy gets to work:

| Step | What Happens |
|------|-------------|
| **Plans** | CEO breaks your goal into strategic pieces |
| **Delegates** | Assigns work to department managers |
| **Sub-delegates** | Managers decompose further, hand off to employees |
| **Executes** | Employees call LLMs, run tools, query memory |
| **Reports back** | Results flow up — each level summarizes before passing along |

No office. No HR. No ping-pong table. Just a beehive of AI productivity working on your problems.

> **Real talk:** This is an alpha. The skeleton works, 102 tests pass, the tool plugin system is live, and you can run 9-agent companies with real LLMs today. Web dashboard, persistent memory, and distributed mode are in progress. Jump in, break things, and [tell us what you want next](https://github.com/akhilyad/swarm/issues).

---

## The Structure

```
                    CEO (strategic planner)
                   /          |            \
          Dept Manager    Dept Manager    Dept Manager
         /    |    \      /    |   \      /    |    \
    Employee Employee  Employee Employee  Employee Employee
    (tools)  (tools)   (tools)  (tools)  (tools)  (tools)
```

| Concept | Why It Matters |
|---------|---------------|
| **Holarchy** | Every manager IS a swarm. A department can spin up an entire sub-company by loading a sub-swarm config. Recursion all the way down. |
| **Message Bus** | Agents never call each other directly. They publish, others consume. Agents can live on different machines, processes, or continents. |
| **Self-Similar** | Same pattern at every scale. 3 agents or 3,000 — the architecture doesn't change. |

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/akhilyad/swarm.git
cd swarm
pip install -e .

# 2. Simulate (no API key needed)
swarm simulate --config configs/examples/software-dev.yaml \
  --goal "Design a task management API"

# 3. Run with real AI
export OPENAI_API_KEY="sk-..."
swarm run --config configs/examples/software-dev.yaml \
  --goal "Design a task management API"

# 4. Explore the company structure
swarm agents --config configs/examples/software-dev.yaml
```

The simulate command runs the full hierarchy at zero LLM cost — useful for testing your config before spending API budget.

---

## Tool Plugin System

Agents are useful. Agents with tools are unstoppable. Every worker agent runs a tool loop: the LLM decides what to call, the runtime executes it, the result feeds back into the next decision.

### Built-in Tools

| Tool | What It Does | Example |
|------|-------------|---------|
| **Read File** | Read files from the filesystem | `read_file(file_path="data.txt")` |
| **Write File** | Write content to files | `write_file(file_path="out.txt", content="hello")` |
| **Bash** | Run shell commands | `bash(command="ls -la")` |
| **Web Fetch** | Fetch URLs | `web_fetch(url="https://example.com")` |
| **Python Exec** | Execute Python code | `python_exec(code="print(2+2)")` |

### How the Loop Works

```
LLM decides → emits TOOL_CALL → runtime parses → executes tool
     ↑                                                  │
     └──────────── result fed back ────────────────────┘
     └────── repeats until LLM gives final answer ────→ DONE
```

### Adding Your Own Tool

A 30-second job:

```python
from src.tools.base import BaseTool, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"
    parameters = {
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "The input"},
        },
        "required": ["input"],
    }

    async def execute(self, **kwargs: str) -> ToolResult:
        data = kwargs.get("input", "")
        return ToolResult(success=True, output="done")
```

**Security:** File tools block path traversal. Bash and Python run in isolated subprocesses with timeouts. Web fetch restricts to http/https only.

---

## Example Config

Define your AI company in YAML. Drop in a config, point it at a goal, watch it work.

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

  lead-eng:
    name: "Engineering"
    role: MANAGER
    parent: ceo
    children: [developer]

  researcher:
    name: "Researcher"
    role: WORKER
    parent: pm

  developer:
    name: "Developer"
    role: WORKER
    parent: lead-eng
```

Three configs are included out of the box: a 9-agent dev agency, a 6-agent research firm, and a 7-agent general company. Build your own — marketing agency, legal firm, research lab, chaos gremlins. Your call.

---

## Why Hyrex?

| Problem | Solution |
|---------|----------|
| One LLM call isn't very smart | Hierarchical planning produces much better results |
| Flat swarms of agents are chaotic | Tree structure = clear chain of command |
| Agents need to communicate without chaos | Async message bus keeps everyone in sync |
| LLM costs can explode | Built-in budget tracking per run, per agent |
| Agents need real-world capabilities | Tool plugin system — files, shell, web, code execution |
| "Works on my machine" | Fully async, designed for distributed from day one |

---

## Project Structure

```
hyrex/
├── pyproject.toml
├── configs/examples/
│   ├── software-dev.yaml        # 9-agent dev agency
│   ├── research.yaml            # 6-agent research firm
│   └── general.yaml             # 7-agent general company
├── src/
│   ├── cli.py                   # CLI entry point (click)
│   ├── core/
│   │   ├── types.py
│   │   ├── config.py
│   │   ├── node.py
│   │   └── errors.py
│   ├── swarm/
│   │   ├── factory.py
│   │   └── registry.py
│   ├── runtime/
│   │   ├── orchestrator.py
│   │   └── agent_loop.py
│   ├── communication/
│   │   ├── bus.py
│   │   ├── message.py
│   │   └── protocol.py
│   ├── tools/
│   │   ├── base.py              # BaseTool, ToolResult, ToolRegistry
│   │   └── builtin/
│   │       ├── read_file.py
│   │       ├── write_file.py
│   │       ├── bash.py
│   │       ├── web_fetch.py
│   │       └── python_exec.py
│   ├── memory/
│   │   ├── store.py
│   │   └── chroma_store.py
│   └── llm/
│       └── client.py            # LiteLLM wrapper with cost tracking
└── tests/                       # 102 tests, all passing
```

---

## Testing

```bash
# Run all tests
pytest -v

# With coverage
pytest --cov=src --cov-report=term-missing
```

| Test Suite | Tests | Covers |
|-----------|-------|--------|
| `test_tools_base.py` | 11 | BaseTool, ToolResult, ToolRegistry lifecycle |
| `test_tools_builtin.py` | 24 | Each built-in tool, isolated |
| `test_agent_loop_tools.py` | 7 | Tool parsing, iteration limits, backward compat |
| Core suites | 60 | Types, config, registry, node, bus, agent loop |

---

## Roadmap

- [x] Tool plugin system — 5 built-in tools, 42 tests
- [x] 102 tests passing
- [ ] Web dashboard — watch your agents work in real time
- [ ] Distributed agents — spread your swarm across machines
- [ ] Persistent memory — agents that remember previous sessions
- [ ] Human-in-the-loop — approval gates before irreversible actions
- [ ] Template marketplace — shareable company configs

---

## Disclaimer

Hyrex is a local, open-source tool — not a hosted service. A few things to know:

1. **Your data stays local.** Nothing is sent anywhere except to the LLM provider you configure (OpenAI, Anthropic, etc.). We don't collect or store anything.
2. **Agents run real tools.** Bash and Python execution happen in subprocesses on your machine. Review your config before pointing this at production systems.
3. **Budget limits are advisory.** The built-in cost tracking helps, but LLM pricing changes. Set conservative budgets while testing.
4. **No guarantees.** This is alpha software. Agents can behave unexpectedly. The authors are not liable for data loss, unexpected costs, or other consequences of use.

---

## Contributing

PRs welcome. If you can dream up a weirder, more efficient, or more dramatic way to organize AI agents, this is the place.

```bash
git checkout -b feature/your-idea
git commit -m 'add your idea'
git push origin feature/your-idea
# open a PR
```

---

## License

MIT — go build your AI empire. Don't blame us when your swarm unionizes.

---

<div align="center">

*Built with pizza and existential dread by [@akhilyad](https://github.com/akhilyad)*

*In a world of AGI hype, be Hyrex.*

</div>

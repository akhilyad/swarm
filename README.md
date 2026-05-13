<div align="center">

# ⚡ HYREX ⚡

### *Hierarchical AI Agent Workforce Platform*

<br>

```
██╗  ██╗██╗   ██╗██████╗ ███████╗██╗  ██╗
██║  ██║╚██╗ ██╔╝██╔══██╗██╔════╝╚██╗██╔╝
███████║ ╚████╔╝ ██████╔╝█████╗   ╚███╔╝
██╔══██║  ╚██╔╝  ██╔══██╗██╔══╝   ██╔██╗
██║  ██║   ██║   ██║  ██║███████╗██╔╝ ██╗
╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
```

_One AI is a party trick. A whole company of them? That's a business plan._

[![Status: Alpha](https://img.shields.io/badge/status-alpha-ff00ff?style=flat-square&labelColor=0a0a0a)](https://github.com/akhilyad/swarm)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-00ffff?style=flat-square&labelColor=0a0a0a)](https://python.org)
[![License MIT](https://img.shields.io/badge/license-MIT-00ff88?style=flat-square&labelColor=0a0a0a)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-ffaa00?style=flat-square&labelColor=0a0a0a)](https://github.com/akhilyad/swarm/pulls)
[![Tests](https://img.shields.io/badge/tests-102%20✓-00ff88?style=flat-square&labelColor=0a0a0a)](https://github.com/akhilyad/swarm)
[![Tools](https://img.shields.io/badge/tools-5%20built--in-ff00ff?style=flat-square&labelColor=0a0a0a)](#-tool-plugin-system)

---

**CEO agent plans. Managers delegate. Employees execute. Every department is itself a swarm.**  
_It's agents all the way down._

</div>

---

## 🔥 What is This?

**Hyrex** is an open-source framework that runs a **company of AI agents** inside your terminal. No office, no HR, no ping-pong table. Just a beehive of AI productivity working on your problems.

You give a goal to the **CEO agent**, and the company gets to work:

| Step | What Happens |
|------|-------------|
| 🧠 **Plans** | CEO breaks your goal into strategic pieces |
| 📤 **Delegates** | Assigns work to department managers |
| 🔄 **Sub-delegates** | Managers break work down further, hand it to employees |
| 🛠️ **Executes** | Employees call LLMs, **run tools**, query memory |
| 📡 **Reports Back** | Results flow up — each level summarizes before passing along |

> **⚠️ Real talk:** This is an **alpha** — the skeleton works, 102 tests pass, the tool plugin system is live, and you can run 9-agent companies in your terminal with real LLMs. The dashboard, persistent memory, and distributed mode are in progress. Jump in, break things, and [tell us what you want next](https://github.com/akhilyad/swarm/issues).

---

## 🏛️ The Structure

```
                         ╔═══════════════════╗
                         ║   CEO (Strategist) ║
                         ║  breaks goals down ║
                         ╚════╤════╤════╤════╝
                              │    │    │
              ┌───────────────┘    │    └───────────────┐
              │                    │                    │
     ╔════════╧════════╗  ╔═══════╧════════╗  ╔════════╧════════╗
     ║  Dept Manager   ║  ║  Dept Manager  ║  ║  Dept Manager   ║
     ║ decomposes again║  ║ decomposes     ║  ║ decomposes      ║
     ╚═══╤═══╤═══╤════╝  ╚═══╤═══╤═══╤═══╝  ╚═══╤═══╤═══╤════╝
         │   │   │           │   │   │           │   │   │
    ┌────┘   │   └────┐ ┌───┘   │   └───┐ ┌───┘   │   └────┐
    ▼        ▼        ▼ ▼       ▼       ▼ ▼       ▼        ▼
  🛠️  Wkr  🛠️  Wkr  🛠️  Wkr  🛠️  Wkr  🛠️  Wkr  🛠️  Wkr  🛠️  Wkr  🛠️  Wkr
  (tools)  (tools)  (tools)  (tools)  (tools)  (tools)  (tools)  (tools)
```

| Concept | Why It Matters |
|---------|---------------|
| **Holarchy** | Every manager IS a swarm. A department manager can spin up an entire sub-company by loading a sub-swarm config. **Recursion all the way down.** |
| **Message Bus** | Agents never call each other directly — they publish, others consume. Agents can live on different machines, processes, or continents. |
| **Self-Similar** | Same pattern at every scale. 3 agents or 3,000 — the architecture doesn't change. |

---

## 🛠️ Tool Plugin System

Agents are powerful, but agents with **tools** are unstoppable. Every worker agent can call tools in a loop: the LLM decides what to use, the runtime executes it, and the result feeds back into the agent's next decision.

### 🔧 Built-in Tools

| Tool | What It Does | Example |
|------|-------------|---------|
| 📖 **Read File** | Read files from the filesystem | `read_file(file_path="data.txt")` |
| ✏️ **Write File** | Write content to files | `write_file(file_path="out.txt", content="hello")` |
| 💻 **Bash** | Run shell commands | `bash(command="ls -la")` |
| 🌐 **Web Fetch** | Fetch URLs (http/https only) | `web_fetch(url="https://example.com")` |
| 🐍 **Python Exec** | Execute Python code | `python_exec(code="print(2+2)")` |

### 🔌 How It Works

```
LLM decides ──→ emits TOOL_CALL ──→ runtime parses ──→ executes tool
     ↑                                                      │
     └──────────── result fed back ─────────────────────────┘
     └────── repeat until LLM gives final answer ──────────→ DONE
```

### 🧪 Example Tool Flow

```
Agent prompt: "Calculate 25 * 4 and save the result"
     │
     ▼
LLM responds: TOOL_CALL: python_exec(code="print(25 * 4)")
     │
     ▼
Runtime executes → result: "100"
     │
     ▼
LLM continues: TOOL_CALL: write_file(file_path="result.txt", content="100")
     │
     ▼
Runtime executes → result: "Wrote 3 bytes to result.txt"
     │
     ▼
Final answer: "The result is 100. I've saved it to result.txt ✅"
```

### 🧱 Tool API

Adding your own tool is a 30-second job:

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
        # ... do the thing ...
        return ToolResult(success=True, output="done ✅")
```

**Security built in:** File tools prevent path traversal attacks, bash/python tools run in isolated subprocesses with timeouts, web fetch only allows http/https.

---

## 🚀 Quick Start

### 📦 Install

```bash
git clone https://github.com/akhilyad/swarm.git
cd swarm
pip install -e .
```

### 🎮 Simulate (No API Key Needed)

```bash
swarm simulate --config configs/examples/software-dev.yaml \
  --goal "Design a task management API"
```

Watch the CEO decompose goals, managers delegate, and employees execute — all simulated, zero LLM cost.

### 🤖 Run With Real AI

```bash
export OPENAI_API_KEY="sk-..."
swarm run --config configs/examples/software-dev.yaml \
  --goal "Design a task management API"
```

### 🔍 Explore the Company

```bash
swarm agents --config configs/examples/software-dev.yaml
# Shows: CEO → Managers → Employees with roles and hierarchy
```

---

## 📋 Example Config

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

  lead-eng:
    name: "Engineering"
    role: MANAGER
    parent: ceo
    children: [developer]

  researcher:
    name: "Researcher"
    role: WORKER
    parent: pm

  writer:
    name: "Writer"
    role: WORKER
    parent: pm

  developer:
    name: "Developer"
    role: WORKER
    parent: lead-eng
```

Drop in more configs or build your own — marketing agency, research lab, legal firm, or a squad of AI chaos gremlins. Your call.

---

## 📁 Project Structure

```
hyrex/
├── pyproject.toml                    # Dependencies & metadata
├── configs/examples/                 # YAML company configs
│   ├── software-dev.yaml             # 9-agent dev agency
│   ├── research.yaml                 # 6-agent research firm
│   └── general.yaml                  # 7-agent general company
├── src/
│   ├── cli.py                        # CLI entry point (click)
│   ├── core/
│   │   ├── types.py                  # Data models & enums
│   │   ├── config.py                 # YAML config loader
│   │   ├── node.py                   # NodeHandle runtime wrapper
│   │   └── errors.py                 # Custom exceptions
│   ├── swarm/
│   │   ├── factory.py                # Build swarm from config
│   │   └── registry.py               # Tree navigation & lookup
│   ├── runtime/
│   │   ├── orchestrator.py           # Top-level coordinator
│   │   └── agent_loop.py             # Per-agent async event loop
│   ├── communication/
│   │   ├── bus.py                    # Async pub/sub message bus
│   │   ├── message.py                # Message types & factories
│   │   └── protocol.py               # Fan-out, request/response
│   ├── tools/                        # 🔌 Tool Plugin System
│   │   ├── __init__.py               # register_all_tools() helper
│   │   ├── base.py                   # BaseTool, ToolResult, ToolRegistry
│   │   └── builtin/
│   │       ├── read_file.py          # 📖 Read file tool
│   │       ├── write_file.py         # ✏️ Write file tool
│   │       ├── bash.py               # 💻 Bash command tool
│   │       ├── web_fetch.py          # 🌐 Web fetch tool
│   │       └── python_exec.py        # 🐍 Python exec tool
│   ├── memory/
│   │   ├── store.py                  # Abstract memory interface
│   │   └── chroma_store.py           # ChromaDB implementation
│   └── llm/
│       └── client.py                 # LiteLLM wrapper w/ cost tracking
└── tests/
    ├── test_types.py                 # Data model tests
    ├── test_config.py                # Config loading tests
    ├── test_registry.py              # Swarm registry tests
    ├── test_node.py                  # NodeHandle tests
    ├── test_bus.py                   # Message bus tests
    ├── test_agent_loop.py            # Core agent loop tests
    ├── test_tools_base.py            # 🆕 Tool base tests (11)
    ├── test_tools_builtin.py         # 🆕 Built-in tool tests (24)
    └── test_agent_loop_tools.py      # 🆕 Tool integration tests (7)
```

---

## 🧪 Testing

```bash
# 102 tests, all passing
pytest -v

# With coverage
pytest --cov=src --cov-report=term-missing
```

### Test Breakdown

| Test Suite | Tests | What It Covers |
|-----------|-------|----------------|
| `test_tools_base.py` | 11 | BaseTool, ToolResult immutability, ToolRegistry lifecycle |
| `test_tools_builtin.py` | 24 | Read/Write/Exec/Web/Fetch — each tool isolated |
| `test_agent_loop_tools.py` | 7 | Agent loop tool parsing, iteration limits, backward compat |

---

## 🎯 Why Hyrex?

| Problem | Solution |
|---------|----------|
| One LLM call isn't very smart | Hierarchical planning produces _much_ better results |
| Flat swarms of agents are chaotic | Tree structure = clear chain of command |
| Agents need to communicate without chaos | **Async message bus** keeps everyone in sync |
| LLM costs can explode | Built-in **budget tracking** per run, per agent |
| Agents need real-world capabilities | **Tool Plugin System** — files, shell, web, code execution |
| "Works on my machine" | Fully async, designed for distributed from day one |

---

## 🗺️ Roadmap

- [x] **Tool Plugin System** — Workers with file, shell, web, and code execution tools _(Done — 5 built-in tools, 42 tests)_
- [x] **102 tests passing** — Tool base, built-ins, and agent loop integration
- [ ] **Web Dashboard** — Watch your AI agents work in real time. It's hypnotic.
- [ ] **Distributed Agents** — Spread your swarm across machines
- [ ] **Persistent Memory** — Agents that remember what they did last session
- [ ] **Human-in-the-Loop** — Approval gates so your AI company doesn't go rogue
- [ ] **Template Marketplace** — Buy and sell company configs. "One AI Marketing Agency, please."

---

## 🤝 Contributing

PRs welcome. If you can dream up a weirder, more efficient, or more dramatic way to organize AI agents, this is the place.

```bash
git checkout -b feature/your-idea
git commit -m 'Add your idea'
git push origin feature/your-idea
# Then open a PR
```

---

## 📄 License

**MIT** — Go build your AI empire. Don't blame us when your swarm unionizes.

---

<div align="center">

_Built with 🍕 and existential dread by [@akhilyad](https://github.com/akhilyad)_

_In a world of AGI hype, be Hyrex._

```
   ╱▔▔╲       ╱▔▔╲       ╱▔▔╲
  ╱    ╲     ╱    ╲     ╱    ╲
  ▏CEO  ▕   ▏MGR  ▕   ▏WKR  ▕
  ╲    ╱     ╲    ╱     ╲    ╱
   ╲▁▁╱       ╲▁▁╱       ╲▁▁╱
```

</div>

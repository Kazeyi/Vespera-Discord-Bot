# Roadmap

## Phase 1 — Foundation ✅ Live

The current, production-deployed state of Vespera.

| Component | Status |
|-----------|--------|
| Hybrid Model Orchestration (Groq + Gemini) | ✅ Complete |
| Truth Block Protocol (RAG-Lite) | ✅ Complete |
| Cloud Engine — AI Advisor + RAG (186 practices) | ✅ Complete |
| Cloud Engine — Terraform Validation Pipeline | ✅ Complete |
| Cloud Engine — Guardrails (Budget / Security / Compliance) | ✅ Complete |
| D&D — Action Economy Validator | ✅ Complete |
| D&D — Rulebook Ingestor (SRD 2024) | ✅ Complete |
| D&D — Generational Void Cycle (3-Phase Campaign Engine) | ✅ Complete |
| Utility — Translator (4 styles + smart glossaries) | ✅ Complete |
| Utility — TL;DR (chunked + string interned) | ✅ Complete |
| Utility — Moderator (AI hostility scoring + LRU cache) | ✅ Complete |
| Aggressive Memory Hygiene (1GB RAM budget) | ✅ Complete |
| Chain-of-Thought Enforcement | ✅ Complete |
| VesperaPersonality Singleton | ✅ Complete |

---

## Phase 2 — Agentic Dissection 🔨 June 2026

**Goal:** Break the monolith. Implement self-correction via Sequential Agentic Workflow.

| Feature | Description |
|---------|-------------|
| **The Blackboard** | Deploy `agent_tasks`, `ai_response_cache`, `system_corrections` SQLite tables. Commands write to DB instead of calling AI directly. |
| **Self-Correction** | Arbiter (Router) → Weaver-Stylist (Actor) → Deep Critic (Reviewer) pipeline with automatic retries on rule violations. |
| **XAI Traceability** | `logic_trace` column on every agent task. `/why` command lets users see which agent made which decision. |
| **Loop Guards** | Hard `retry_count` cap (max 3). Semaphore limiting 3 concurrent pipelines, queue depth 10. |
| **Security Mitigations** | Cache poisoning prevention, loop injection cap, structured output validation by the Critic. |

See the full technical design: [Planned — Lite MAS](architecture/lite-mas.md)

---

## Phase 3 — Modular Skill-Set 🔭 July – August 2026

**Goal:** True scalability and industry-standard tooling integration.

| Feature | Description |
|---------|-------------|
| **Skill-Based Architecture** | Move logic out of Cogs into standalone `skills/` modules. `skills/cloud/` holds Terraform templates and CLI handlers. `skills/dnd/` holds rulebook fragments and combat logic. |
| **Model Context Protocol (MCP)** | Integrate an MCP client, allowing Vespera to interface with any MCP-compatible external tool without writing custom wrappers per API. |
| **The Proactive Pulse** | A background `asyncio` task that wakes on a configurable schedule (e.g., every 60 minutes) to proactively audit cloud FinOps costs or check narrative progression — making Vespera an agent, not just a responder. |
| **Semantic Long-Term Memory (RAG 2.0)** | Upgrade from keyword RAG to embedding-based semantic retrieval, allowing contextual memory that persists meaningfully across campaign sessions or cloud projects. |

---

## Future Possibilities

These are exploratory ideas with no committed timeline:

- **Auto-Improvement Cron**: A nightly background job that reviews Critic rejection logs and proposes prompt refinements
- **Persona Guardrails**: Formal constitutional constraints on Vespera's personality to prevent tone drift even under adversarial prompting
- **Cross-Guild Knowledge Sharing**: Opt-in anonymized best-practice sharing between servers for the Cloud Engine RAG base

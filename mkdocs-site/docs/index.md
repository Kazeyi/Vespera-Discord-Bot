# Vespera — The Silent Architect

> A modular, AI-powered Discord bot for Cloud Engineering, Tabletop RPGs, and Community Moderation — designed to run on 1 vCPU / 1GB RAM.

<div class="grid cards" markdown>

-   :material-lightning-bolt: **&lt;2s Latency**

    Near-instant responses via Groq LPU inference for time-critical game interactions.

-   :material-memory: **1-Core / 1GB VPS**

    Aggressive memory optimizations — GC tuning, String Interning, strict LRU caches — keep the footprint flat over time.

-   :material-database: **186 Cloud Best Practices**

    RAG knowledge base across GCP, AWS, and Azure powering the Cloud Engine advisor.

-   :material-shield-check: **RAG-Powered Accuracy**

    The Truth Block Protocol constrains AI output to verified facts only — no hallucinated spells or invalid Terraform resources.

</div>

---

## What is Vespera?

Vespera is a Discord bot built around a **"Persona as Infrastructure"** philosophy. Rather than bolting AI responses onto a simple command router, every module — Cloud, D&D, Moderation — shares a single `VesperaPersonality` singleton that guarantees consistent tone, color palette, and error messaging across all 15+ cogs.

The system dynamically routes tasks to the best model for the job: **Groq (Llama-3)** for sub-500ms game round responses and **Gemini Pro 1.5** for large-context cloud document analysis. All AI outputs touching factual domains (D&D rules, Terraform specs) are constrained by **Truth Blocks** — verbatim data injected from verified sources that the model is strictly instructed to format, never invent.

[View Architecture :material-arrow-right:](architecture/current.md){ .md-button .md-button--primary }
[GitHub Repository :material-github:](https://github.com/Kazeyi/Vespera-Discord-Bot){ .md-button }

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Runtime** | Python 3.11, asyncio |
| **Bot Framework** | discord.py |
| **Database** | SQLite (WAL mode) |
| **Fast Inference** | Groq — Llama 3.3 / Mixtral |
| **Large Context** | Google Gemini Pro 1.5 |
| **IaC Generation** | Terraform (AWS / GCP / Azure) |
| **Data Store** | SQLite (bot_database.db, cloud_infrastructure.db, cloud_knowledge.db) |

---

## Core Modules

| Module | Purpose |
|--------|---------|
| [☁️ Cloud Engine](features/cloud.md) | AI infrastructure advisor, Terraform code generation, cost estimation |
| [🐉 D&D System](features/dnd.md) | 5e rules engine, character management, narrative AI |
| [🛡️ Utility Core](features/utility.md) | Translation, summarization, automated moderation |

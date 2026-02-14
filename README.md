# Vespera Discord Bot

Vespera ("The Silent Architect") is a highly modular, advanced Discord bot designed for Cloud Engineering Operations, Tabletop RPG management, and Community Moderation.

## Core Features
*   **Vespera Personality Engine**: A unified response system ensuring consistent tone and style across all bot interactions.
*   **Cloud Engine**: AI-driven infrastructure advisor, Terraform code generation (AWS/GCP/Azure), and cost estimation.
*   **Dungeons & Dragons System**: Complete 5e rules integration, character sheet management, and narrative AI assistance.
*   **Moderator Core**: Automated threat analysis and community safety tools.
*   **Utility Core**: Centralized memory management and optimization for low-resource environments (1 Core / 1GB RAM optimized).

## 🧠 The Architecture of Logic: Technical Glossary

Vespera is not just a wrapper for an LLM; she is a curated system of distinct cognitive architectures, each chosen to solve a specific problem in accuracy, speed, or memory.

### 1. Hybrid Model Orchestration
We do not use a "one size fits all" model. Vespera dynamically routes tasks to the most efficient engine based on the nature of the request.

| Module | Engine | Rationale |
| :--- | :--- | :--- |
| **D&D Combat & Roleplay** | **Groq (Llama-3)** | **Speed is King.** Combat rounds must happen instantly (>500ms). Groq's LPU inference delivers near-instantaneous responses, keeping the game flow uninterrupted. High reasoning capability isn't needed for "Goblin attacks with +4", but speed is critical. |
| **Utility & Cloud Ops** | **Gemini Pro 1.5** | **Context is King.** Translating documents or analyzing Terraform state files requires massive context windows (1M+ tokens). We knowingly sacrifice speed (latency) for the ability to ingest entire log files, policy docs, or codebases in a single shot without truncation. |

### 2. The "Truth Block" Protocol (RAG-Lite)
In AI generation, "hallucination" is the enemy of Cloud Infrastructure and D&D Rules. Vespera minimizes this via the Truth Block architecture:
1.  **Retrieval**: Fetch raw data (SRD JSON for D&D, Terraform Docs for Cloud) from the local database.
2.  **Injection**: Pass this *verbatim* data into a dedicated section of the system prompt called the `[TRUTH_BLOCK]`.
3.  **Constraint**: The AI is strictly instructed to *only* format or explain the injected data, never to invent it.
    *   *Result*: She won't invent a D&D spell that doesn't exist, nor will she invent a Terraform resource type that causes `terraform apply` errors.

### 3. Chain of Thought (CoT) Enforcement
For complex tasks where "gut feeling" is dangerous (Moderation Analysis, Cloud Cost Estimation), Vespera is forced to show her work:
*   Before giving a final answer, the internal prompt requires a `[Reasoning]` block.
*   This forces the model to step through logic (e.g., "User said X, context is Y, therefore hostility is Low") *before* committing to an output.
*   **Why?**: LLMs generate token-by-token. If they start a sentence with "This is safe", they are biased to justify it. By forcing reasoning *first*, we significantly reduce false positives in moderation and prevent "math errors" in cloud estimation.

### 4. Lazy Context Injection (The "Need-to-Know" Principle)
Used heavily in the **Translator** and **D&D Spell Lookup**.
*   **The Problem**: Sending the entire D&D Player's Handbook or a full Cloud Glossary in every prompt is expensive and confuses the model ("Lost in the Middle" phenomenon).
*   **The Solution**: We scan the user's input for keywords (e.g., "Fireball", "Kubernetes"). Only *if* a keyword is found do we inject the specific definition for that term.
*   **Benefit**: Reduces token consumption by ~90% and increases accuracy by removing irrelevant noise from the context window.

### 5. Aggressive Memory Hygiene (The 1GB Ceiling)
Vespera is optimized to run on low-spec instances (1 vCPU, 1GB RAM).
*   **Manual GC Tuning**: We override Python's default Garbage Collection thresholds (`gc.set_threshold`) to force collection more frequently than standard apps.
*   **String Interning**: In the TL;DR and Log Analysis modules, we use `sys.intern()` for repeated headers or usernames. This ensures that if the string "User_X" appears 1,000 times, it only consumes memory for 1 string object.
*   **LRU Caching**: We utilize Strict LRU (Least Recently Used) caches with hard caps (e.g., max 128 items) to ensure the memory footprint remains flat over time, rather than growing indefinitely.

### 6. The "Vespera" Singleton (Persona as Infrastructure)
To prevent **Personality Drift**—where the bot sounds like a pirate in one command and a corporate assistant in another—we decoupled the personality from the logic.
*   **Implementation**: A static class `VesperaPersonality` acts as the "Single Source of Truth".
*   **Usage**: All 15+ cogs import their prompts, color palettes (`0x2C2F33`), and error messages from this central registry.
*   **Effect**: If we need to change Vespera's tone from "Cold Architect" to "Happy Helper", we change it in *one* file, and the entire bot updates instantly.

## Future Roadmap

### Phase 2: Transition to Sequential Agentic Orchestration
*Goal: Evolving Vespera from a monolithic utility into a collaborative Multi-Agent System (MAS) optimized for low-resource environments (1GB RAM).*

**Core Architecture**: Transitioning from in-memory context to a "Blackboard" Pattern (SQLite State Machine), allowing agents to hibernate when idle.

#### 1. Dungeons & Dragons (Narrative Engine)
*   **The Weaver (Generative)**: Drafts the story, improvisation, and NPC dialogue. 
*   **The Arbiter (Governance)**: Checks the draft against 5e Rules (Truth Blocks) and dice rolls. Rejects "impossible" actions or "hallucinated" spells.
*   **The Stylist (Persona)**: Refines the output into the immersive "Dungeon Master" tone.

#### 2. Cloud Engine (Infrastructure Operations)
*   **The Architect (Planner)**: Generates Terraform code and architectural diagrams based on user intent.
*   **The Sentinel (Security)**: Audits the code against Policy-as-Code (IAM restrictions, Cost Budgets). Blocks insecure deployments before they happen.
*   **The Liaison (Interface)**: Translates technical errors, Terraform plans, and JSON outputs into human-readable executive summaries.

#### 3. Moderator Core (Community Governance)
*   **The Watcher (Analysis)**: Scans chat context for sentiment and pattern matching (beyond simple REGEX).
*   **The Justicar (Verdict)**: Compares behavior against the server's specific Constitution/Rulebook to determine intent.
*   **The Diplomat (Intervention)**: Generates de-escalation messages or ban notices that are firm but professional, avoiding "robotic" automated warnings.

## Installation
1.  Clone the repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Set up environment variables in `.env`.
4.  Run the bot:
    ```bash
    python3 main.py
    ```

## License
MIT License

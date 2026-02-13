# Vespera Discord Bot

Vespera ("The Silent Architect") is a highly modular, advanced Discord bot designed for Cloud Engineering Operations, Tabletop RPG management, and Community Moderation.

## Core Features
*   **Vespera Personality Engine**: A unified response system ensuring consistent tone and style across all bot interactions.
*   **Cloud Engine**: AI-driven infrastructure advisor, Terraform code generation (AWS/GCP/Azure), and cost estimation.
*   **Dungeons & Dragons System**: Complete 5e rules integration, character sheet management, and narrative AI assistance.
*   **Moderator Core**: Automated threat analysis and community safety tools.
*   **Utility Core**: Centralized memory management and optimization for low-resource environments (1 Core / 1GB RAM optimized).

## 🧠 The Architecture of Logic: Technical Glossary

Vespera is not just a wrapper for an LLM; she is a curated system of distinct cognitive architectures. Every technical choice was made to balance **Latency**, **Accuracy**, and **Context**.

### 1. Hybrid Model Orchestration
We do not use a "one size fits all" model. Vespera dynamically routes tasks to the most efficient engine:

| Module | Engine | Rationale |
| :--- | :--- | :--- |
| **D&D Combat & Roleplay** | **Groq (Llama-3)** | **Speed is King.** Combat rounds must happen instantly. Groq's LPU inference delivers near-instantaneous responses, keeping the game flow uninterrupted. High reasoning capability isn't needed for "Goblin attacks with +4". |
| **Utility & Cloud Ops** | **Gemini Pro 1.5** | **Context is King.** Translating documents or analyzing Terraform state files requires massive context windows (1M+ tokens). We knowingly sacrifice speed for the ability to ingest entire log files or documentation chapters in one shot. |

### 2. The "Truth Block" Protocol
In AI generation, "hallucination" is the enemy of Cloud Infrastructure and D&D Rules. Vespera minimizes this via the Truth Block architecture:
1.  **Retrieval**: Fetch raw data (SRD JSON for D&D, Terraform Docs for Cloud).
2.  **Injection**: Pass this *verbatim* data into the system prompt.
3.  **Constraint**: The AI is instructed to *only* format the injected data, never to invent it.
    *   *Result*: She won't invent a D&D spell that doesn't exist, nor will she invent a Terraform resource type that causes `apply` errors.

### 3. Chain of Thought (CoT) Enforcement
For complex tasks (Moderation Analysis, Cloud Cost Estimation), Vespera is forced to show her work:
*   Before giving a final answer, the internal prompt requires a `[Reasoning]` block.
*   This forces the model to step through logic (e.g., "User said X, context is Y, therefore hostility is Low") before committing to an output.
*   This significantly reduces false positives in moderation and prevents "math errors" in cloud cost estimation.

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

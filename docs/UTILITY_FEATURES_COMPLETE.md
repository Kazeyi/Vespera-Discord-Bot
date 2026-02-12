# UTILITY FEATURES DOCUMENTATION

> Updated: Generational Update (Vespera Integration)

## Table of Contents
- [Overview](#overview)
- [Core Personality (Vespera)](#core-personality-vespera)
- [1. Translator Cog](#1--translator-cog-cogstranslatepy)
- [2. TL;DR Cog](#2--tldr-cog-cogstldrpy)
- [3. Moderator Cog](#3--moderator-cog-cogsmoderatorpy)

---

# Overview

The **Utility Core** (`cogs/utility_core/`) is the foundation of the bot. It provides essential shared services including personality consistency, memory optimization, language processing, and moderation.

The Discord Cogs (`cogs/translate.py`, `cogs/tldr.py`, `cogs/moderator.py`) act as lightweight wrappers around this core logic, ensuring strict Separation of Concerns.

---

# Core Personality (Vespera)

**Module:** `cogs/utility_core/personality.py`

This module acts as the Single Source of Truth for the bot's identity. Instead of hardcoding prompts and colors in every file, all Cogs reference `VesperaPersonality`.

### Key Components
*   **Identity**: Defines Name ("Vespera"), Title ("The Silent Architect"), and System Prompts.
*   **Visual Identity**: Centralized Color Palette (`VP.Colors`) ensures consistent Embed styling across Cloud, D&D, and Mod logs.
    *   `VP.Colors.PRIMARY`: Dark Grey/Black (Base)
    *   `VP.Colors.SUCCESS`: Muted Green
    *   `VP.Colors.ERROR`: Red
    *   `VP.Colors.MYSTIC`: Purple (D&D)
    *   `VP.Colors.CLOUD`: Blue (Cloud)
*   **Response Registry**: Pre-defined static responses for common errors, permissions warnings, and startup messages.

---

## 1. 🌍 Translator Cog (`cogs/translate.py`)

**Status:** `Lazy Glossary Optimized` & `Personality Integrated`

### 🎯 Purpose
AI-powered translation with specific support for **D&D** and **Cloud** terminology. It uses "Lazy Glossary Injection" to only include relevant terms in the prompt, saving tokens and improving accuracy.

### ✨ Key Features
*   **Context-Aware Translation**: Understands technical jargon.
*   **4 Styles**: 
    *   **Formal**: Professional business tone.
    *   **Informal**: Casual conversation.
    *   **Slang**: Internet slang and idioms.
    *   **Lyrical**: Poetic or dramatic (great for D&D).
*   **Smart Glossaries**:
    *   **D&D**: *Fireball, Saving Throw, Advantage/Disadvantage...*
    *   **Cloud**: *Kubernetes, Docker, AWS, Serverless...*
*   **Interface**:
    *   `/translate <text> <language> <style>`
    *   **Reaction Trigger**: Add a flag emoji (🇺🇸, 🇯🇵, etc.) to a message to translate it to that language.

### 🚀 Optimizations
*   **Lazy Glossary Injection**: Reduces prompt size by 95% by only injecting terms present in the input text.
*   **Memory Usage**: ~25MB RAM (down from 60MB).
*   **String Interning**: Caches glossary keys.

---

## 2. 📝 TL;DR Cog (`cogs/tldr.py`)

**Status:** `JSON Optimized` & `String Interned`

### 🎯 Purpose
Provides instant summarization of chat logs or uploaded text files. It is heavily optimized to run in low-memory environments.

### ✨ Key Features
*   **Modes**:
    *   **Summarize**: A general overview.
    *   **Action Items**: Extracts to-do lists and assignments.
    *   **Key Points**: Bulleted list of critical information.
*   **Input Support**:
    *   Chat History (Last N messages)
    *   Text Files (`.txt`, `.md`, `.log`)

### 🚀 Optimizations
*   **String Interning**: Repeated words in chat logs are interned to save RAM.
*   **Chunked Processing**: Large files are processed in stream-safe chunks.

---

## 3. 🛡️ Moderator Cog (`cogs/moderator.py`)

**Status:** `Vespera Integrated`

### 🎯 Purpose
Automated threat analysis and community safety. Uses the AI engine to detect hostility, spam, or rule violations with nuance that regex cannot match.

### ✨ Key Features
*   **Threat Analysis**: Assigns a "Hostility Score" (0-10) to messages.
*   **Hallucination Check**: Verifies if the AI is generating safe responses.
*   **Personality Integration**: Violations are flagged using the `VP.Colors.ERROR` palette and Vespera's strict tone.

### 🚀 Optimizations
*   **LRU Cache**: Caches analysis results for frequent phrases to avoid wasted API calls.

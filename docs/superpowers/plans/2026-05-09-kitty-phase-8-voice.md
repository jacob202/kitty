# Phase 8 — Voice Input & Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable Jacob to talk to Kitty and hear her voice responses. Uses `faster-whisper` for STT and `Kokoro TTS` for TTS.

**Architecture:**
1. Two standalone FastAPI microservices (or modules within the Gateway).
2. OpenAI-compatible endpoints: `/v1/audio/transcriptions` and `/v1/audio/speech`.
3. Open WebUI connects to these endpoints.

**Tech Stack:** Python 3.12, `faster-whisper`, `Kokoro-TTS`, FastAPI.

---

## Task 1: Setup Speech-to-Text (STT)

- [ ] **Step 1: Install `faster-whisper`**
```bash
./venv/bin/pip install faster-whisper
```

- [ ] **Step 2: Create STT Service wrapper**
- [ ] **Step 3: Wire into Open WebUI settings**

---

## Task 2: Setup Text-to-Speech (TTS)

- [ ] **Step 1: Install `Kokoro-TTS`**
- [ ] **Step 2: Create TTS Service wrapper**
- [ ] **Step 3: Wire into Open WebUI settings**

---

## Verification

Gate: Speak a sentence in the Open WebUI, verify Kitty "hears" it and her text response is read aloud in the chosen voice.

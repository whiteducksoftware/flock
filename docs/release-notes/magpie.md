---
title: Magpie – 0.1.0
---

# Release: Magpie 🐦

We're thrilled to announce **Flock 0.1.0 (codename "Magpie")** – the first public release!  Magpies are known for their intelligence and ability to collect shiny objects; likewise this release brings together the essential pieces for building smart, modular AI agent systems.

## Highlights

### ✨ Declarative Agent Core

* Define agents via `input` / `output` signatures.
* Built-in `DeclarativeEvaluator` turns those specs into GPT-4o calls automatically.

### 🔌 Plug-in Architecture

* **Modules** for output formatting, metrics, memory, and tracing.
* **Tools** registered with `@flock_tool` give agents real-world powers.
* **Routers** enable dynamic branching.

### 🚀 Temporal Integration

* Toggle `enable_temporal=True` to run your flock as a *durable workflow*.
* Automatic retries, state persistence, and visibility via Temporal Web.

### 📊 Observability

* Structured logging with `fmtlog`.
* OpenTelemetry spans for every agent hook and workflow stage.

### 🧪 Testing & CLI Goodies

* CLI for quick runs: `flock run path/to/flock.yaml`.
* REST API & Web UI prototype included.
* Comprehensive examples in `.flock/01-getting-started` & `.flock/02-core-concepts`.

## Upgrade Notes

This is a **major baseline**; future 0.x releases may include breaking changes as we stabilise the API.  For production workloads pin the minor version (`0.1.*`).

## Acknowledgements

Huge thanks to the early adopters and the Temporal community for invaluable feedback.

---

Happy hacking, and welcome to the Flock! 🐣

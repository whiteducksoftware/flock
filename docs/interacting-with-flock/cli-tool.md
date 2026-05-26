---
hide:
  - toc
---

# 🛠️ Flock CLI Tool

Beyond integrating Flock into your Python code or exposing it via an API, Flock provides a dedicated command-line interface (CLI) tool, accessed simply by running `flock` in your terminal (once installed).

This tool is primarily designed for **managing and interacting with persistent Flock configurations** stored in `.flock.yaml` files.

## Key Features

* **Loading Flocks:** Load complete Flock configurations, including agents, types, and components, from `.flock.yaml` files.
* **Creating Flocks:** A guided wizard (`flock` -> "Create a new Flock") helps you scaffold a new `.flock.yaml` file with basic settings and initial agents.
* **Executing Flocks:** Run workflows (single or batch) defined within a loaded `.flock.yaml` file directly from the command line.
* **Registry Management:** View, add, remove, and automatically scan for components (agents, types, callables/tools) in the global Flock registry. This is crucial for ensuring correct serialization and deserialization.
* **Settings Management:** View and edit global Flock settings, primarily environment variables stored in `~/.flock/.env`, including API keys and configuration flags. Manage different `.env` profiles.
* **Theme Builder:** Interactively preview and configure output themes for agents using rich tables.
* **(Future):** Potential deployment commands (e.g., to Docker, Kubernetes).

## How to Use

1. **Installation:** Ensure `flock-core` (or the relevant package) is installed in your environment.
2. **Run:** Simply type `flock` in your terminal.
3. **Navigate:** Use the interactive menu (powered by `questionary`) to select actions like "Load a *.flock file", "Create a new Flock", "Registry management", "Settings", etc.

*(Placeholder: Screenshot of the main `flock` CLI menu)*

## Distinction from Other Interaction Methods

* **vs. Programmatic API:** The CLI tool operates on *serialized* Flock states (`.flock.yaml`), while the programmatic API works with `Flock` *objects* in Python memory. The CLI is for management; the API is for integration.
* **vs. Interactive Script CLI:** The `flock` tool is a standalone application for managing configurations. The `flock.start_cli()` method discussed in [Interactive Script CLI](interactive-cli.md) is used *within* a Python script for debugging the *current*, in-memory `Flock` instance.

Use the Flock CLI tool when you need to:

* Save and load reusable Flock configurations.
* Execute predefined workflows without writing Python scripts each time.
* Manage the global registry of components, types, and tools shared across your projects.
* Configure global settings like API keys or CLI behavior.

---
hide:
  - toc
---

# Interacting with Flock: Beyond the Build 🚀

You've designed your Flock, defined your agents, and maybe even chained them together. Now what? How do you actually *use* your sophisticated AI system?

Flock is designed for flexibility, offering multiple ways to interact with your agents and workflows, catering to different needs from development and debugging to integration and deployment.

This section explores the primary methods for interacting with a configured `Flock` instance:

*   **[🐍 Programmatic API (Python)](programmatic.md):** The most direct way. Integrate Flock directly into your Python applications, trigger runs, and process results using simple method calls like `flock.run()`, `flock.run_async()`, and `flock.run_batch()`. Ideal for core development and integration within Python projects.
*   **[🌐 REST API](rest-api.md):** Expose your Flock as a web service. Start a FastAPI server (`flock.start_api()`) to allow remote execution via HTTP requests. Perfect for integrating Flock with web frontends, other microservices, or external systems.
*   **[🖥️ Web UI (FastHTML)](web-ui.md):** A simple, automatically generated web interface for interactive testing and demonstrations. Launch it alongside the REST API (`flock.start_api(create_ui=True)`) for a quick way to select agents, provide inputs, and view results in your browser.
*   **[🛠️ Flock CLI Tool](cli-tool.md):** Manage your Flock configurations using the main `flock` command-line tool. Load `.flock.yaml` files, execute runs, manage the registry, and configure settings without writing Python code. Best for system administration and managing saved Flock states.
*   **[⌨️ Interactive Script CLI](interactive-cli.md):** Debug agent interactions directly within your terminal while running a Python script using `flock.start_cli()`. Useful for stepping through agent handoffs and inspecting context during development.

Choose the interaction method that best suits your current task, whether it's embedding AI logic deep within an application, providing an API for others, quickly demoing capabilities, or managing persistent configurations.
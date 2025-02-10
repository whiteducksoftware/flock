
## Requirements

- **Python:** 3.12+
- **Temporal Server:** (Optional) Run locally for production-grade workflow features.
- **API Keys:** Required for integrated services (e.g., Tavily for web search).

---

## User Installation

Install the core package:

```bash
pip install flock-core
```

To use the integrated tools:

```bash
pip install flock-core[tools]
```

For full functionality (including the docling tools, which require PyTorch):

```bash
pip install flock-core[all-tools]
```

---

## Development Setup

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/yourusername/flock.git
   cd flock
   ```

2. **Create a Virtual Environment and Sync All Packages:**

   ```bash
   uv sync --all-groups --all-extras
   ```

3. **Install the Local Version of Flock:**

   ```bash
   uv build && uv pip install -e .
   ```

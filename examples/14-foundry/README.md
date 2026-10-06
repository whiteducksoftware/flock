# 14 - Microsoft Foundry hosted agents

Host a `FlockApplication` as a Microsoft Foundry hosted agent with the optional
`foundry` extra:

```bash
uv add "flock-core[azure,foundry]"
```

```python
from flock.integrations.foundry import FoundryResponsesAdapter

host = FoundryResponsesAdapter(application, input_mapper=..., output_mapper=...)
host.run()   # port $PORT or 8088
```

| Example | What it shows |
|---|---|
| [`incident-triage/`](incident-triage/) | Deployable sample in the official Foundry layout (`azure.yaml`, Dockerfile, `requirements.txt`), managed-identity model calls, local offline mode |

The applications API it builds on is in [`../13-applications`](../13-applications/).
Guide: [Microsoft Foundry hosted agents](https://whiteducksoftware.github.io/flock/guides/foundry/).

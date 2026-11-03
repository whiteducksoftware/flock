# 16 - Sinks

A sink is an external system as a consumer on the blackboard: it subscribes
like an agent, delivers what it consumes over HTTP and publishes a receipt,
`Delivered` or `DeliveryFailed`.

```python
flock = Flock(endpoints={"myapp": Endpoint("https://myapp.example", auth=Bearer(env="MYAPP_TOKEN"))})
flock.sink("billing-api").consumes(Reply).post("myapp:/billing", response=CrmRecord)
flock.agent("support").consumes(Ticket).publishes(Reply, post="myapp:/audit")
```

| Example | What it shows |
|---|---|
| [`01_billing_sink.py`](01_billing_sink.py) | Endpoints with a secret from the environment, a sink with a response type, the `publishes(..., post=)` shorthand, a retry and a rejected delivery; runs without API keys against a local stand-in server |
| [`02_snake.py`](02_snake.py) | A self-playing Snake: the game publishes every step over REST into one run per game, `azure/decision-1` decides the move, and a sink posts it back in order. Start/Pause on the page, a field for Flock's address, `--port` / `--flock-port`. `--fake` plays with a heuristic, no key |
| [`03_quick_draw.py`](03_quick_draw.py) | Quick, Draw!: the page uploads the canvas after every stroke (a multipart upload into an `Image` field), `openai/gpt-6-luna` guesses among 16 things, and a sink pushes every guess back until it is sure. `--fake` grows surer stroke by stroke, no key |

Both games open their own page (Snake on port 8792, Quick, Draw! on 8793) next to the dashboard on 8344.

Guide: [Sinks](https://whiteducksoftware.github.io/flock/guides/sinks/).

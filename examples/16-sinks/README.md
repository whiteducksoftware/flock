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

Guide: [Sinks](https://whiteducksoftware.github.io/flock/guides/sinks/).

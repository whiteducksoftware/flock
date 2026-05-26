# 🛠️ Adding Custom REST End-Points to a Flock API

Flock's built-in REST server ships with a handful of generic routes (`/run/*`, `/batch/*`, …). When you need to expose **bespoke functionality** — for example hiding complex agent initialization, or data enrichtment — you can declare additional routes with *zero boiler-plate*.

The `FlockEndpoint` helper lets you attach extra FastAPI routes while keeping full OpenAPI support.

```python title="quick-peek.py"
from pydantic import BaseModel
from flock.core import Flock
from flock.core.api.custom_endpoint import FlockEndpoint

class SlugifyReq(BaseModel):
    text: str

async def slugify(body: SlugifyReq):
    return {"slug": body.text.lower().replace(" ", "-")}

flock = Flock()
flock.start_api(
    custom_endpoints=[
        FlockEndpoint(
            path="/api/slugify",
            methods=["POST"],
            callback=slugify,
            request_model=SlugifyReq,
            summary="Turns a sentence into an URL slug",
        )
    ]
)
```

Hit <http://localhost:8344/docs> and you will see the **Slugify** operation alongside the default Flock API.

---

## 1️⃣ `FlockEndpoint` fields

| Field | Type | Description |
|-------|------|-------------|
| `path` | `str` | FastAPI-style route e.g. `/api/echo` or `/api/item/{id}` |
| `methods` | `list[str]` | HTTP verbs (default `['GET']`) |
| `callback` | `Callable` | Your async/sync handler |
| `request_model` | `BaseModel \| None` | Pydantic model for the request-body |
| `response_model` | `BaseModel \| None` | Explicit response schema |
| `summary`, `description` | `str` | Metadata shown in Swagger UI |
| `include_in_schema` | `bool` | Hide the route if set to `False` |

Any **kwarg** that appears in the callback's signature will be provided if possible:

* `body` – the deserialised request model (if declared)
* `query` – `dict` of query parameters
* `flock` – the active `Flock` instance
* Path parameters present in `path`

Everything else is ignored, so the handler remains clean.

---

## 2️⃣ Complete example (Yoda translator)

```python title="07-custom-endpoints.py" linenums="1"
from pydantic import BaseModel
from flock.core import Flock, FlockFactory
from flock.core.api.custom_endpoint import FlockEndpoint

class YodaReq(BaseModel):
    text: str

async def yoda(body: YodaReq, flock: Flock):
    res = await flock.run_async("yoda_translator", {"text": body.text})
    return {"yoda_text": res["yoda_text"]}

flock = Flock()
flock.add_agent(
    FlockFactory.create_default_agent(
        name="yoda_translator",
        input="text",
        output="yoda_text",
    )
)

flock.start_api(
    custom_endpoints=[
        FlockEndpoint(
            path="/api/yoda",
            methods=["POST"],
            callback=yoda,
            request_model=YodaReq,
            summary="Translate English into Yoda-speak",
        )
    ]
)
```

---

## 3️⃣ Testing utilities

In unit tests you can mount extra routes on a `TestClient`:

```python
from fastapi.testclient import TestClient
from flock.core.api.main import FlockAPI

api = FlockAPI(my_flock, custom_endpoints=[my_endpoint])
client = TestClient(api.app)
```

See `tests/api/test_custom_endpoints.py` for a ready-made example.

---

## 4️⃣ FAQ

**Q:** *Can I still use the old dict syntax?*  
**A:** Yes—`start_api(custom_endpoints={("/api/foo", ("GET",)): cb})` still works, but OpenAPI docs will be basic.

**Q:** *How do I add authentication or `Depends`?*  
**A:** Wrap the callback with FastAPI dependencies or use middleware; `FlockEndpoint` doesn't interfere with FastAPI's dependency system.

---

Happy hacking – and may your APIs soar like a flock of 🦜! 
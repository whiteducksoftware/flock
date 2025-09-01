# Hydrating Pydantic Models 🧪

Flock can “hydrate” Pydantic models — fill in missing fields using an LLM — via the `@flockclass` decorator. This creates a temporary agent from your model schema and runs it.

```python
from pydantic import BaseModel, Field
from flock.core.util.hydrator import flockclass

@flockclass(model="openai/gpt-5")
class RandomPerson(BaseModel):
    name: str | None = None
    age: int | None = None
    bio: str | None = Field(default=None, description="Short bio")

person = RandomPerson()
person = person.hydrate()  # fills missing fields
```

Notes:
- The decorator builds a dynamic agent using your field types and descriptions.
- The temporary Flock runs locally by default and returns updated model values.
- See `07-hydrator.py` for a complete example.

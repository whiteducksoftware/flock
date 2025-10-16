# 📐 Publishing Patterns

This folder demonstrates the various ways agents can publish artifacts to the blackboard—one of Flock's most powerful features.

## 🎯 What You'll Learn

These examples show the evolution from simple single-output agents to advanced fan-out patterns that generate multiple artifacts in one execution:

- **Single Publish** - One agent, one artifact type
- **Multi Publish** - One agent, multiple artifact types
- **Fan-Out** - One agent, multiple instances of the same type
- **Multi Fan-Out** - One agent, multiple instances of multiple types

## 📚 Examples

### 01 - Single Publish
**Pattern:** `consumes(Idea).publishes(Movie)`

The most basic pattern - one input artifact produces one output artifact. Each execution creates exactly one Movie from one Idea.

```bash
uv run 00-patterns/01-single_publish.py
```

**Use Case:** Simple 1:1 transformations

---

### 02 - Multi Publish
**Pattern:** `consumes(Idea).publishes(Movie, MovieScript, MovieCampaign)`

One agent execution produces multiple different artifact types. The agent outputs a Movie, a MovieScript, AND a MovieCampaign all in a single LLM call!

```bash
uv run 00-patterns/02-multi_publish.py
```

**Use Case:** When you need multiple perspectives or outputs from the same input

**💡 Key Benefit:** 3 artifacts in 1 LLM call = 67% cost savings vs 3 separate agents!

---

### 03 - Multi-Artifact Multi-Publish
**Pattern:** Multiple agents, each publishing multiple types

Complex orchestration where different agents produce multiple artifact types, creating rich blackboard interactions.

```bash
uv run 00-patterns/03-multi-artifact-multi-publish.py
```

**Use Case:** Complex workflows with multiple agents each producing varied outputs

---

### 04 - Fan-Out
**Pattern:** `consumes(Idea).publishes(Movie, fan_out=4)`

Generate multiple variations of the same type! One Idea produces 4 different Movie concepts—perfect for creative brainstorming.

```bash
uv run 00-patterns/04-fan-out.py
```

**Use Case:**
- Generate multiple alternatives
- A/B testing scenarios
- Creative exploration
- Portfolio diversification

**⭐ NEW in Flock 0.5**

---

### 05 - Multi Fan-Out
**Pattern:** `consumes(Idea).publishes(Movie, MovieScript, MovieCampaign, fan_out=3)`

The ultimate publishing pattern! Generate 3 instances of EACH type = 9 total artifacts from one execution:
- 3 Movies
- 3 MovieScripts
- 3 MovieCampaigns

```bash
uv run 00-patterns/05-multi-fan-out.py
```

**Use Case:** Maximum creative output with perfect context alignment

**💡 Cost Optimization:** 9 artifacts in 1 LLM call = 89% savings vs 9 separate calls!

**⭐ NEW in Flock 0.5**

---

## 🎓 Learning Path

Work through these examples in order:

1. **Start with 01** - Understand basic publishing
2. **Try 02** - See how multi-publish works
3. **Move to 04** - Learn fan-out for same-type generation
4. **Master 05** - Combine everything for maximum output

## 🔑 Key Concepts

### Why Fan-Out?

Traditional approach (without fan-out):
```python
# ❌ OLD WAY: 4 separate LLM calls
for i in range(4):
    await flock.invoke(movie_agent, idea)  # 4x the cost!
```

Fan-out approach:
```python
# ✅ NEW WAY: 1 LLM call, 4 outputs
agent.publishes(Movie, fan_out=4)
await flock.publish(idea)  # Generates 4 movies at once!
```

### Advanced Fan-Out Features

You can enhance fan-out with filtering and validation:

```python
# Filter low-quality outputs
agent.publishes(Movie, fan_out=10, where=lambda m: m.rating >= 8.0)

# Validate outputs
agent.publishes(Movie, fan_out=5, validate=lambda m: m.budget > 0)

# Dynamic visibility per artifact
agent.publishes(
    Movie,
    fan_out=3,
    visibility=lambda m: PrivateVisibility(agents=[m.target_audience])
)
```

## 💡 When to Use Each Pattern

| Pattern | Use When | Example |
|---------|----------|---------|
| **Single Publish** | Simple 1:1 transformations | Bug report → Diagnosis |
| **Multi Publish** | Need multiple outputs per input | Order → Invoice + Receipt + Tracking |
| **Fan-Out** | Want multiple variations | Idea → 5 different movie concepts |
| **Multi Fan-Out** | Need comprehensive output set | Idea → 3 Movies + 3 Scripts + 3 Campaigns |

## 🚀 Next Steps

After mastering these patterns, explore:
- **01-cli/** - See these patterns in complete workflows
- **02-dashboard/** - Visualize publishing patterns
- **03-claudes-workshop/** - Production patterns and best practices

## 📖 Additional Resources

- [Fan-Out Publishing Guide](https://github.com/whiteducksoftware/flock-flow/blob/main/docs/guides/fan-out.md)
- [Agent Guide](https://github.com/whiteducksoftware/flock-flow/blob/main/docs/guides/agents.md)
- AGENTS.md - Section on "Fan-Out Publishing"

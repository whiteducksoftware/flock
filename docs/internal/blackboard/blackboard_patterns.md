# Blackboard-Native Coordination Patterns

This catalog covers coordination patterns that only become practical when agents share a persistent, typed blackboard. For each pattern we outline what it is, why the blackboard is essential, how Flock supports it today, and what API ideas would close remaining gaps. When a capability depends on future work we flag it explicitly.

Legend for support status:
- **Built-in** – works today using existing APIs.
- **Partial** – possible with workarounds; native support would improve ergonomics.
- **Planned** – requires new API surface.

All examples assume `from flock.orchestrator import Flock` and artifact schemas registered with `@flock_type`.

---

## 1. Opportunistic Scheduling & Meta-Control
- **Synopsis:** Knowledge sources post tentative actions and a controller chooses the most promising one based on the evolving board, rather than following a fixed workflow.citeturn0search0
- **Why Blackboard Matters:** Every agent—including the controller—sees the same artifacts, so reprioritisation needs no bespoke messaging fabric.
- **Support:** Partial. Agents can encode priorities in artifacts, but there is no dedicated control board.
- **Flock Usage:** Publish `DispatchPlan` artifacts and let a meta-controller agent decide which downstream agent to trigger next. Consider adding `flock.control_board()` to host scheduling directives separately from domain data.

## 2. Multi-Level Hypothesis Lattice
- **Synopsis:** Blackboard systems arrange hypotheses at different abstraction levels (signals → features → decisions) and let agents climb the lattice when higher-level ideas fail.citeturn0search0
- **Why Blackboard Matters:** The board stores every intermediate layer so later agents can revisit, merge, or prune earlier work without recomputation.
- **Support:** Built-in. Artifacts already hold type, correlation, and provenance.
- **Flock Usage:**
  ```python
  frame_agent = flock.agent("frame_extractor").consumes(InputBlob).publishes(RawFrame)
  segmenter = flock.agent("segmenter").consumes(RawFrame).publishes(Segment)
  decoder = flock.agent("decoder").consumes(Segment).publishes(TranscriptHypothesis)
  reviewer = flock.agent("reviewer").consumes(TranscriptHypothesis)
  ```

## 3. Reflective Blackboard & Policy Agents
- **Synopsis:** A reflective layer monitors the domain board and posts control knowledge—policies, heuristics, thresholds—that tune the core system at runtime.citeturn4search0
- **Why Blackboard Matters:** Reflection uses the same vocabulary as domain agents, making adaptations observable and auditable.
- **Support:** Partial. Metrics and tracing exist, but there is no native API for publishing control policies back into the scheduler.
- **API Idea:** `await flock.post_policy(ExecutionPolicy(...))` paired with a `PolicyVisibility` control board so dashboards can list active runtime rules.

## 4. Expectation Watchlists
- **Synopsis:** Controllers maintain lists of “desired evidence” (expectations) that cue agents to gather missing data or hold for events.citeturn0search0
- **Why Blackboard Matters:** Expectations persist alongside regular artifacts, so any agent can satisfy or invalidate them asynchronously.
- **Support:** Partial. Model expectations as artifacts (e.g., `InfoRequest`) but there is no managed queue.
- **Flock Usage:**
  ```python
  @flock_type
  class InfoRequest(BaseModel):
      need: str
      priority: int = 0

  scout = (
      flock.agent("scout")
      .consumes(InfoRequest, where=lambda r: r.need == "platform_signature")
      .publishes(SignalSample)
  )
  ```
- **API Idea:** `await flock.expect("platform_signature", ttl=30)` could register expectations with automatic expiry.

## 5. Clock & Temporal Triggers
- **Synopsis:** Blackboard systems often use clock events (e.g., “check every 5 minutes”) to compare expected vs. actual progress.citeturn0search0
- **Why Blackboard Matters:** Temporal context is logged next to domain artifacts, enabling retrospective timing analysis.
- **Support:** Partial. Flock persists timestamps but cannot schedule future wake-ups.
- **API Idea:** `await flock.schedule_event(at="2025-10-10T14:00Z", payload=ClockTick(...))` triggering agents that consume `ClockTick`.

## 6. Goal Posting & Problem Queues
- **Synopsis:** Agents publish unsolved subproblems to a goal list that others can claim, keeping the system proactive.citeturn0search0
- **Why Blackboard Matters:** Goals are visible and prioritize-able without hard-coding ownership.
- **Support:** Partial. Publish a `Goal` artifact today; add optimistic locking to prevent duplicate work.
- **API Idea:** `goal_id = await flock.post_goal(...); await flock.claim_goal(goal_id)` to coordinate ownership.

## 7. History & Explanation Trails
- **Synopsis:** Blackboard applications maintain history lists explaining how hypotheses evolved, supporting audits and debugging.citeturn0search0
- **Why Blackboard Matters:** Explanations reference the same artifact graph; auditors can replay reasoning steps.
- **Support:** Built-in. SQLite history, tracing, and `artifact.consumptions` already expose the trail.
- **Flock Usage:**
  ```python
  artifacts, _ = await flock.store.query_artifacts(
      filters=FilterConfig(type_names=["TaskDirective"]),
      embed_meta=True,
  )
  ```
- **Enhancement:** Provide `flock.explain(artifact_id)` to generate a narrative from provenance links.

## 8. Volunteer / Market-Based Responders
- **Synopsis:** Specialized agents “volunteer” when they detect a task matching their niche, enabling loose coupling and organic scaling.citeturn5academia14
- **Why Blackboard Matters:** All bids and offers are visible, avoiding hidden side channels.
- **Support:** Built-in. Use type filters, tags, and delivery modes.
- **Flock Usage:**
  ```python
  data_hunter = (
      flock.agent("s3_curator")
      .consumes(DataInquiry, where=lambda q: "s3://" in q.scope)
      .publishes(DataFinding)
  )
  ```

## 9. Event-Driven Knowledge Invocation
- **Synopsis:** Event-based blackboard systems let knowledge sources subscribe to specific change notifications instead of polling.citeturn3search2
- **Why Blackboard Matters:** Events carry references to artifacts, keeping data and triggers in sync.
- **Support:** Partial. Flock subscriptions already fire on publish, but there is no separate event bus.
- **API Idea:** `flock.events.on("artifact_updated", filter=...)` that enqueues synthetic artifacts for downstream agents.

## 10. Sensor & Panel Fusion
- **Synopsis:** Independent sensor pipelines write to panel-specific regions and a fusion agent combines them into situational awareness.citeturn0search0
- **Why Blackboard Matters:** Panels share a schema but stay logically separated; fusion agents can draw cross-panel correlations.
- **Support:** Built-in via tags, partition keys, and visibility.
- **Flock Usage:**
  ```python
  radar_agent = flock.agent("radar_ingest").consumes(RawRadar).publishes(Track, tags={"panel:radar"})
  vision_agent = flock.agent("vision_ingest").consumes(CameraFrame).publishes(Detection, tags={"panel:vision"})
  fusion = flock.agent("fusion_center").consumes(Track, Detection).publishes(SituationalPicture)
  ```

## 11. Distributed Sub-Blackboards
- **Synopsis:** Large projects decompose into cooperating blackboards (e.g., ELINT, COMINT) that exchange summaries through a main board.citeturn0search0
- **Why Blackboard Matters:** Each subsystem operates autonomously yet publishes cross-domain artifacts when needed.
- **Support:** Partial. Use `partition_key` today; dedicated helper APIs would simplify routing and metrics.
- **API Idea:** `with flock.subboard("ELINT") as b:` to scope publish/subscribe calls automatically.

## 12. Auction or Bidding-Based Activation
- **Synopsis:** Control agents run bidding rounds where knowledge sources estimate utility vs. cost before execution.citeturn5search3
- **Why Blackboard Matters:** Bids include references to the same artifacts, making trade-offs transparent.
- **Support:** Planned. Requires a structured bidding API.
- **API Idea:**
  ```python
  async with flock.control_round(artifact) as round_ctx:
      await round_ctx.bid(agent="data_cleaner", utility=0.8, cost=3)
      await round_ctx.bid(agent="summarizer", utility=0.7, cost=1)
  winner = await round_ctx.select()
  ```

## 13. Ensemble Metaheuristic Blackboard
- **Synopsis:** Heterogeneous optimisers (GA, hill climb, LHC) share intermediate designs, each improving on the others.citeturn4search2
- **Why Blackboard Matters:** Candidate designs persist, letting each heuristic reuse promising points discovered elsewhere.
- **Support:** Built-in. Publish shared `DesignCandidate` artifacts and filter by performance thresholds.

## 14. Cooperative Hint Sharing
- **Synopsis:** Agents publish hints—partial structures, heuristics, or embeddings—that peers can adopt to accelerate their own search.citeturn5search2
- **Why Blackboard Matters:** Hints become reusable knowledge, not transient messages.
- **Support:** Built-in. Define a `Hint` artifact with `target` and `confidence` fields.

## 15. Focus-of-Attention & Budgeted Reasoning
- **Synopsis:** Control components store the current “focus” (subspace + budget) so only relevant knowledge sources activate.citeturn0search0
- **Why Blackboard Matters:** Focus state is visible and auditable; agents can relinquish or extend it cooperatively.
- **Support:** Partial. You can publish `FocusWindow` artifacts today, but the scheduler ignores budgets.
- **API Idea:** `async with flock.request_focus(topic, tokens=200): ...` would let the orchestrator enforce cost ceilings.

## 16. Hypothesis Aging & Reliability Management
- **Synopsis:** Hypotheses carry reliability values and age out when lower-confidence evidence is superseded.citeturn0search0
- **Why Blackboard Matters:** Reliability metadata lives beside payloads, so critics can retire or downgrade entries without deleting history.
- **Support:** Partial. Add fields like `status` and `expires_at` to artifacts; provide store utilities to filter active vs. retired.

## 17. Control vs. Domain Board Separation
- **Synopsis:** Some architectures separate “executive” information from domain knowledge to avoid interference and simplify control logic.citeturn5search3
- **Why Blackboard Matters:** Both boards still share the same infrastructure, enabling consistent tooling and observability.
- **Support:** Planned. Requires explicit control-board helpers and dashboard support.

## 18. Broadcast Steering Artifacts
- **Synopsis:** Broadcasting policies or “system prompts” via shared artifacts ensures every agent sees global directives without editing individual prompts.citeturn3search5
- **Why Blackboard Matters:** Steering artifacts are auditable, versioned, and persist for replay or rollback.
- **Support:** Built-in once `Flock.post_announcement()` ships (see `my_amazing_steering_implementation.md`).
- **Usage:** `await flock.post_announcement("Prefer cached data when cost estimate > $10.")`

## 19. Security-Scoped Blackboard Panels
- **Synopsis:** Secure blackboard variants enforce clearance levels or role-based access on artifacts to prevent information leaks.citeturn4search6
- **Why Blackboard Matters:** Visibility metadata lives with the artifact, letting trusted and untrusted agents share the same runtime safely.
- **Support:** Built-in. Use `Visibility` subclasses and labels to mimic clearance levels.

## 20. Open Agent Architecture Task Boards
- **Synopsis:** The Open Agent Architecture used blackboard “task structures” to manage multi-agent workflows, demonstrating goal decomposition and resumption.citeturn3search14
- **Why Blackboard Matters:** Task structures persist; agents can suspend, resume, or delegate work without hard-coded workflows.
- **Support:** Partial. Model task structures as artifacts; add helper APIs for resuming suspended work (`flock.resume_task(task_id)`).

---

## Implementation Checklist
1. Model shared concepts explicitly as artifacts (e.g., `Goal`, `Hint`, `FocusWindow`) so they inherit persistence and visibility.
2. Use `tags`, `partition_key`, and `visibility` to carve panels, sub-boards, and security domains.
3. Enable tracing (`FLOCK_AUTO_TRACE=true`) so reflective or critic agents have the telemetry needed to adapt policies.
4. Surface pattern-specific metrics in the dashboard—e.g., active expectations, focus windows, auction outcomes.

---

## References
- H. P. Nii, “Blackboard Application Systems and Knowledge Engineering Perspective,” *AI Magazine*, 1986.citeturn0search0
- National Academies Press, “Blackboard Architecture Overview,” 1988.citeturn0search1
- Confluent, “What Is the Blackboard Architectural Pattern?,” 2024.citeturn3search5
- S. Sato et al., “Fast Multi-Agent Negotiation using Blackboard Architecture,” 2023.citeturn5search3
- L. P. Kaelbling et al., “The Open Agent Architecture,” 1996.citeturn3search14
- D. Garlan et al., “Event-Based Blackboard Architecture,” 2013.citeturn3search2
- A. Salemi et al., “LLM-based Multi-Agent Blackboard System for Information Discovery in Data Science,” 2025.citeturn5academia14
- A. Yang et al., “Blackboard-Based Heuristic Ensemble,” 2017.citeturn5search2
- P. Teodorović et al., “Blackboard-Based Coordination for Metaheuristics,” GECCO Companion, 2015.citeturn4search2
- F. Li et al., “Secure Blackboard Pattern,” 2016.citeturn4search6

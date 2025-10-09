# Developer Workflow Prompt

> Use this prompt as your operating manual when working on feature #298 (SQL-backed Blackboard Store) or similar large features. Follow the steps rigidly so that planning structure, issue hierarchy, and documentation stay consistent.

---

## 1. Feature Specification
1. Create a feature spec issue from `.github/ISSUE_TEMPLATE/feature_spec.yml`.
   - Title format: `🧭 [SPEC] [<version>] <feature name>`.
   - Fill in every section (problem, scope, metrics, NFRs, dependencies, risks, timeline, validation, follow-ups).
2. Store the exact Markdown used for the issue inside `docs/internal/issues/<feature-id>/feature_spec.md`.
3. Maintain a `notes.md` scratchpad in the same directory for research, decisions, and schema sketches.

## 2. Phase Planning
1. For each major delivery slice, create a Phase Plan issue using `.github/ISSUE_TEMPLATE/phase_plan.yml`.
   - Title format: `🧱 [#<feature-id>] [PHASE] [<version>] Phase X – <name>`.
   - Use `gh sub-issue create --parent <feature>` with the phase markdown.
2. Keep the canonical phase plan Markdown in scratchpad as `docs/internal/issues/<feature-id>/<feature-id>-phase0X-<name>.md`.
   - Example: `docs/internal/issues/298/298-phase01-foundation.md`.
3. Each phase plan must include objectives, deliverables, entry/exit criteria, scope, dependencies, risks, validation strategy, timeline, communication plan, and follow-ups.

## 3. Implementation Tasks
1. For each phase, craft implementation task drafts using `.github/ISSUE_TEMPLATE/task.yml`.
   - Filename convention in scratchpad:
     `docs/internal/issues/<feature-id>/<feature-id>-<phase-id>-task0N-<topic>.md`.
   - Example: `docs/internal/issues/298/298-299-task01-schema.md`.
2. Each task draft must include:
   - Context: parent feature + phase IDs, task ID, owner
   - Problem statement
   - Scope (in/out)
   - Acceptance criteria
   - Definition of Done checklist
   - Implementation plan steps
   - Technical notes
   - Dependencies/blocks
   - Validation strategy
   - Artifacts list
   - Timeline & reviewers
   - Status update section
   - Risks & mitigations
   - Follow-ups
3. Once drafted, commit the `.md` files in scratchpad, then create sub-issue(s):
   - Command: `gh sub-issue create --parent <phase_issue> --title "[#feature] [#phase] [TASK] <name>" --label enhancement --body "$(cat path/to/task.md)"`
   - Ensure title does **not** include emoji; keep `[TASK]` indicator and IDs of feature + phase.

## 4. Branch & Commit Strategy
1. Work on a dedicated feature branch for planning, e.g., `feat/<feature-id>-sql-blackboard-store-prep`.
2. Commit series should capture:
   - Issue templates addition (if any)
   - Scratchpad updates (notes, phase plans, tasks)
   - Additional artifacts (dev workflow, ADR drafts, etc.)
3. Push branch after each logical milestone so others can follow along.

## 5. Naming & Metadata Rules
- **Issues:** Always include relevant IDs in titles. Example: Feature `[#298]`, Phase `[#298] [#299]`, Task `[#298] [#299] [TASK]`.
- **Scratchpad files:** Prefix with feature and phase IDs to keep them sorted.
- **Templates:** Never omit required fields. If something is N/A, explicitly write “N/A”.
- **Owners:** Use actual GitHub handles (e.g., `@AndreRatzenberger`).
- **Documentation:** Keep roadmap, README, docs, and internal notes synchronized with new information.

## 6. Validation & Proof of Work
- Tests: document commands run and attach logs in the task issue.
- Docs: cross-link to relevant sections (README, docs/guides, etc.).
- Examples: include output or instructions for manual verification.
- Feedback: create a discussion/issue for collecting beta feedback and attach to Phase 3 task.

## 7. After Planning
- Once planning is complete and branch pushed, raise a PR summarizing templates, scratchpad docs, and issue hierarchy.
- Tag the feature spec (#298) with all phase and task links in the body for quick navigation.
- Only start implementation once planning PR is approved or merged.

---

**Reminder**: This workflow ensures future instances of the AI coding agent (you) can step in mid-feature with full context, maintain strict structure, and avoid missing documentation. Follow it exactly, update this file if the process evolves, and keep scratchpad files committed for traceability.

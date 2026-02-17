# Tasks: Dashboard Hierarchical ELK Migration (P2)

## 1. Engine Abstraction

- [ ] 1.1 Introduce hierarchical layout engine interface
- [ ] 1.2 Move current Dagre hierarchical logic behind the interface
- [ ] 1.3 Keep current `LayoutResult` contract stable

## 2. ELK Engine

- [ ] 2.1 Add ELK dependency and engine implementation
- [ ] 2.2 Map dashboard direction/spacing options to ELK configuration
- [ ] 2.3 Normalize ELK output coordinates to React Flow node positions

## 3. Runtime Integration

- [ ] 3.1 Switch hierarchical auto-layout runtime path from Dagre to ELK
- [ ] 3.2 Keep existing auto-layout context menu behavior intact

## 4. Validation

- [ ] 4.1 Add unit tests for option mapping and layout contract compatibility
- [ ] 4.2 Add fixture tests for layout quality regression checks
- [ ] 4.3 Run manual dashboard comparisons on dense real graphs
- [ ] 4.4 Document perf and quality deltas for migration evidence

## 5. Review

- [ ] 5.1 Request Claude review before merge/push

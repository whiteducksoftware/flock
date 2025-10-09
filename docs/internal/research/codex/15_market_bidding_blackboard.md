# Market/Bidding Coordination on the Blackboard

Score: 7.2 / 10

## Abstract
We implement market‑style bidding (e.g., Contract Net Protocol‑inspired) where agents attach bids to artifacts, and the blackboard selects winners according to policies (price, quality, fairness). We compare against FIFO and round‑robin for assignment efficiency and fairness.

## Research Questions / Hypotheses
- H1: Bidding reduces contention and improves task‑agent matching quality.
- H2: Typed artifacts enable safe bidding by scoping bids and preventing unsafe cross‑domain competition.

## Experiment Sketch
- Add bidding API on publish; implement allocation policies; evaluate on heterogeneous agent pools and tasks.
- Compare welfare (utility), fairness, and makespan vs FIFO/round‑robin.

## Project Plan (3–5 weeks)
- Week 1: Bidding API + policies.
- Week 2: Benchmarks; ablations by heterogeneity.
- Week 3: Analysis + write‑up.

## Metrics
- Assignment optimality (utility), fairness metrics, makespan, and stability.

## Value Proposition
- A flexible coordination primitive well‑studied in MAS, expressed naturally via blackboard artifacts.

## Sources / Further Reading
- Contract Net Protocol (Smith, 1980). https://doi.org/10.1145/358886.358892
- Surveys of market‑based control in multi‑agent systems. https://doi.org/10.1016/S0921-8890(01)00145-2

# Reconstructed Real Instance Cross-Validation

The reconstructed `REAL_1` instance was cross-validated against the published
company-instance optimum reported by Luche, Morabito, and Pureza (2009, APJOR,
Section 4.2).

Published reference:

- Instance: company order book with `n = 159` processes
- Solver/reference: CPLEX circa 2008
- Reported solve time: 26 s
- Published optimum: 10,475 kg of shortage

Current reconstructed-instance result:

- Source JSON: `experiments/matheuristics/results_production/real/REAL_1_mip_seed1_b10800.json`
- Method: cold MIP, 10,800 s budget
- Shortage: 10,475.0
- Difference from published shortage optimum: 0.0
- Excess: 967,625.0
- Objective with inventory term: 11,442.625
- Objective formula: `Z = shortage + 0.001 * excess`

The reconstructed instance therefore preserves exactly the published optimum
shortage level. Under the present manuscript model with the excess-inventory
term (`gamma = 0.001`), the shortage component remains 10,475.0 kg and the
reported objective is 11,442.625.

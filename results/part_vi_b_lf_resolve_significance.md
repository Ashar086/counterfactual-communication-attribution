# VI.B LF Resolve@1 — significance & CIs

Table. VI.B LF-rescored Resolve@1 with 95% Wilson CIs and pairwise Fisher exact tests vs CR-guided (n=100).

| Method | Resolved/n | Rate | 95% Wilson CI | p vs CR-guided (Fisher exact) |
|---|---:|---:|---|---:|
| CR-guided | 2/100 | 0.02 | [0.006, 0.070] | — |
| Reward-only | 4/100 | 0.04 | [0.016, 0.098] | 0.6827 |
| Random | 3/100 | 0.03 | [0.010, 0.085] | 1 |
| Static | 3/100 | 0.03 | [0.010, 0.085] | 1 |

Overall (4×2) asymptotic χ² p = 0.8762 (df=3); Monte Carlo exact-style p = 0.9776 (200,000 reps). Prefer MC given sparse cells.

Clopper–Pearson 95% CIs (supplement):
- CR-guided: [0.002, 0.070]
- Reward-only: [0.011, 0.099]
- Random: [0.006, 0.085]
- Static: [0.006, 0.085]

## Pairwise Fisher exact detail

- **CR-guided vs Reward-only**: OR=0.4897959183673469, p=0.682717, table=[[2, 98], [4, 96]]
- **CR-guided vs Random**: OR=0.6598639455782312, p=1, table=[[2, 98], [3, 97]]
- **CR-guided vs Static**: OR=0.6598639455782312, p=1, table=[[2, 98], [3, 97]]

## Overall test

- χ² (asymptotic) = 0.6873, df=3, p=0.87619
- Monte Carlo p = 0.977595 (reps=200000)
- Note: Asymptotic chi-square may be unreliable: several expected cell counts < 5. Prefer Monte Carlo p-value for the overall test.

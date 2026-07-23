---
name: clinical-survival
description: Survival analysis — Kaplan-Meier curves, log-rank test, Cox proportional-hazards regression for time-to-event clinical outcomes (overall survival, progression-free survival, any censored endpoint). Use when the user has survival data (time, event) and asks to test survival differences, stratify by a biomarker, compute hazard ratios, or generate KM plots.
requiredTools: [run_python, bash, read, write, observe_figure]
tags: [clinical, survival, kaplan-meier, log-rank, cox-ph, hazard-ratio, censoring, time-to-event]
---

# Clinical Survival Analysis — KM, Log-Rank, Cox PH

Survival analysis: Kaplan-Meier estimator for survival curves, log-rank test for group comparison, Cox proportional-hazards regression for hazard ratios and multivariable adjustment. Builds on `omics-shared` (loaded automatically — its evidence/grounding rules apply).

This is **NOT** competing-risks analysis, **NOT** recurrent-event models, **NOT** cure models.

---

## Prerequisites

1. **Data format**: time-to-event table with `time` (numeric, follow-up duration) and `event` (binary: 1=event, 0=censored)
2. **Context**: grouping variable (treatment, biomarker high/low) or continuous covariates (age, expression) for stratification/adjustment
3. **Library**: `lifelines` (standard Python survival package) — **not in `task1–4`; provision it first**

Build the env **beside your analysis outputs** — not in the package, whose manifest is a
checksum-verified artifact the host may delete and re-fetch (`omics-shared`'s
`assets/references/AOSE_nonStandard_env.md` carries the routing and the hard rules):

```toml
# pixi.toml, at your analysis root
[workspace]
name = "survival"
channels = ["conda-forge"]
platforms = ["linux-64"]

[dependencies]
lifelines = "*"
scanpy = "*"      # only if you also read .h5ad here; it brings pandas/numpy/scipy/matplotlib
```

```bash
pixi lock && pixi install --locked
pixi run --frozen python survival.py
```

Never a bare `pip install lifelines` — it resolves against whatever `python` leads `$PATH`,
frequently conda `base`.

---

## Capability Menu

| Capability | Maturity | Tool/Method | Reference Doc |
|------------|----------|-------------|---------------|
| Kaplan-Meier survival curves | **PARTIAL** | lifelines.KaplanMeierFitter — not pinned | `assets/references/km_logrank.md` |
| Log-rank test (two-group comparison) | **PARTIAL** | lifelines.statistics.logrank_test — not pinned | `assets/references/km_logrank.md` |
| Cox proportional-hazards regression | **PARTIAL** | lifelines.CoxPHFitter — not pinned | `assets/references/cox_ph.md` |
| PH assumption check (Schoenfeld residuals) | **PARTIAL** | CoxPHFitter.check_assumptions — not pinned | `assets/references/cox_ph.md` |
| Hazard ratio + 95% CI | **PARTIAL** | Cox model summary — not pinned | `assets/references/cox_ph.md` |

Everything here is **PARTIAL** for one reason only: `lifelines` is in no pinned env, so provision it
before planning a run (above). The *methods* are unambiguous — what still needs study-specific judgment
is censoring interpretation, PH-violation handling, covariate selection, and stratification cutoffs.
`omics_preflight` only validates `task1–4`, so check the import yourself and record the env + version
in the `report`.

Other skills route survival work here — `microbiome`'s per-taxon Cox capability points at
`cox_ph.md` — and they already label it PARTIAL. If a workflow needs both this and a pinned method,
provision **one** env composing the pinned stack plus `lifelines` and run the whole thing there rather
than splitting it across two interpreters.

---

## Standard Workflow

Each step names the decisions it forces and the traps that do not announce themselves. **The runnable
recipe lives in the reference doc** — read it before writing the step. All of it needs the provisioned
`survival` env (Prerequisites).

A **landmark / fixed-horizon question** (one asking about survival, or an outcome, at a specific time
point) is still a survival question: stratify the biomarker (median split, or a stated cut) and run
KM + log-rank — and Cox for adjustment — on the **full** time-to-event data as the **primary** analysis.
Do **not** reduce it to a binary outcome at the horizon and a rank test; that discards censoring and the
shape of the curve, and its p-values will not match the log-rank result the endpoint implies.

### 1. Kaplan-Meier curves

Per-group survival curves, with a risk table.

- **Censoring is data, not missingness.** `event=0` means "alive at last follow-up", and dropping
  those rows is the classic way to manufacture a survival difference
- Report median survival **with its CI** — an un-reached median (curve never crosses 0.5) is `inf`,
  which is a real answer, not a failure
- Always show numbers-at-risk; a separation driven by three patients in the tail is not a finding

### 2. Log-rank test

Compare two curves.

- Log-rank tests the **whole curve**, not survival at one timepoint
- It assumes **proportional hazards**. Crossing curves violate it and the test loses power exactly
  where the biology is most interesting — look at the KM plot before trusting the p-value

→ `assets/references/km_logrank.md`

### 3. Cox proportional-hazards regression

Multivariable HR with covariate adjustment.

- **Check the PH assumption** (`check_assumptions`, Schoenfeld residuals). A violated PH makes the HR
  a weighted average over follow-up time — a number that describes no actual period
- Covariate selection is a **design decision**, not a search: pre-specify it
- Report **HR + 95% CI**, not just p. An HR of 1.02 with p<0.001 in a large cohort is not clinically
  interesting, and the CI is what shows that

→ `assets/references/cox_ph.md`

---

## Survival Best Practice (on top of omics-shared)

### 1. Right-censoring convention

`event=1` → event occurred (death, progression). `event=0` → censored (lost to follow-up, study end). Always check the coding — some datasets use opposite convention.

### 2. Time units

State the time unit (days, months, years) explicitly. Median survival = 12 (months? years?) is ambiguous.

### 3. Median survival with CI

Report median survival (the time at which survival = 50%) **with its 95% CI, in time units**.

The CI must come from `median_survival_times`, which inverts the confidence band to get time bounds.
`confidence_interval_survival_function_` looks like the same thing and returns **survival
probabilities** instead — they sit near 0.5 for any dataset, so "median 19.2 months, 95% CI
[0.42, 0.57]" is nonsense in the wrong units that never raises. See `assets/references/km_logrank.md`.

### 4. Hazard ratio interpretation

HR > 1 → increased hazard (worse outcome). HR < 1 → protective. Always report the 95% CI — a wide CI (e.g., [0.8, 3.2]) spans 1.0 and is not significant.

### 5. PH assumption check

Cox PH requires proportional hazards (group hazard ratio constant over time). Check with Schoenfeld residuals. If violated, use stratification or time-varying coefficients.

### 6. "Favorable *despite* lacking X" → benchmark against the group that HAS X

When a question frames a subgroup's outcome as favorable **despite** its lacking a feature, the implied
reference is the group that **has** the feature. Build the comparison explicitly: include the
has-feature group as a distinct arm in the KM + log-rank, and fit a Cox model with the
**has-feature group as the reference level**; then pre-specify an explicit **equivalence-style**
criterion for "comparable to the reference" and state it before looking. "As good as those who have X"
is a between-group claim — a within-subgroup median split alone does not test it.

### 7. One measurement scale per feature

When a biomarker/feature is reported on multiple measurement scales (e.g. percent-of-parent vs
percent-of-leukocytes in flow cytometry, or raw vs normalized units), pick **one** scale consistent with
the question and **never mix scales** within a single feature set — mixing pulls in duplicate or
incomparable features, changing both the feature list and the cohort that survives filtering.

---

## Pitfalls

- **Event coding reversed** — treating censored as events
- **No PH check** — Cox model invalid if PH violated
- **HR without CI** — HR=2.1 with CI=[0.9, 4.8] crosses 1.0 (not significant)
- **Median survival not reported** — log-rank p-value alone doesn't quantify the effect
- **Time units not stated** — "median=12" is ambiguous
- **Left-truncation ignored** — delayed entry (e.g., all patients recruited after year 1) biases KM

---

## Evidence & Reporting

Every analysis emits:
- **Data**: n patients, n events, median follow-up
- **KM**: median survival per group with 95% CI, survival at landmark times (1yr, 5yr)
- **Log-rank**: test statistic + p-value
- **Cox**: HR + 95% CI + p per covariate, PH assumption check result
- **Figures** → inspect the figure

See reference docs for per-analysis reporting templates.

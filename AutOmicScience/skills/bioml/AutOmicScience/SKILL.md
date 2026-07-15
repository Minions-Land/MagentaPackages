---
name: bioml
description: Bioinformatics machine-learning engineering — reproduce published DL methods (single-cell foundation models, sequence models, spatial GNNs), fetch code/weights from GitHub & Hugging Face, run and adapt paper repos to exact output files, and apply ML-engineering discipline (bounded repair, honest error paths, reproducible snapshots, publication-grade figures). Use when a task requires training or reproducing a machine-learning model on omics data rather than a standard scanpy/tabular analysis.
requiredTools: [run_python, bash, read, write, WebFetch, observe_figure, omics_preflight, omics_compute]
tags: [bioml, machine-learning, deep-learning, reproduction, scvi-tools, huggingface, github, model-training]
---

# BioML — Bioinformatics Machine-Learning Engineering

BioML covers the tasks where the deliverable is a **trained or reproduced machine-learning model** on biological data — not a standard analytical write-up. Think: reproduce SATURN / scPoli / scVI / a sequence foundation model / a spatial GNN to a tight objective metric, or build a competitive DL baseline on omics data. Builds on `omics-shared` (loaded automatically — don't restate its rules). This parent gives the ML-engineering mental model and routes to subskills.

## The Core Insight (read this first)

For most BioML reproduction tasks, **the winning move is not to reinvent the method**. In priority order:

1. **Run the paper's public repo.** Clone the GitHub repo, install its environment, adapt its I/O to the required output file/shape. → `repro/SKILL.md`
2. **Use a mature simpler method that already matches or beats the target.** A well-tuned `scVI` + KMeans, `scANVI`, or a task-specific CNN often equals or beats a bespoke model at a fraction of the effort. → `deep-models/SKILL.md`
3. **Exploit escape hatches.** Sometimes a strong baseline beats the "SOTA" method on the exact metric being scored. Always check whether a simpler path clears the bar before committing to a heavy pipeline.

Only reimplement from scratch when no repo runs and no simpler method fits. The #1 capability here is **ML-engineering: get the paper's code running, get its weights, adapt the outputs** — the domain method is secondary.

## Routing: Which Subskill?

| You need to… | Subskill | What it covers |
|--------------|----------|----------------|
| **Reproduce a published method** — clone a repo, fetch model weights/datasets, run and adapt it | `repro/SKILL.md` | GitHub fetch, Hugging Face fetch (with mirror emphasis), running paper repos, escape-hatch awareness |
| **Build/train a single-cell deep model** — scVI, scANVI, scArches, scPoli, scGPT, contrastiveVI, SATURN | `deep-models/SKILL.md` | scvi-tools / scArches / foundation-model recipes, reference mapping, label transfer, integration |
| **Build/apply a DNA/RNA/protein sequence model** — NT, DNABERT, HyenaDNA, Borzoi, RNA-FM, ESM-2, GPN | `sequence-fm/SKILL.md` | Sequence foundation models, tokenization, finetune vs zero-shot, FASTA loaders, CNN escape hatches |
| **Build/train a graph or geometric model** — GNN node classification on biological networks, spatial graph-autoencoders, 3D-structure/mesh geometric GNNs | `graph-dl/SKILL.md` | PyTorch Geometric: graph construction, transductive node classification (+ hetero / imbalance), graph autoencoders (STAGATE-family spatial domains), geometric/equivariant models (SchNet/DimeNet/point/ViSNet, e3nn) |
| **Write and verify ML code** — plan, implement, repair a failing check, test, package a reproducible snapshot | `coding/SKILL.md` | coding methodology (plan → implement → simplify → test), bounded repair loop, silent-failure & type audits, reproducible code snapshot |
| **Produce or audit publication figures** — matplotlib discipline, vector-font compliance, layout audit | `figure-check/SKILL.md` | academic-plotting rcParams/Type-42 gate, chart-type selection, pixel-level layout audit |

The subskills are chapters of this skill and cannot be invoked independently. Read the one that matches your current step.

## BioML foundations (details in `omics-shared` + the subskill)

- **Confirm compute before training** — GPU (`nvidia-smi`), CUDA/torch versions, RAM/disk. Many BioML tasks are bound by data size + wall-clock, not GPU FLOPs. Stream multi-GB data (read shapes first, load lazily); sanity-check on a subset / few epochs before scaling. Prefer the pinned envs via `omics_compute`; build a fresh env only when the paper repo demands it.
- **Reproduce to an EXACT output contract** — read the required file name / format / array shape / dtype and the exact metric (ARI, Pearson, MCC, cosine, silhouette…) first; a model that trains perfectly but writes the wrong shape scores zero. Know the baseline you target.
- **Honest ML, no faked success** — every reported number comes from a real run against real data; surface failures (diverged run, repo that won't install, OOM) as blockers, don't paper over them.
- **Fetch discipline (code & weights)** — GitHub via `gh` / `raw.githubusercontent.com`; Hugging Face via mirror endpoints + `GIT_LFS_SKIP_SMUDGE=1`; always record source repo + commit SHA, where bytes landed, and the **license**. Recipes in `repro/`. (Evidence/grounding rules: `omics-shared`; figure inspection: `figure-check/`.)

## Next Steps

Identify your current step and read the matching subskill. A typical reproduction flows: `repro/` (get code+weights running) → `deep-models/` (single-cell model) or `graph-dl/` (GNN / geometric model) → `coding/` (implement/repair/test the glue + package it) → `figure-check/` (if the deliverable includes figures).

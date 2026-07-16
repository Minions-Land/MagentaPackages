---
name: bioml-sequence-fm
disable-model-invocation: true
---

# BioML Sequence Foundation Models — DNA/RNA/Protein Transformers

> Subskill of `bioml`. Enter here from the parent skill when you need to train or apply a DNA, RNA, or protein sequence foundation model. Read the parent (`../SKILL.md`) and the always-loaded `omics-shared` skill first — their ML-engineering foundations and evidence rules apply here.

This subskill covers **sequence-based foundation models**: Nucleotide Transformer, DNABERT, HyenaDNA, Borzoi (DNA); RNA-FM (RNA); ESM-2, GPN (protein). These are orthogonal to `deep-models` (single-cell scVI/scGPT on count matrices); here the input is FASTA/raw sequences and the task is sequence classification, per-base prediction, or embedding.

---

## When to Use Sequence FMs

Use this path when:
- The task is **DNA regulatory prediction** (enhancer activity, chromatin state, splicing)
- The task is **RNA structure/function** from sequence alone (no expression matrix)
- The task is **protein function/structure** from AA sequence
- The deliverable is an **exact output file** (logits, embeddings, per-base scores) in a required output format

**Escape hatch:** If the task has a lighter baseline (CNN, GRU, k-mer features + logistic regression), **try that first**. NatureBench documented cases where DeepSTARR CNN beat Nucleotide Transformer on one task. Foundation models justify their cost for transfer/few-shot or when simpler methods provably fall short.

---

## Model Menu

**Everything here is PARTIAL.** `torch` is pinned, but **`transformers` is in no pinned env** — every
snippet below fails at the import until you provision it. Repo-based models (HyenaDNA, Borzoi, RNA-FM,
GPN) additionally need their own clone + requirements.

```toml
# pixi.toml, at your analysis root — use a named conda env instead if a CUDA build must be pinned
[workspace]
name = "seqfm"
channels = ["conda-forge"]
platforms = ["linux-64"]

[dependencies]
pytorch = "*"

[pypi-dependencies]
transformers = "*"
datasets = "*"
```

```bash
pixi lock && pixi install --locked
pixi run --frozen python -c "import transformers"
```

Never a bare `pip install transformers` — it resolves against whatever `python` leads `$PATH` (often
conda `base`) and drags its own `torch` pin. Full protocol: `omics-shared`'s
`assets/references/AOSE_nonStandard_env.md`. `omics_preflight` covers only `task1–4`, so verify the
import yourself and record the env + versions in the `report`.

| Model | Maturity | Modality | Use case | Package/Repo | Compute |
|-------|----------|----------|----------|--------------|---------|
| **Nucleotide Transformer (NT)** | **PARTIAL** — `transformers` | DNA | Regulatory prediction, genomic regions | HF `InstaDeepAI/nucleotide-transformer-*` | GPU (hours) |
| **DNABERT** | **PARTIAL** — `transformers` | DNA | Promoter/enhancer classification | HF `zhihan1996/DNABERT-*` | GPU (hours) |
| **ESM-2** | **PARTIAL** — `transformers` | Protein | Protein function/structure | HF `facebook/esm2_*` | GPU (hours) |
| **HyenaDNA** | **PARTIAL** — repo install | DNA | Long-context DNA (1M bp) | Repo `HazyResearch/hyena-dna` | GPU (hours), large memory |
| **Borzoi** | **PARTIAL** — repo install | DNA | Per-base epigenome prediction | Repo `calico/borzoi` | GPU (hours–days) |
| **RNA-FM** | **PARTIAL** — repo install | RNA | RNA structure/function | Repo `ml4bio/RNA-FM` | GPU (hours) |
| **GPN** | **PARTIAL** — repo install | Protein/genomic | Genomic PTM/variant effect | Repo (GPN) | GPU (hours) |

**First try:** If a lightweight baseline (CNN, k-mer BOW) exists in the literature for the same task, run that first. FMs escalate when the baseline misses the target metric.

---

## Task-Specific Reference Docs

| Task | Reference doc |
|------|---------------|
| DNA regulatory (enhancer, promoter, chromatin) | `assets/references/dna_fm.md` |
| RNA structure/function prediction | `assets/references/rna_fm.md` |
| Protein function/structure | `assets/references/protein_fm.md` |

---

## Common Workflow (DNA FM example)

Each step names the decisions it forces and the traps that do not announce themselves. **The runnable
recipe lives in the reference doc** — read it before writing the step. `transformers` is **not
pinned**; provision it first (Model Menu).

### 1. Tokenize

Use the model's **paired** tokenizer — always `from_pretrained` on the same checkpoint id.

- A mismatched tokenizer (DNABERT's on NT) **degrades results silently**; nothing raises
- Max length is a property of the checkpoint, not a preference. NT is ~6 kb (1000 tokens × 6 nt).
  Beyond it, window — or pick a long-context model

### 2. Load the pretrained model

- The published checkpoints are **masked-LMs**. `AutoModelForSequenceClassification` keeps the encoder
  and creates a **randomly initialised** classifier head; transformers warns, and the warning is
  correct. Never report zero-shot numbers from that object — until you train it, the head is noise

### 3. Finetune

- **Finetune** when you have labels (100s+); **zero-shot embed + kNN/logistic** when you have few or
  none. Finetuning wins whenever data exists
- Hold out a real validation set — an FM overfits a small labelled set effortlessly

### 4. Output contract

Verify shape *and* semantics against what was asked (logits vs probabilities vs per-base scores).
`(n, 3)` where `(n, 2)` was wanted is the cheap failure; the right shape with the wrong axis order is
the expensive one.

### 5. DNA-specific

**Average forward + reverse-complement predictions.** DNA is double-stranded; a model scoring only one
strand is answering a question the biology does not ask.

→ `assets/references/dna_fm.md` · `assets/references/rna_fm.md` · `assets/references/protein_fm.md`

---

## Sequence-FM Best Practice (on top of bioml/omics-shared)

### 1. Tokenization must match the model

Each FM has a specific tokenizer (k-mer size, special tokens). Using the wrong tokenizer silently degrades results. Always use the model's paired tokenizer.

### 2. Sequence length limits

Transformers have max-length limits (512–4096 tokens typical). For longer sequences, use windowing or a long-context model (HyenaDNA 1M bp).

### 3. Escape-hatch baseline first

Run the simpler method first (documented in the task's baseline). If it clears the bar, the FM is unnecessary. If not, escalate.

### 4. Output shape verification

The expected output has an exact shape (e.g., `(n_samples, n_classes)` logits). Verify `.shape` before submitting.

### 5. Finetune vs zero-shot

- **Finetune**: when you have labeled data (100s+ examples)
- **Zero-shot embedding**: when you have no labels, or very few (embed + kNN/logistic)

Finetune is almost always better if data exists.

---

## Pitfalls

- **Wrong tokenizer** — using DNABERT tokenizer on NT model (silent failure)
- **Sequence length overflow** — truncating without windowing loses context
- **Output shape mismatch** — the expected output is (n, 3), you return (n, 2)
- **Jumping to FM without baseline** — wastes GPU when a CNN would clear the bar
- **No validation on a holdout** — finetune overfits without proper eval
- **Reverse-complement not considered** — DNA is double-stranded; average fwd + revcomp predictions

---

## Evidence & Reporting

Every FM run emits:
- Model name + version (commit SHA for repos, HF model ID for HuggingFace)
- Tokenizer + max_length
- Hyperparams: learning rate, batch size, epochs, warmup
- Output shape + path
- Evaluation metrics (MCC, Pearson, AUPR, F1) on validation set
- Baseline comparison (and why the FM was chosen over the simpler path)

This is your audit trail.

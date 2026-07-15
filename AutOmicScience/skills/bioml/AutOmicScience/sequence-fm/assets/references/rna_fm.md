# Reference — RNA Foundation Models

**Maturity: PARTIAL** — `rna-fm` is **not in any pinned environment** (`task1–4`), so this method must be provisioned before it can run. Follow `omics-shared`'s `assets/references/AOSE_nonStandard_env.md`: §A a new Pixi feature + environment with its **own solve-group** (preferred — lands in `pixi.lock`), or §B a **named** conda env if Pixi can't solve it. Never a bare `pip install` (it can land in `base`), and never add these pins to `task1–4`. `omics_preflight` does not cover non-standard envs — check the import yourself, and record the env + versions in the `report`. If it can be neither imported nor provisioned, that is a **blocker**, not a cue to substitute a weaker method.

RNA-FM / RNAErnie for ncRNA classification and RNA secondary-structure prediction.

## RNA-FM (classification)
Pretrained RNA language model. For ncRNA family classification (macro-F1 contract):
```python
import fm  # RNA-FM package
model, alphabet = fm.pretrained.rna_fm_t12()
batch_converter = alphabet.get_batch_converter()
# Extract embeddings, then finetune a classification head
```

## RNA secondary structure
Predict base-pairing (contact map). Deep head on RNA-FM embeddings, or off-the-shelf UFold/MXfold2.

### .bpseq output format (1-indexed pairing table)
```python
# Each line: position, base, paired_position (0 if unpaired)
with open(f"{name}.bpseq", "w") as f:
    for i, (base, pair) in enumerate(zip(sequence, pairings), start=1):
        f.write(f"{i} {base} {pair}\n")   # pair = 1-indexed partner or 0
```
Scored by base-pair F1 (predicted pairs vs true pairs).

## Escape hatch: UFold / MXfold2
For the structure task, off-the-shelf UFold (0.81–0.85 F1) is a strong baseline before training a custom head. Run it first.

## Output contracts
- Classification: `predictions.csv` (ncRNA class) → macro-F1
- Structure: `{name}.bpseq` per sequence (1-indexed) → base-pair F1

## Pitfalls
- .bpseq 0-indexed instead of 1-indexed
- Symmetric pairing not enforced (i pairs j ⟹ j pairs i)
- Pseudoknots (RNA-FM/UFold may not predict them)
- Sequence length limits

## Grounding
`report`: model + version, task (classification/structure), output format verified, macro-F1 or base-pair-F1 on validation, baseline (UFold) comparison for structure.

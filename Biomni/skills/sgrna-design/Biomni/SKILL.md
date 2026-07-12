---
name: sgrna-design
description: >
  CRISPR sgRNA design workflow using pre-computed ranked human and mouse libraries,
  external design resources, and de novo design tools. Use this skill when designing
  guide RNAs for CRISPR knockout experiments, evaluating sgRNA candidates, or planning
  genome editing experiments.
tags:
- CRISPR
- sgRNA
- gene-editing
- Cas9
- Cas12a
source: Biomni
license: CC-BY-4.0
---

# sgRNA Design Skill

Comprehensive workflow for CRISPR sgRNA design using pre-computed libraries and computational tools.

## When to Use This Skill

Use this skill when you need to:
- Design guide RNAs for CRISPR knockout experiments
- Find ranked sgRNA candidates from pre-computed libraries
- Compare different sgRNA design approaches
- Plan CRISPR-Cas9 or Cas12a genome editing experiments

## Three-Tier Design Strategy

Always start with Tier 1 and proceed to subsequent tiers only if needed.

### Tier 1: Pre-computed Ranked sgRNAs (Recommended First)

**Approach**: Search Biomni's pre-computed human or mouse knockout library.

**When to use**:
- Target species is human or mouse
- Need ranked candidates quickly
- The target gene is covered by the downloaded library

**Methods**:
1. **Use the bundled Biomni tool**:
   - See [assets/references/design_knockout_sgrna.md](assets/references/design_knockout_sgrna.md)
   - Searches the files distributed through Biomni's release data lake

2. **Check external experimental resources separately when validation evidence is needed**:
   - Visit: https://www.addgene.org/crispr/reference/grna-sequence/
   - Confirm the guide, publication, organism, and experimental context independently

The bundled library does not itself establish Addgene provenance or experimental
validation for every returned guide.

### Tier 2: CRISPick Computational Designs

**Approach**: Use Broad Institute's CRISPick predictions

**When to use**:
- No suitable pre-computed sgRNAs are available
- Need multiple sgRNA options
- Want predicted efficacy scores

**Method**:
1. Visit: https://portals.broadinstitute.org/gppx/crispick/public
2. Enter gene symbol, species, CRISPR system
3. Review predictions:
   - On-target score (efficacy)
   - Off-target score (specificity)
   - Pick rank (combined)

**Citations**:
- Cas9: Sanson KR, et al. Nat Commun. 2018;9(1):5416. PMID: 30575746
- Cas12a: DeWeirdt PC, et al. Nat Biotechnol. 2021;39(1):94-104. PMID: 32661438

### Tier 3: De Novo Design Tools

**Approach**: Use alternative design algorithms

**When to use**:
- Gene not in CRISPick database
- Need custom PAM sequences
- Want alternative predictions

**Tools**:
- CHOPCHOP: https://chopchop.cbu.uib.no/
- Benchling: https://www.benchling.com/crispr
- CCTop: https://crispr.cos.uni-heidelberg.de/

See [assets/references/crispr_editing.md](assets/references/crispr_editing.md) for CRISPR editing simulation

## Key Design Principles

### Target Selection
- **Location**: Exons near 5' end for knockout
- **PAM sequence**: NGG for SpCas9, TTTV for Cas12a
- **GC content**: 40-60% optimal
- **Avoid**: Poly-T tracts (4+ Ts), repetitive sequences

### Specificity
- **Off-targets**: < 3 mismatches to other genomic sites
- **Seed region**: Critical (12 bp adjacent to PAM)
- **Check**: Whole genome alignment

### Efficiency
- **Activity scores**: Use CRISPick or Azimuth predictions
- **Validation**: Test 3-4 sgRNAs per target
- **Controls**: Non-targeting sgRNA, validated positive control

## Experimental Validation

### Essential Tests
1. **Editing efficiency**: T7E1 or Sanger sequencing
2. **Off-target effects**: Deep sequencing of predicted sites
3. **Functional validation**: Western blot for knockout

### Recommended Controls
- Non-targeting sgRNA (scrambled)
- Positive control (known effective sgRNA)
- Mock transfection

## Common CRISPR Systems

| System | PAM | Length | Notes |
|--------|-----|--------|-------|
| SpCas9 | NGG | 20 bp | Most common, extensive data |
| SaCas9 | NNGRRT | 21 bp | Smaller, AAV compatible |
| AsCas12a | TTTV | 23 bp | T-rich PAM, 5' overhang |
| enAsCas12a | TTTV | 23 bp | Enhanced vs AsCas12a |

## Workflow Example

```
1. Search Tier 1 (pre-computed library)
   ↓ (if not found)
2. Try Tier 2 (CRISPick)
   ↓ (if needed)
3. Use Tier 3 (De novo)
   ↓
4. Select 3-4 top candidates
   ↓
5. Check off-targets
   ↓
6. Experimental validation
```

## Available Tools

This skill includes executable tools for automated design:

### Tool 1: design_knockout_sgrna
Search pre-computed, ranked human or mouse sgRNA libraries

**Reference**: [assets/references/design_knockout_sgrna.md](assets/references/design_knockout_sgrna.md)

### Tool 2: perform_crispr_cas9_genome_editing
Simulate CRISPR-Cas9 genome editing process

**Reference**: [assets/references/crispr_editing.md](assets/references/crispr_editing.md)

## Data Requirements

The sgRNA libraries are not bundled with this skill. From the MagentaPackages
repository root, download them to an external directory and configure that path:

```bash
python Biomni/scripts/fetch_biomni_data.py \
  --dest /absolute/path/to/biomni-data \
  --skill sgrna-design
export BIOMNI_DATA_LAKE=/absolute/path/to/biomni-data
```

`design_knockout_sgrna` uses an explicit `data_lake_path` when supplied;
otherwise it reads `BIOMNI_DATA_LAKE`.

## Troubleshooting

**Low editing efficiency**:
- Try different sgRNAs
- Optimize transfection
- Check Cas protein expression
- Verify PAM sequence

**High off-targets**:
- Use higher specificity sgRNAs
- Try Cas9 variants (HiFi, eSpCas9)
- Reduce Cas9 concentration
- Shorten exposure time

## Resources

**Databases**:
- Addgene: https://www.addgene.org/crispr/
- CRISPick: https://portals.broadinstitute.org/gppx/crispick/
- Biomni release data lake: pre-computed human and mouse knockout libraries

**Design Tools**:
- CHOPCHOP: https://chopchop.cbu.uib.no/
- Benchling: https://www.benchling.com/crispr
- CCTop: https://crispr.cos.uni-heidelberg.de/

**Guidelines**:
- Broad GPP: https://portals.broadinstitute.org/gpp/public/
- Addgene protocols: https://www.addgene.org/protocols/

## Citation

If using Biomni tools:
- Cite: Biomni bioRxiv 2025.05.30.656746v1
- Cite any external guide source or experimental publication actually used
- License: CC BY 4.0

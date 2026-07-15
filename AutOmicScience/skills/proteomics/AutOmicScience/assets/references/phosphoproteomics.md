# Reference — Phosphoproteomics (Site-Specific & Activating Sites)

**Maturity: REFERENCE** — no compute subcommand; hand-rolled in a Python script. Kinase activity is
the exception: `decoupler` is pinned in `task1`, so only the network (`pip install omnipath`) is an
install.

Phosphoproteomics measures phosphorylation site occupancy — not total protein abundance. Critical: ActivatingSite filtering and site nomenclature.

## Data structure

Phosphoproteomics tables have **site-level rows**, not gene-level:

| Protein | Site | Position | Phospho_abundance | Total_protein_abundance |
|---------|------|----------|-------------------|-------------------------|
| TP53    | S15  | 15       | 2.1               | 1.3                     |
| TP53    | S20  | 20       | 1.8               | 1.3                     |

Or a site identifier like `TP53_S15` (protein_site).

## Site nomenclature

- `S` = serine, `T` = threonine, `Y` = tyrosine (phosphorylatable)
- Position is AA number in the canonical UniProt isoform
- Example: `TP53_S15` = TP53 serine 15

## ActivatingSite filtering

Only a small subset of phosphosites are **activating** (enhance kinase/protein activity). Most are
neutral or regulatory. The annotation lives in PhosphoSitePlus's **`Regulatory_sites`** table — *not*
in `Kinase_Substrate_Dataset`, which carries the kinase→site edges but no `ON_FUNCTION` column. You
need both tables for different jobs:

| PSP table | Gives | Use for |
|---|---|---|
| `Regulatory_sites` | `GENE`, `MOD_RSD` (e.g. `S15-p`), `ON_FUNCTION` (e.g. "activity, induced") | this filter |
| `Kinase_Substrate_Dataset` | `GENE` (kinase), `SUB_GENE`, `SUB_MOD_RSD` | kinase→site edges (§ below) |

```python
reg = pd.read_csv("Regulatory_sites.gz", sep="\t", skiprows=3)     # PSP ships 3 header lines
reg = reg[reg.ORGANISM == "human"]
act = reg[reg.ON_FUNCTION.fillna("").str.contains("activity, induced")]

# MOD_RSD is "S15-p" -> build the same site id your matrix uses ("TP53_S15")
act_ids = set(act.GENE.astype(str) + "_" + act.MOD_RSD.str.split("-").str[0])
phospho_act = phospho[phospho.site_id.isin(act_ids)]
```

**Why it matters:** without the filter, DE phosphoproteomics returns hundreds of neutral sites and
the "which pathways are activated?" question stays unanswered.

**PhosphoSitePlus needs a manual download and a licence** (free for academic use, but no API key
flow — you fetch the `.gz` from phosphosite.org yourself). If you cannot get it, use the kinase
activity route below instead: it needs no PSP download and answers the same biological question with
a network you can fetch programmatically.

## Phosphosite occupancy

Normalized phospho = phospho abundance / total protein abundance (to control for protein-level changes):

```python
# Both matrices on the log2 scale (the usual MS output) — occupancy is then a difference:
phospho["log2_occupancy"] = phospho.log_phospho - phospho.log_total
# From raw intensities instead, log the ratio; do not test the raw ratio:
phospho["log2_occupancy"] = np.log2(phospho.phospho_abundance / phospho.total_protein_abundance)
```

A site with high phospho_abundance but also high total_protein may not be specifically phosphorylated — the protein is just abundant. Occupancy corrects for this.

**Test on the log scale.** A raw phospho/total ratio is bounded below by 0 and right-skewed, so a
t-test on it is testing the wrong distribution and its "mean ratio" is not the ratio of means. Work
in log2 throughout, where the t-test is on a difference and `log2FC` is just a difference of means.

## Differential phosphorylation

```python
from scipy.stats import ttest_ind
from statsmodels.stats.multitest import multipletests

results = []
for site in phospho.site_id.unique():
    case = phospho[(phospho.site_id == site) & (phospho.group == "case")].log2_occupancy
    ctrl = phospho[(phospho.site_id == site) & (phospho.group == "ctrl")].log2_occupancy
    if len(case) < 2 or len(ctrl) < 2:
        continue
    stat, p = ttest_ind(case, ctrl)
    log2fc = case.mean() - ctrl.mean()          # already log2: a difference, not log2(mean/mean)
    results.append({"site": site, "log2FC": log2fc, "p": p})
de = pd.DataFrame(results)
de["padj"] = multipletests(de.p, method="fdr_bh")[1]
```

## Integration with dependency

Task: proteins upregulated in phospho AND dependency-flagged → driver candidates:

```python
# Phospho: activating-site upregulated (log2FC > 1, padj < 0.05)
phospho_up = set(de_phospho[(de_phospho.padj < 0.05) & (de_phospho.log2FC > 1)].gene)

# Dependency: gene-effect < -0.5 in relevant cancer
dep_genes = set(depmap[depmap.gene_effect < -0.5].gene)

# Overlap
candidates = phospho_up & dep_genes
```

Report the overlap with exact counts.

## Kinase activity inference (the upstream context)

A site-level DE table says *which sites moved*; it does not say *which kinase is driving them*. Score
kinase activity by aggregating each kinase's substrate sites — the same enrichment machinery the
scRNA skill uses for TF activity, with a kinase-substrate network instead of a regulon.

`decoupler` is **already in the pinned `task1` env**; the network comes from OmniPath
(`pip install omnipath`, fetched over the network at runtime):

```python
import omnipath as op
import decoupler as dc
import pandas as pd

enzsub = op.requests.Enzsub.get(organisms="human", genesymbols=True)
ks = enzsub[enzsub.modification == "phosphorylation"].copy()

# residue_type / modification come back as pandas *categoricals* — concatenating them
# without astype(str) raises "Object with dtype category cannot perform the numpy op add".
ks["target"] = (ks.substrate_genesymbol.astype(str) + "_"
                + ks.residue_type.astype(str) + ks.residue_offset.astype(int).astype(str))
net = ks[["enzyme_genesymbol", "target"]].rename(columns={"enzyme_genesymbol": "source"})
net = net.drop_duplicates()
net["weight"] = 1.0        # Enzsub is unsigned; see the caveat below

# adata: samples x phosphosites, log-scale, var_names formatted "GENE_S15"
dc.mt.ulm(adata, net, tmin=5)
activities = adata.obsm["score_ulm"]       # samples x kinases
```

Site ids must match `SUBSTRATE_<residue><offset>` (`SOCS3_Y204`) — the same convention as the
ActivatingSite filter above, so both routes read the same matrix.

> **Enzsub is unsigned.** OmniPath's enzyme-PTM records say *that* a kinase phosphorylates a site,
> not whether that activates or inhibits the substrate. `weight=1.0` therefore scores "how much of
> this kinase's substrate set moved", which is the standard kinase-activity readout — but a kinase
> whose substrates are inhibitory sites will still score positive. `op.requests.SignedPTMs` infers a
> sign from the interaction network when you need direction; state which you used.

Report `tmin` (kinases with fewer measured substrate sites are dropped) and how many kinases survived
it — a kinase scored on 5 sites is not comparable to one scored on 200.

## PhosphoSitePlus curation

PhosphoSitePlus (phosphosite.org) provides:
- **`Regulatory_sites`** — `ON_FUNCTION` annotations (activity induced/inhibited, enhances binding, …)
- **`Kinase_Substrate_Dataset`** — kinase→site edges (an alternative network to OmniPath's Enzsub)
- **Disease mutations** at or near phosphosites

Both are manual downloads (free for academic use, licence required for commercial).

## Pitfalls

- **Not normalizing by total protein** — high phospho may just reflect high protein
- **No ActivatingSite filter** — neutral sites dominate; biological signal buried
- **Treating phosphosites as genes** — `TP53_S15` ≠ TP53 gene-level
- **Not resolving isoform positions** — different isoforms have different numbering
- **Missing kinase-substrate context** — without the upstream kinase, interpretation is incomplete; score kinase activity (§ *Kinase activity inference*) rather than reading site lists

## Grounding

`report`: n phosphosites measured, activating-site filter applied (source + n filtered), occupancy normalization method, test, n significant, top hits with gene/site/log2FC. For kinase activity also record the network source + version (OmniPath Enzsub, `decoupler.__version__`), whether it was signed, `tmin`, and how many kinases survived it.

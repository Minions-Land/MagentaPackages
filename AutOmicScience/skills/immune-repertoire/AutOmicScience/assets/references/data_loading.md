# Loading paired scTCR/scBCR & tool interop

**Maturity: PARTIAL** — `sc-dandelion`, `scirpy` are **not in any pinned environment** (`task1–4`), so this method must be provisioned before it can run. Provision it into its own environment per `omics-shared`'s `assets/references/AOSE_nonStandard_env.md`, which carries the routing and the hard rules.

Two loaders (dandelion and scirpy) plus the bridge between them. Pick by what you'll do next:
dandelion `Dandelion` object for preprocessing/BCR; scirpy AnnData/MuData for downstream analytics.

## dandelion

```python
vdj = ddl.read_airr("filtered_contig_dandelion.tsv")   # AIRR rearrangement tsv -> Dandelion
# also: ddl.read_10x_vdj(csv/json), ddl.read_10x_airr(cellranger airr_rearrangement.tsv),
#       ddl.read_h5ddl("x.h5ddl"); merge samples with ddl.concat([...])
```

A `Dandelion` holds `.data` (contig-level AIRR), `.metadata` (per-cell summary), and — after
`generate_network` — `.graph`/`.layout`/`.distances`.

## scirpy

scirpy holds chains in `adata.obsm["airr"]` (awkward array); it runs on an **AnnData** (AIRR only)
or a **MuData** `{"gex","airr"}` and defaults to the `airr` modality.

```python
import scirpy as ir
adata = ir.io.read_10x_vdj("filtered_contig_annotations.csv")   # 10x
adata = ir.io.read_airr("rearrangement.tsv")                     # AIRR tsv (also accepts a list / DataFrame)
```

**Generic per-cell annotated table** (one row per cell with both chains' V/J/CDR3, e.g. an
already-annotated metadata CSV): reshape **wide → long AIRR** (one row per chain) and pass the
DataFrame to `read_airr`:

```python
import pandas as pd
def wide_to_airr(df, barcode="cell_barcode"):
    rows = []
    for _, r in df.iterrows():
        for arm, locus in (("TRA","TRA"), ("TRB","TRB")):      # TRA->VJ arm, TRB->VDJ arm
            cdr3 = r.get(f"{arm}_cdr3")
            if pd.notna(cdr3):
                rows.append({"cell_id": r[barcode], "locus": locus,
                             "v_call": r.get(f"{arm}_v_gene"), "j_call": r.get(f"{arm}_j_gene"),
                             "junction_aa": cdr3, "productive": True})
    return pd.DataFrame(rows)

adata = ir.io.read_airr(wide_to_airr(df_cells))                 # -> AnnData, chains in .obsm["airr"]
adata.obs = adata.obs.join(df_cells.set_index("cell_barcode")[["patient", "cell_type"]])
```

- Set `productive=True` — the default `index_chains` filter drops non-productive / no-`junction_aa` chains.
- If you also have a GEX count matrix, combine as `mu.MuData({"gex": adata_gex, "airr": adata})`
  (prefix obs keys `gex:`/`airr:` downstream). With only an annotated table (no expression matrix),
  the bare AIRR AnnData above is sufficient — scirpy works on both.
- Custom fields with no reader: build `ir.io.AirrCell` objects (`AirrCell.empty_chain_dict()` for
  the mandatory fields) then `ir.io.from_airr_cells([...])`. `from_airr` does **not** exist.

## Always index chains before any `tl.*` clonotype call

```python
ir.pp.index_chains(adata)     # -> obsm["airr"]["chain_indices"] (VJ_1/2, VDJ_1/2)
ir.tl.chain_qc(adata)         # -> obs receptor_type / chain_pairing (needed for within_group default)
```

## Interop (needs `pip install sc-dandelion` on scirpy's side)

```python
mdata = ddl.to_scirpy(vdj, to_mudata=True, gex_adata=adata)   # Dandelion -> scirpy MuData
adata = ddl.to_scirpy(vdj, to_mudata=False)                   # -> AnnData with .obsm["airr"]
adata = ir.io.from_dandelion(vdj, transfer=False, to_mudata=False)  # equivalent from scirpy's side
vdj   = ddl.from_scirpy(mdata)                                # reverse: scirpy -> Dandelion
```

Typical bridge: preprocess + reannotate + mutate in **dandelion**, then hand a clean object to
**scirpy** for repertoire analytics (or vice versa for lineage/SHM).

## Reporting

- Source format, n cells, n with a productive paired receptor, n donors; how chains were indexed.

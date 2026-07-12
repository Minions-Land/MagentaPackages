#!/usr/bin/env python3
"""Fetch the Biomni data-lake files that this package's skills need.

The Biomni tools read large reference files from a "data lake" directory. Those
files are NOT bundled with this package -- they live in Biomni's public release
bucket and are downloaded on demand into a directory of your choosing outside
this package's source tree.

Usage:
    # everything the three skills need, into a dir you choose
    python fetch_biomni_data.py --dest /path/you/choose

    # only what one skill needs
    python fetch_biomni_data.py --dest /path/you/choose --skill sgrna-design

    # the full upstream data lake (all 76 files)
    python fetch_biomni_data.py --dest /path/you/choose --all

Then point the tools at it, either by exporting an environment variable
(the tools use it as the default when data_lake_path is not passed):

    export BIOMNI_DATA_LAKE=/path/you/choose

or by passing data_lake_path="/path/you/choose" on each call.

Do NOT download into this package's source directory. Keep large data files
outside the Git working tree so package updates cannot replace them.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
import urllib.error

BASE_URL = "https://biomni-release.s3.amazonaws.com/data_lake"

# Files each skill's tools actually read from the data lake (verified against the
# upstream env_desc.py manifest). Shared files are listed under every skill that
# uses them; the download de-duplicates.
SKILL_FILES: dict[str, list[str]] = {
    "sgrna-design": [
        "sgRNA_KO_SP_human.txt",
        "sgRNA_KO_SP_mouse.txt",
    ],
    "single-cell-annotation": [
        "czi_census_datasets_v4.parquet",
    ],
    "biomedical-tools": [
        "czi_census_datasets_v4.parquet",
        "sgRNA_KO_SP_human.txt",
        "sgRNA_KO_SP_mouse.txt",
        "ddinter_alimentary_tract_metabolism.csv",
        "ddinter_antineoplastic.csv",
        "ddinter_antiparasitic.csv",
        "ddinter_blood_organs.csv",
        "ddinter_dermatological.csv",
        "ddinter_hormonal.csv",
        "ddinter_respiratory.csv",
        "ddinter_various.csv",
        "hp.obo",
        "txgnn_name_mapping.pkl",
        "txgnn_prediction.pkl",
    ],
}

# The full upstream data lake (all files listed in Biomni's env_desc.py). Used
# only with --all; most are not needed by this package's three skills.
FULL_MANIFEST: list[str] = [
    "BindingDB_All_202409.tsv", "DepMap_CRISPRGeneDependency.csv",
    "DepMap_CRISPRGeneEffect.csv", "DepMap_Model.csv",
    "DepMap_OmicsExpressionProteinCodingGenesTPMLogp1.csv", "DisGeNET.parquet",
    "McPAS-TCR.parquet", "Virus-Host_PPI_P-HIPSTER_2020.parquet",
    "affinity_capture-ms.parquet", "affinity_capture-rna.parquet",
    "broad_repurposing_hub_molecule_with_smiles.parquet",
    "broad_repurposing_hub_phase_moa_target_info.parquet", "co-fractionation.parquet",
    "czi_census_datasets_v4.parquet", "ddinter_alimentary_tract_metabolism.csv",
    "ddinter_antineoplastic.csv", "ddinter_antiparasitic.csv",
    "ddinter_blood_organs.csv", "ddinter_dermatological.csv", "ddinter_hormonal.csv",
    "ddinter_respiratory.csv", "ddinter_various.csv", "dosage_growth_defect.parquet",
    "enamine_cloud_library_smiles.pkl", "evebio_assay_table.csv",
    "evebio_bundle_table.csv", "evebio_compound_table.csv", "evebio_control_table.csv",
    "evebio_detailed_result_table.csv", "evebio_observed_points_table.csv",
    "evebio_summary_result_table.csv", "evebio_target_table.csv", "gene_info.parquet",
    "genebass_missense_LC_filtered.pkl", "genebass_pLoF_filtered.pkl",
    "genebass_synonymous_filtered.pkl", "genetic_interaction.parquet", "go-plus.json",
    "gtex_tissue_gene_tpm.parquet", "gwas_catalog.pkl", "hp.obo", "kg.csv",
    "marker_celltype.parquet", "miRDB_v6.0_results.parquet",
    "miRTarBase_MicroRNA_Target_Sites.parquet",
    "miRTarBase_microRNA_target_interaction.parquet",
    "miRTarBase_microRNA_target_interaction_pubmed_abtract.txt",
    "mousemine_m1_positional_geneset.parquet", "mousemine_m2_curated_geneset.parquet",
    "mousemine_m3_regulatory_target_geneset.parquet",
    "mousemine_m5_ontology_geneset.parquet",
    "mousemine_m8_celltype_signature_geneset.parquet",
    "mousemine_mh_hallmark_geneset.parquet", "msigdb_human_c1_positional_geneset.parquet",
    "msigdb_human_c2_curated_geneset.parquet",
    "msigdb_human_c3_regulatory_target_geneset.parquet",
    "msigdb_human_c3_subset_transcription_factor_targets_from_GTRD.parquet",
    "msigdb_human_c4_computational_geneset.parquet",
    "msigdb_human_c5_ontology_geneset.parquet",
    "msigdb_human_c6_oncogenic_signature_geneset.parquet",
    "msigdb_human_c7_immunologic_signature_geneset.parquet",
    "msigdb_human_c8_celltype_signature_geneset.parquet",
    "msigdb_human_h_hallmark_geneset.parquet", "omim.parquet", "proteinatlas.tsv",
    "proximity_label-ms.parquet", "reconstituted_complex.parquet",
    "sgRNA_KO_SP_human.txt", "sgRNA_KO_SP_mouse.txt", "synthetic_growth_defect.parquet",
    "synthetic_lethality.parquet", "synthetic_rescue.parquet", "two-hybrid.parquet",
    "txgnn_name_mapping.pkl", "txgnn_prediction.pkl", "variant_table.parquet",
]


def _dedup(files: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _download(filename: str, dest_dir: str) -> None:
    url = f"{BASE_URL}/{filename}"
    out_path = os.path.join(dest_dir, filename)
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        print(f"  skip (exists): {filename}")
        return
    tmp_path = out_path + ".part"
    with urllib.request.urlopen(url) as resp:  # noqa: S310 - fixed trusted host
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        with open(tmp_path, "wb") as out:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if total:
                    pct = 100 * done / total
                    print(f"\r  {filename}: {done/1e6:.0f}/{total/1e6:.0f} MB "
                          f"({pct:.0f}%)", end="", flush=True)
    os.replace(tmp_path, out_path)
    print(f"\r  OK: {filename} ({os.path.getsize(out_path)/1e6:.1f} MB)          ")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dest", required=True,
                        help="target directory (outside this repo) for the data lake")
    parser.add_argument("--skill", choices=sorted(SKILL_FILES),
                        help="fetch only the files this skill needs (default: all three)")
    parser.add_argument("--all", action="store_true",
                        help="fetch the full upstream data lake (76 files)")
    args = parser.parse_args()

    if args.all:
        files = FULL_MANIFEST
    elif args.skill:
        files = SKILL_FILES[args.skill]
    else:
        files = [f for fs in SKILL_FILES.values() for f in fs]
    files = _dedup(files)

    os.makedirs(args.dest, exist_ok=True)
    print(f"Downloading {len(files)} file(s) into {args.dest}")
    failed: list[str] = []
    for f in files:
        try:
            _download(f, args.dest)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            print(f"\n  FAILED: {f} ({exc})")
            failed.append(f)

    if failed:
        print(f"\n{len(failed)} file(s) failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    print(f"\nDone. Point the tools at it:  export BIOMNI_DATA_LAKE={args.dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

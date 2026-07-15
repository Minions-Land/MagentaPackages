"""Shared guards for the snapATAC2-backed scatac subcommands.

snapATAC2 owns the science (TSSe, FRiP, MACS3, gene matrices); this module only
turns its preconditions into diagnosable errors before it is called.
"""

import tempfile
from contextlib import contextmanager
from pathlib import Path

from ..shared.io import open_maybe_gzip

FRAGMENT_KEYS = ("fragment_paired", "fragment_single")


@contextmanager
def preserved_tempdir():
    """Restore `tempfile.tempdir`, which snapATAC2's macs3 leaks.

    `snapatac2.tl.macs3(groupby=...)` points the global `tempfile.tempdir` at its own
    scratch directory and never restores it (2.9.0, `tools/_call_peaks.py:175`). With
    `n_jobs=1` that assignment runs in this process, so once the scratch directory is
    removed every later `tempfile` call fails with a FileNotFoundError naming a path
    unrelated to whatever is actually running.
    """
    original = tempfile.tempdir
    try:
        yield
    finally:
        tempfile.tempdir = original


def require_fragments(adata, subcommand):
    """Fail loud unless `adata` carries the per-cell fragments snapATAC2 reads.

    snapATAC2's metrics/peak/gene functions read insertions from
    `obsm['fragment_paired'|'fragment_single']` and chromosome sizes from
    `uns['reference_sequences']` — both written by `snapatac2.pp.import_fragments`.
    Without them it raises a bare RuntimeError naming the obsm keys, with no hint
    about which upstream step was skipped.
    """
    if not any(key in adata.obsm for key in FRAGMENT_KEYS):
        raise ValueError(
            f"{subcommand} needs per-cell fragments in obsm{FRAGMENT_KEYS}, which only "
            "snapatac2.pp.import_fragments writes. The input looks like a plain feature "
            "matrix; re-run import_fragments (see the atac skill's import_fragments.md) "
            "and pass its output."
        )
    if "reference_sequences" not in adata.uns:
        raise ValueError(
            f"{subcommand} needs uns['reference_sequences'] (chromosome sizes) from "
            "snapatac2.pp.import_fragments. The object carries fragments but lost its "
            "reference sequences — do not hand-build it; re-run import_fragments."
        )


def chrom_sizes(adata):
    """Return {chromosome: length} from `uns['reference_sequences']`."""
    ref = adata.uns["reference_sequences"]
    return {
        str(name): int(length)
        for name, length in zip(ref["reference_seq_name"], ref["reference_seq_length"])
    }


def require_matching_chroms(adata, annotation_file):
    """Fail loud when the annotation and the data disagree on chromosome naming.

    On a 'chr1' vs '1' mismatch snapATAC2 surfaces `ValueError: The truth value of an
    array with more than one element is ambiguous`, which names neither the cause nor
    the file. Compare the two namespaces first and say what actually differs.
    """
    data_chroms = set(chrom_sizes(adata))
    anno_chroms = set()
    with open_maybe_gzip(annotation_file) as handle:
        for line in handle:
            if not line.startswith("#"):
                anno_chroms.add(line.split("\t", 1)[0])
    if not anno_chroms:
        raise ValueError(f"No records found in annotation file: {annotation_file}")
    if not (data_chroms & anno_chroms):
        raise ValueError(
            f"Chromosome naming mismatch between {Path(annotation_file).name} and the data: "
            f"annotation has {sorted(anno_chroms)[:5]}, data has {sorted(data_chroms)[:5]}. "
            "They share no chromosome, so every region would be empty. Use an annotation "
            "whose chromosome names match the fragment file (e.g. both 'chr1' or both '1')."
        )

import os
from typing import Any

import pandas as pd


def _resolve_data_lake(data_lake_path=None):
    """Resolve the Biomni data lake directory.

    Uses the explicit ``data_lake_path`` if given, else the ``BIOMNI_DATA_LAKE``
    environment variable. Raises loudly (no silent default) if neither is set.
    """
    path = data_lake_path or os.environ.get("BIOMNI_DATA_LAKE")
    if not path:
        raise RuntimeError(
            "Biomni data lake not configured: pass data_lake_path=... or set the "
            "BIOMNI_DATA_LAKE environment variable. Download the files these tools "
            "need with: python Biomni/scripts/fetch_biomni_data.py --dest <dir>"
        )
    return path


def design_knockout_sgrna(
    gene_name: str,
    data_lake_path: str = None,
    species: str = "human",
    num_guides: int = 1,
) -> dict[str, Any]:
    """Design sgRNAs for CRISPR knockout by searching pre-computed sgRNA libraries.
    Returns optimized guide RNAs for targeting a specific gene.

    Args:
        gene_name (str): Target gene symbol/name (e.g., "EGFR", "TP53")
        data_lake_path (str): Path to the directory holding the pre-computed sgRNA
            libraries (sgRNA_KO_SP_human.txt / sgRNA_KO_SP_mouse.txt)
        species (str): Target organism species (default: "human")
        num_guides (int): Number of guides to return (default: 1)

    Returns:
        Dict: Dictionary containing:
            - explanation: Explanation of the output fields
            - gene_name: Target gene name
            - species: Target species
            - guides: List of sgRNA sequences

    """
    data_lake_path = _resolve_data_lake(data_lake_path)
    DEFAULT_LIBRARIES = {
        "human": data_lake_path + "/sgRNA_KO_SP_human.txt",
        "mouse": data_lake_path + "/sgRNA_KO_SP_mouse.txt",
    }

    # Resolve the library file path for the requested species
    library_path = DEFAULT_LIBRARIES[species.lower()]

    # Check if library file exists
    if not os.path.exists(library_path):
        error_msg = f"Library file for {species} not found at path: {library_path}"
        error_msg += "\n\nThis error typically occurs when the datalake files are not available."
        raise FileNotFoundError(error_msg)

    # Load the sgRNA library (local tab-delimited file)
    try:
        df = pd.read_csv(library_path, delimiter="\t")
    except Exception as e:
        raise RuntimeError(f"Failed to load sgRNA library: {str(e)}") from None

    # Filter for target gene
    gene_name = gene_name.upper()  # Ensure consistent capitalization
    gene_df = df[df["Target Gene Symbol"].str.upper() == gene_name]

    if gene_df.empty:
        # Try partial matching if exact match fails
        gene_df = df[df["Target Gene Symbol"].str.upper().str.contains(gene_name)]

    if gene_df.empty:
        return {
            "explanation": "Output contains target gene name, species, and list of sgRNA sequences",
            "gene_name": gene_name,
            "species": species,
            "guides": [],
        }

    # Sort by combined rank (default priority)
    gene_df = gene_df.sort_values(by=["Combined Rank"])

    # Get top guides
    top_guides = gene_df.head(num_guides)

    # Extract just the sgRNA sequences
    guides = top_guides["sgRNA Sequence"].tolist()

    return {
        "explanation": "Output contains target gene name, species, and list of sgRNA sequences",
        "gene_name": gene_name,
        "species": species,
        "guides": guides,
    }


def get_oligo_annealing_protocol() -> dict[str, Any]:
    """Return a standard protocol for annealing oligonucleotides without phosphorylation.

    Returns:
        Dict: Dictionary containing detailed protocol steps for oligo annealing

    """
    protocol = {
        "title": "Oligo Annealing Protocol",
        "description": "Standard protocol for annealing complementary oligonucleotides",
        "steps": [
            {
                "step_number": 1,
                "title": "Prepare annealing reaction",
                "description": "Mix the following components in a PCR tube:",
                "components": [
                    {"name": "Forward oligo (100 μM)", "volume": "1 μl"},
                    {"name": "Reverse oligo (100 μM)", "volume": "1 μl"},
                    {"name": "Nuclease-free water", "volume": "8 μl"},
                ],
                "total_volume": "10 μl",
            },
            {
                "step_number": 2,
                "title": "Anneal in thermocycler",
                "description": "Run the following program on a thermocycler:",
                "program": [
                    {
                        "temperature": "95°C",
                        "time": "5 minutes",
                        "description": "Initial denaturation",
                    },
                    {
                        "temperature": "Ramp down to 25°C",
                        "rate": "5°C/minute",
                        "description": "Slow cooling for proper annealing",
                    },
                ],
            },
            {
                "step_number": 3,
                "title": "Dilute annealed oligos",
                "description": "Dilute the annealed oligos 1:200 in nuclease-free water",
                "details": "Add 1 μl of annealed oligos to 199 μl of nuclease-free water",
            },
        ],
        "notes": [
            "Store annealed and diluted oligos at -20°C for long-term storage",
            "Diluted oligos can be used directly in ligation reactions",
        ],
    }

    return protocol

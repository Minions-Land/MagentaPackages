# Tool: design_knockout_sgrna

Design sgRNAs for CRISPR knockout by searching pre-computed, ranked human or mouse libraries distributed by Biomni.

## Description

Searches pre-computed sgRNA knockout libraries and returns guide candidates ordered by
their `Combined Rank` for a target gene. The library files contain on-target scores,
off-target ranks, PAMs, strands, and target positions. Returned candidates still require
independent off-target review and experimental validation.

## Parameters

### Required

- **gene_name** (str): Target gene symbol/name
  - Example: "EGFR", "TP53", "BRCA1"
  - Case-insensitive (converted to uppercase)
  - Supports partial matching if exact match fails

### Optional

- **data_lake_path** (str): Directory containing the sgRNA libraries. When omitted,
  the tool uses `BIOMNI_DATA_LAKE`.
  - Must contain `sgRNA_KO_SP_human.txt` for human
  - Must contain `sgRNA_KO_SP_mouse.txt` for mouse

- **species** (str): Target organism species
  - Default: "human"
  - Options: "human", "mouse"
  - Case-insensitive

- **num_guides** (int): Number of guides to return
  - Default: 1
  - Returns top-ranked guides by Combined Rank score
  - Recommend requesting 3-4 for experimental validation

## Data Setup

The library files are not bundled with this skill and are not downloaded from
Addgene at runtime. From the MagentaPackages repository root, fetch the files
distributed by Biomni:

```bash
python Biomni/scripts/fetch_biomni_data.py \
  --dest /absolute/path/to/biomni-data \
  --skill sgrna-design
export BIOMNI_DATA_LAKE=/absolute/path/to/biomni-data
```

You can then omit `data_lake_path`, or pass the directory explicitly on each call.

## Returns

Dictionary containing:
- **explanation**: Description of output fields
- **gene_name**: Target gene name (uppercase)
- **species**: Target species
- **guides**: List of sgRNA sequences (20 bp, 5' to 3')

Returns empty guides list if gene not found in library.

## Usage Example

```python
import sys
sys.path.insert(0, "<SKILL_DIR>/tools")   # <SKILL_DIR> = this skill's directory (where SKILL.md lives)
from design_knockout_sgrna import design_knockout_sgrna

# Single guide for human gene
result = design_knockout_sgrna(
    gene_name="TP53",
    species="human",
    num_guides=1
)

# Multiple guides for validation
result = design_knockout_sgrna(
    gene_name="EGFR",
    data_lake_path="./data",
    species="human",
    num_guides=4
)

# Mouse gene knockout
result = design_knockout_sgrna(
    gene_name="Trp53",
    data_lake_path="./data",
    species="mouse",
    num_guides=3
)

# Access results
print(f"Gene: {result['gene_name']}")
print(f"Species: {result['species']}")
for i, guide in enumerate(result['guides'], 1):
    print(f"Guide {i}: {guide}")
```

## Implementation Notes

### Library Format
The sgRNA libraries are tab-delimited files with columns:
- Target Gene Symbol
- sgRNA Sequence (20 bp)
- Combined Rank (lower is better)
- Additional metadata (efficacy scores, off-targets, etc.)

### Search Strategy
1. Exact match on gene symbol (case-insensitive)
2. If no exact match, tries partial matching (substring search)
3. Sorts results by Combined Rank
4. Returns top N guides

### Ranking
Guides are ordered by the library's `Combined Rank`. The distributed files also
provide on-target efficacy scores and off-target ranks; this package does not
recompute or independently validate those values.

### Error Handling
- Raises `FileNotFoundError` if library file doesn't exist
- Raises `RuntimeError` if library fails to load
- Returns empty guides list if gene not found (no exception)

### Performance
- Fast lookup (indexed CSV read)
- No computational design - pre-computed results only
- Typical query: <1 second for any gene

## Data Source

**Distribution**: Biomni release data lake

- Files: `sgRNA_KO_SP_human.txt`, `sgRNA_KO_SP_mouse.txt`
- Species: Human, Mouse
- Upstream metadata describes them as sgRNA knockout data. It does not establish
  that every entry comes from Addgene or has experimental validation.

Addgene remains a useful independent resource for CRISPR plasmids, protocols,
and published guide information, but it is not the download location for these
two Biomni files.

## Limitations

### Coverage
- Limited to genes represented in the downloaded libraries
- A returned guide is a ranked candidate, not proof of experimental efficacy
- For novel genes, use Tier 2 (CRISPick) or Tier 3 (de novo) tools

### PAM Compatibility
- Library contains primarily SpCas9 (NGG PAM) sequences
- Check PAM context if using alternative Cas enzymes

### Species Support
- Currently: Human, Mouse
- For other species, use computational design tools

## Best Practices

### Experimental Validation
For every returned candidate:
1. Test 3-4 guides per target
2. Include non-targeting control
3. Verify by T7E1 or Sanger sequencing
4. Confirm protein knockout by Western blot

### Citation Requirements
When using results from this tool:
1. Cite the Biomni tool: bioRxiv 2025.05.30.656746v1
2. Cite any external guide database or experimental publication actually used

### When to Use Other Tools
Use computational design (CRISPick, CHOPCHOP) if:
- Gene not found in library (empty guides list)
- Need custom PAM sequences
- Want multiple design algorithms for comparison
- Targeting non-coding regions

## Dependencies

- **pandas**: For library data loading
- **os**: For file path handling

## Related Tools

- [crispr_editing.md](crispr_editing.md): Simulate CRISPR editing outcomes
- CRISPick: Computational design for any gene
- CHOPCHOP: Alternative design algorithm

## Troubleshooting

**FileNotFoundError**: Library file not found
- Check `data_lake_path` is correct
- If no explicit path is passed, check `BIOMNI_DATA_LAKE`
- Verify sgRNA library files exist
- Download them with `Biomni/scripts/fetch_biomni_data.py --skill sgrna-design`

**Empty guides list**: Gene not in library
- Try computational design (CRISPick)
- Check gene symbol spelling
- Try alternative gene names (synonyms)

**Wrong species**: Check species parameter
- Use "human" or "mouse" (case-insensitive)
- Verify gene name matches species conventions

## Source Attribution

- **Tool Source**: Biomni (Stanford SNAP Lab)
- **Library Distribution**: Biomni release data lake
- **License**: MIT (tool); CC BY 4.0 (this guide)
- **Paper**: bioRxiv 2025.05.30.656746v1

# Reference — Lipid-Class Nomenclature

**Maturity: REFERENCE** — hand-rolled parsing with `re` (stdlib). Vendor platforms each spell lipids
differently and none of them is a database identifier, so this is a normalisation step you own.

Parse lipid shorthand: class + carbon:double-bond composition.

## The formats you will actually meet

One class, many spellings — a parser that only handles `PC 34:2` silently drops most of a real table:

| Spelling | Where from | Meaning |
|---|---|---|
| `PC 34:2` | LIPID MAPS `abbrev`, Metabolon | sum composition |
| `PC(34:2)` | LipidSearch, Lipidyzer | same lipid, bracketed |
| `PC 18:1_16:0` / `TG(16:0_18:1_18:2)` | chain-resolved | individual chains, `_` = order unknown |
| `Cer(d18:1/16:0)` / `SM(d18:1/16:0)` | sphingolipids | `d`/`t` = di/tri-hydroxy base; `/` = sn-position known |
| `PC O-34:1` / `PC P-34:1` | ether lipids / plasmalogens | `O-` alkyl, `P-` alkenyl |

## Parser

```python
import re

LIPID = re.compile(r"""
    ^(?P<cls>[A-Za-z][A-Za-z0-9]*)                    # class: PC, LPC, TG, Cer, SM, CE
    \s*(?:\(|\s)\s*                                   # separator: "(" or whitespace
    (?P<ether>[OP]-)?                                 # ether (O-) / plasmalogen (P-) prefix
    (?P<chains>[dtme]?\d+:\d+(?:[_/][dtme]?\d+:\d+)*) # 34:2 | d18:1/16:0 | 16:0_18:1_18:2
    \)?$
""", re.X)

def parse_lipid(name):
    """Parse lipid shorthand into class + summed composition. None if not lipid shorthand."""
    m = LIPID.match(name.strip())
    if not m:
        return None
    chains = re.findall(r"[dtme]?(\d+):(\d+)", m.group("chains"))
    return {
        "class": m.group("cls"),
        "ether": m.group("ether"),                       # None | "O-" | "P-"
        "carbons": sum(int(c) for c, _ in chains),       # chain-resolved names sum to the total
        "double_bonds": sum(int(d) for _, d in chains),
        "n_chains": len(chains),
    }
```

Verified against `PC 34:2`, `PC(34:2)`, `TG(16:0_18:1_18:2)` → 52:3, `Cer(d18:1/16:0)` → 34:1,
`PC O-34:1`, `LPC 18:0`, `SM(d18:1/16:0)`, `CE(18:1)`, `FA 16:0`, `PC 18:1_16:0` → 34:1; and it
returns `None` for `glucose` / `HMDB0000122` rather than mangling them.

**Chain-resolved names sum.** `TG(16:0_18:1_18:2)` is the same lipid as `TG 52:3` — the parser adds
the chains so both spellings land in one bin. Do not compare a `52:3` row against a `16:0_18:1_18:2`
row as if they were different species.

## Common classes

- **PC**: phosphatidylcholine · **LPC**: lysophosphatidylcholine
- **TG/TAG**: triacylglycerol · **DG/DAG**: diacylglycerol
- **CE**: cholesteryl ester · **FA**: fatty acid
- **Cer**: ceramide · **SM**: sphingomyelin
- **AC/CAR**: acylcarnitine

Class abbreviations are **not standardised across vendors** (`TG` vs `TAG`, `AC` vs `CAR`). Map them
to one vocabulary before grouping, and report the mapping.

## Pitfalls

- **A space-only regex** — `r"(\w+)\s+(\d+):(\d+)"` matches `PC 34:2` but not `PC(34:2)`,
  `TG(16:0_18:1_18:2)`, `Cer(d18:1/16:0)` or `PC O-34:1`; on a LipidSearch table it drops nearly
  every row, and silently, because `re.match` returns `None`.
- **Dropping the ether prefix** — `PC O-34:1` is an ether lipid, biologically distinct from
  `PC 34:1`. Parsing them to the same key merges two species.
- **Treating shorthand as an identifier** — it is not queryable in HMDB/KEGG/LIPID MAPS as-is. Map to
  an `lm_id` first (`annotation.md`); LIPID MAPS' `abbrev` field is the space form (`FA 16:0`).
- **Not counting the unparsed** — report how many names `parse_lipid` returned `None` for. A parser
  that silently keeps 40% of the table looks identical to one that keeps 100%.

## Grounding

`report`: n lipids parsed vs n input, **n unparsed (with examples)**, per-class distribution after
vocabulary mapping, and how many names were chain-resolved vs sum-composition.

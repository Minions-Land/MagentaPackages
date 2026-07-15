"""Shared cross-modality utilities.

Submodules are imported lazily (PEP 562) so that importing a stdlib-only module
such as ``preflight`` does not pull in scanpy/anndata. This lets preflight report
a missing core dependency as structured output instead of crashing at import.
"""
import importlib

__all__ = ["conventions", "io", "summarize", "preprocess", "score",
           "preflight", "layout", "evidence", "load_dataset"]


def __getattr__(name):
    if name in __all__:
        return importlib.import_module(f".{name}", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""Format adapters that translate files to the canonical string DataFrame."""

from .registry import get_adapter, parse_dataset

__all__ = ["get_adapter", "parse_dataset"]

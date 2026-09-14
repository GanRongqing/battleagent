"""strategy_library — simple Strategy metadata registry (CRUD) on SQLite."""
from .repository import StrategyRepository, get_repository  # noqa
__all__ = ["StrategyRepository", "get_repository"]

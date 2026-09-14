from dataclasses import dataclass, field, asdict
from typing import List, Optional

VALID_SIDES = {"white", "black", "neutral", "system"}
VALID_STATUS = {"experimental", "active", "frozen", "completed", "deprecated"}


@dataclass
class StrategyInfo:
    strategy_id: str
    name: str
    side: str
    version: Optional[str] = None
    strategy_type: str = "harness"
    status: str = "experimental"
    description: Optional[str] = None
    entrypoint: Optional[str] = None
    runtime_mode: Optional[str] = None
    parent_id: Optional[str] = None
    hash: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class StrategyCreate:
    strategy_id: str
    name: str
    side: str
    version: Optional[str] = None
    strategy_type: str = "harness"
    status: str = "experimental"
    description: Optional[str] = None
    entrypoint: Optional[str] = None
    runtime_mode: Optional[str] = None
    parent_id: Optional[str] = None
    hash: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[dict] = None

    def to_info(self, now):
        return StrategyInfo(strategy_id=self.strategy_id, name=self.name, side=self.side,
                            version=self.version, strategy_type=self.strategy_type,
                            status=self.status, description=self.description,
                            entrypoint=self.entrypoint, runtime_mode=self.runtime_mode,
                            parent_id=self.parent_id, hash=self.hash,
                            tags=self.tags or [], metadata=self.metadata or {},
                            created_at=now, updated_at=now)

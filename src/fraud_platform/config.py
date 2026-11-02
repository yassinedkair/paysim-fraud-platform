"""Chemins locaux, sans connexion cloud ni lecture de secrets."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DataPaths:
    """Sépare les sources, les couches de données et la quarantaine."""

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    @property
    def raw(self) -> Path:
        return self.root / "raw"

    @property
    def bronze(self) -> Path:
        return self.root / "bronze"

    @property
    def silver(self) -> Path:
        return self.root / "silver"

    @property
    def gold(self) -> Path:
        return self.root / "gold"

    @property
    def quarantine(self) -> Path:
        return self.root / "quarantine"

    def create(self) -> None:
        """Crée les dossiers ; peut être rappelé sans effacer les données."""
        for path in (self.raw, self.bronze, self.silver, self.gold, self.quarantine):
            path.mkdir(parents=True, exist_ok=True)

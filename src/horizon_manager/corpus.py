"""Known horizon corpus registry for the external Horizon Manager app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SHARED_ROOT = Path.home() / "projects/shared"


@dataclass(frozen=True)
class HorizonCorpus:
    name: str
    title: str
    repo_root: Path
    horizons_dir: Path
    generated_dir: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "repo_root", Path(self.repo_root))
        object.__setattr__(self, "horizons_dir", Path(self.horizons_dir))
        object.__setattr__(self, "generated_dir", Path(self.generated_dir))

    def to_dict(self) -> dict[str, str]:
        return {
            "generated_dir": str(self.generated_dir),
            "horizons_dir": str(self.horizons_dir),
            "name": self.name,
            "repo_root": str(self.repo_root),
            "title": self.title,
        }


def known_corpora(shared_root: Path = SHARED_ROOT) -> tuple[HorizonCorpus, ...]:
    shared = Path(shared_root)
    geoforge = shared / "GeoForge"
    cli_profile = shared / "cli-profile-manager"
    horizon_manager = geoforge / "management/subprojects/horizon-manager"
    return (
        HorizonCorpus(
            name="hco",
            title="HCO subproject horizons",
            repo_root=geoforge,
            horizons_dir=geoforge / "management/subprojects/hermes-consistency-orchestrator/horizons",
            generated_dir=geoforge / "management/subprojects/hermes-consistency-orchestrator",
        ),
        HorizonCorpus(
            name="cli-profile-manager",
            title="CLI Profile Manager management horizons",
            repo_root=cli_profile,
            horizons_dir=cli_profile / "management/horizons",
            generated_dir=cli_profile / "management",
        ),
        HorizonCorpus(
            name="geoforge",
            title="GeoForge management horizons",
            repo_root=geoforge,
            horizons_dir=geoforge / "management/horizons",
            generated_dir=geoforge / "management",
        ),
        HorizonCorpus(
            name="horizon-manager",
            title="Horizon Manager management horizons",
            repo_root=horizon_manager,
            horizons_dir=horizon_manager / "management/horizons",
            generated_dir=horizon_manager / "management",
        ),
    )


def corpus_names() -> tuple[str, ...]:
    return tuple(corpus.name for corpus in known_corpora())


def default_corpus() -> HorizonCorpus:
    return known_corpora()[0]


def resolve_corpus(name: str | None) -> HorizonCorpus:
    normalized = (name or default_corpus().name).strip()
    for corpus in known_corpora():
        if corpus.name == normalized:
            return corpus
    options = ", ".join(corpus_names())
    raise ValueError(f"unknown corpus: {normalized!r}; expected one of: {options}")

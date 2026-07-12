"""Config-backed horizon corpus registry for the external Horizon Manager app."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tomllib
from typing import Any, Iterable


SHARED_ROOT = Path.home() / "projects/shared"
CONFIG_ENV_VAR = "HORIZON_MANAGER_CORPORA_CONFIG"
DEFAULT_CONFIG_PATH = Path.home() / ".config/horizon-manager/corpora.toml"
_REQUIRED_CONFIG_FIELDS = ("title", "repo_root", "horizons_dir", "generated_dir")


@dataclass(frozen=True)
class HorizonCorpus:
    name: str
    title: str
    repo_root: Path
    horizons_dir: Path
    generated_dir: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "title", self.title.strip())
        object.__setattr__(self, "repo_root", Path(self.repo_root).expanduser())
        object.__setattr__(self, "horizons_dir", Path(self.horizons_dir).expanduser())
        object.__setattr__(self, "generated_dir", Path(self.generated_dir).expanduser())

    def to_dict(self) -> dict[str, str]:
        return {
            "generated_dir": str(self.generated_dir),
            "horizons_dir": str(self.horizons_dir),
            "name": self.name,
            "repo_root": str(self.repo_root),
            "title": self.title,
        }


@dataclass(frozen=True, order=True)
class CorpusPathDiagnostic:
    corpus: str
    field: str
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "corpus": self.corpus,
            "field": self.field,
            "message": self.message,
            "path": self.path,
        }


def builtin_corpora(shared_root: Path = SHARED_ROOT) -> tuple[HorizonCorpus, ...]:
    shared = Path(shared_root).expanduser()
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


def load_corpora(
    *,
    shared_root: Path = SHARED_ROOT,
    config_path: str | Path | None = None,
    include_builtin: bool = True,
) -> tuple[HorizonCorpus, ...]:
    corpora = list(builtin_corpora(shared_root)) if include_builtin else []
    selected_config = _selected_config_path(config_path)
    if selected_config is not None and selected_config.exists():
        corpora.extend(_load_config_file(selected_config))
    return _dedupe_corpora(corpora)


def known_corpora(shared_root: Path = SHARED_ROOT, config_path: str | Path | None = None) -> tuple[HorizonCorpus, ...]:
    return load_corpora(shared_root=shared_root, config_path=config_path)


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


def validate_corpus_paths(corpora: Iterable[HorizonCorpus], *, require_non_empty_horizons: bool = True) -> tuple[CorpusPathDiagnostic, ...]:
    diagnostics: list[CorpusPathDiagnostic] = []
    for corpus in sorted(corpora, key=lambda item: item.name):
        diagnostics.extend(_path_diagnostics(corpus, "repo_root", corpus.repo_root, require_directory=True))
        diagnostics.extend(_path_diagnostics(corpus, "horizons_dir", corpus.horizons_dir, require_directory=True))
        diagnostics.extend(_path_diagnostics(corpus, "generated_dir", corpus.generated_dir, require_directory=True))
        if require_non_empty_horizons and corpus.horizons_dir.is_dir() and not any(corpus.horizons_dir.glob("H[0-9][0-9]*/README.md")):
            diagnostics.append(
                CorpusPathDiagnostic(
                    corpus=corpus.name,
                    field="horizons_dir",
                    code="empty_horizons_dir",
                    path=str(corpus.horizons_dir),
                    message="horizons_dir contains no Hxx README files",
                )
            )
    return tuple(sorted(diagnostics))


def _selected_config_path(config_path: str | Path | None) -> Path | None:
    if config_path is not None:
        return Path(config_path).expanduser()
    env_path = os.environ.get(CONFIG_ENV_VAR, "").strip()
    if env_path:
        return Path(env_path).expanduser()
    return DEFAULT_CONFIG_PATH


def _load_config_file(path: Path) -> tuple[HorizonCorpus, ...]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    raw_corpora = data.get("corpora", {})
    if not isinstance(raw_corpora, dict):
        raise ValueError("corpora config must contain a [corpora.<name>] table")
    config_dir = path.parent
    return tuple(_corpus_from_config(name, value, config_dir) for name, value in sorted(raw_corpora.items()))


def _corpus_from_config(name: str, value: Any, config_dir: Path) -> HorizonCorpus:
    if not isinstance(value, dict):
        raise ValueError(f"corpus {name!r} must be a table")
    missing = [field for field in _REQUIRED_CONFIG_FIELDS if not str(value.get(field, "")).strip()]
    if missing:
        raise ValueError(f"corpus {name!r} missing required field(s): {', '.join(missing)}")
    repo_root = _resolve_path(value["repo_root"], base=config_dir)
    return HorizonCorpus(
        name=name,
        title=str(value["title"]),
        repo_root=repo_root,
        horizons_dir=_resolve_path(value["horizons_dir"], base=repo_root),
        generated_dir=_resolve_path(value["generated_dir"], base=repo_root),
    )


def _resolve_path(value: Any, *, base: Path) -> Path:
    raw = os.path.expandvars(os.path.expanduser(str(value).strip()))
    path = Path(raw)
    if path.is_absolute():
        return path
    return base / path


def _dedupe_corpora(corpora: Iterable[HorizonCorpus]) -> tuple[HorizonCorpus, ...]:
    seen: dict[str, HorizonCorpus] = {}
    duplicates: list[str] = []
    for corpus in corpora:
        if not corpus.name:
            raise ValueError("corpus name must not be empty")
        if corpus.name in seen:
            duplicates.append(corpus.name)
        seen[corpus.name] = corpus
    if duplicates:
        raise ValueError(f"duplicate corpus name(s): {', '.join(sorted(set(duplicates)))}")
    return tuple(seen.values())


def _path_diagnostics(corpus: HorizonCorpus, field: str, path: Path, *, require_directory: bool) -> tuple[CorpusPathDiagnostic, ...]:
    if not str(path).strip():
        return (
            CorpusPathDiagnostic(
                corpus=corpus.name,
                field=field,
                code="empty_path",
                path="",
                message=f"{field} is empty",
            ),
        )
    if not path.exists():
        return (
            CorpusPathDiagnostic(
                corpus=corpus.name,
                field=field,
                code="missing_path",
                path=str(path),
                message=f"{field} does not exist",
            ),
        )
    if require_directory and not path.is_dir():
        return (
            CorpusPathDiagnostic(
                corpus=corpus.name,
                field=field,
                code="not_directory",
                path=str(path),
                message=f"{field} is not a directory",
            ),
        )
    return ()

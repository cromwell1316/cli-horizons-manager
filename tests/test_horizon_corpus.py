"""Tests for the config-backed Horizon Manager corpus registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from horizon_manager.corpus import (
    CONFIG_ENV_VAR,
    HorizonCorpus,
    known_corpora,
    load_corpora,
    resolve_corpus,
    validate_corpus_paths,
)


def test_builtin_corpora_keep_existing_order_and_fields(tmp_path: Path) -> None:
    corpora = known_corpora(shared_root=tmp_path, config_path=tmp_path / "missing.toml")

    assert [corpus.name for corpus in corpora] == ["hco", "cli-profile-manager", "geoforge", "horizon-manager"]
    assert corpora[0].title == "HCO subproject horizons"
    assert corpora[0].repo_root == tmp_path / "GeoForge"
    assert corpora[0].horizons_dir == tmp_path / "GeoForge/management/subprojects/hermes-consistency-orchestrator/horizons"
    assert corpora[0].generated_dir == tmp_path / "GeoForge/management/subprojects/hermes-consistency-orchestrator"


def test_load_corpora_reads_configured_corpora_from_toml(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    config = tmp_path / "corpora.toml"
    config.write_text(
        """[corpora.demo]
title = "Demo Horizons"
repo_root = "repo"
horizons_dir = "management/horizons"
generated_dir = "management"
""",
        encoding="utf-8",
    )

    corpora = load_corpora(config_path=config, include_builtin=False)

    assert len(corpora) == 1
    assert corpora[0].name == "demo"
    assert corpora[0].title == "Demo Horizons"
    assert corpora[0].repo_root == repo
    assert corpora[0].horizons_dir == repo / "management/horizons"
    assert corpora[0].generated_dir == repo / "management"


def test_env_config_path_is_used_when_no_explicit_config_is_passed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    config = tmp_path / "corpora.toml"
    config.write_text(
        f"""[corpora.env_demo]
title = "Env Demo"
repo_root = "{repo}"
horizons_dir = "horizons"
generated_dir = "."
""",
        encoding="utf-8",
    )
    monkeypatch.setenv(CONFIG_ENV_VAR, str(config))

    corpora = load_corpora(shared_root=tmp_path / "shared", include_builtin=False)

    assert [corpus.name for corpus in corpora] == ["env_demo"]


def test_duplicate_configured_corpus_names_are_rejected(tmp_path: Path) -> None:
    config = tmp_path / "corpora.toml"
    config.write_text(
        """[corpora.hco]
title = "Duplicate"
repo_root = "."
horizons_dir = "horizons"
generated_dir = "."
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate corpus name"):
        load_corpora(shared_root=tmp_path, config_path=config)


def test_missing_config_fields_are_rejected_deterministically(tmp_path: Path) -> None:
    config = tmp_path / "corpora.toml"
    config.write_text(
        """[corpora.bad]
title = ""
repo_root = "."
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="corpus 'bad' missing required field\\(s\\): title, horizons_dir, generated_dir"):
        load_corpora(config_path=config, include_builtin=False)


def test_resolve_corpus_reports_available_options(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(CONFIG_ENV_VAR, raising=False)

    with pytest.raises(ValueError, match="expected one of: hco, cli-profile-manager, geoforge, horizon-manager"):
        resolve_corpus("missing")


def test_validate_corpus_paths_reports_missing_and_empty_horizons_deterministically(tmp_path: Path) -> None:
    empty_repo = tmp_path / "empty-repo"
    empty_horizons = empty_repo / "management/horizons"
    empty_horizons.mkdir(parents=True)
    (empty_repo / "management").mkdir(exist_ok=True)
    corpora = (
        HorizonCorpus(
            name="empty",
            title="Empty",
            repo_root=empty_repo,
            horizons_dir=empty_horizons,
            generated_dir=empty_repo / "management",
        ),
        HorizonCorpus(
            name="missing",
            title="Missing",
            repo_root=tmp_path / "missing-repo",
            horizons_dir=tmp_path / "missing-repo/horizons",
            generated_dir=tmp_path / "missing-repo/generated",
        ),
    )

    diagnostics = validate_corpus_paths(corpora)

    assert [(item.corpus, item.field, item.code) for item in diagnostics] == [
        ("empty", "horizons_dir", "empty_horizons_dir"),
        ("missing", "generated_dir", "missing_path"),
        ("missing", "horizons_dir", "missing_path"),
        ("missing", "repo_root", "missing_path"),
    ]
    assert diagnostics[0].to_dict()["message"] == "horizons_dir contains no Hxx README files"

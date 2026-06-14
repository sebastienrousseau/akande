# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Pytest mirror of tests/smoke_imports.py.

The shell-driven script in ``scripts/regression.sh`` runs the
``smoke_imports`` module directly to validate a *fresh* install.
This test runs the same expectations inside the normal pytest
suite so a missed module addition surfaces in PR CI, not after
release.
"""

from __future__ import annotations

import importlib

import pytest

from tests.smoke_imports import (
    OPTIONAL_MODULES,
    REQUIRED_MODULES,
)


@pytest.mark.parametrize("module", REQUIRED_MODULES)
def test_required_module_imports(module: str) -> None:
    importlib.import_module(module)


@pytest.mark.parametrize("module", OPTIONAL_MODULES)
def test_optional_module_imports_or_skips(module: str) -> None:
    try:
        importlib.import_module(module)
    except ImportError as exc:  # pragma: no cover - env dependent
        pytest.skip(
            f"optional dep missing: {type(exc).__name__}: {exc}"
        )


def test_required_list_has_no_duplicates() -> None:
    assert len(REQUIRED_MODULES) == len(set(REQUIRED_MODULES))


def test_optional_list_has_no_duplicates() -> None:
    assert len(OPTIONAL_MODULES) == len(set(OPTIONAL_MODULES))


def test_required_and_optional_are_disjoint() -> None:
    assert not (set(REQUIRED_MODULES) & set(OPTIONAL_MODULES))

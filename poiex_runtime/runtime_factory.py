"""Fail-closed runtime store selection for local and Cloud Run environments."""

from __future__ import annotations

import os
from typing import Callable, Mapping, Optional

from .firestore_store import FirestoreStore
from .store import MemoryStore, RuntimeStore


def build_store_from_env(
    env: Optional[Mapping[str, str]] = None,
    *,
    firestore_factory: Callable[..., RuntimeStore] = FirestoreStore.from_default_credentials,
) -> RuntimeStore:
    env = env or os.environ
    mode = env.get("POIEX_GOC_STORE", "memory").strip().lower()
    on_cloud_run = bool(env.get("K_SERVICE"))

    if on_cloud_run and mode != "firestore":
        raise RuntimeError(
            "Cloud Run execution must explicitly set POIEX_GOC_STORE=firestore; "
            "refusing ephemeral MemoryStore for governed state"
        )

    if mode == "memory":
        return MemoryStore()
    if mode != "firestore":
        raise ValueError(f"unsupported POIEX_GOC_STORE mode: {mode}")

    return firestore_factory(
        project=env.get("GOOGLE_CLOUD_PROJECT") or None,
        database=env.get("FIRESTORE_DATABASE") or None,
        namespace=env.get("POIEX_GOC_NAMESPACE", "poiex_goc_v0_1"),
    )

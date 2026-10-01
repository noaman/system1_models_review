"""Call each System 1 model and return a normalized result."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from typing import Any

from playground.catalog import ModelSpec, model_by_id
from playground.normalize import normalize_response

logger = logging.getLogger(__name__)


class ModelRunner:
    """Shared lifecycle for a lazily created client."""

    spec: ModelSpec

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def run(self, state: Any, questions: list[dict]) -> dict:
        started = time.perf_counter()
        error = None
        normalized: dict = {
            "answers": {},
            "backend_model": None,
            "routing_reason": None,
            "usage": None,
        }
        try:
            raw = self.infer(state, {question["id"]: question["wire"] for question in questions})
            normalized = normalize_response(raw, questions)
        except Exception as exc:
            error = public_error(exc)
            logger.warning("%s failed: %s", self.spec.id, exc.__class__.__name__)
        else:
            logger.info("%s finished", self.spec.id)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        return {
            "id": self.spec.id,
            "name": self.spec.name,
            "elapsed_ms": elapsed_ms,
            "error": error,
            "backend_model": normalized["backend_model"],
            "routing_reason": normalized["routing_reason"],
            "usage": normalized["usage"],
            "answers": normalized["answers"],
        }

    def infer(self, state: Any, questions: dict[str, dict]) -> Any:
        raise NotImplementedError


class TypeSafeRunner(ModelRunner):
    spec = model_by_id("typesafe")

    def __init__(self) -> None:
        super().__init__()
        self._client = None

    def infer(self, state: Any, questions: dict[str, dict]) -> Any:
        return self._client_or_create().system_one(state=state, questions=questions)

    def _client_or_create(self):
        if self._client is not None:
            return self._client
        with self._lock:
            if self._client is None:
                api_key = os.environ.get("JEV_APIKEY")
                if not api_key:
                    raise RuntimeError("JEV_APIKEY is not set. Add it to .env and restart the playground.")
                from typesafe_sdk import TypeSafeClient

                self._client = TypeSafeClient(api_key=api_key)
            return self._client


class LayaRunner(ModelRunner):
    """One router for the process. Checkpoints are loaded at startup and kept resident."""

    spec = model_by_id("laya")
    _CHECKPOINTS = ("english", "multilingual")

    def __init__(self) -> None:
        super().__init__()
        self._router = None
        self._warmed = False
        self._warm_error: str | None = None

    @property
    def warmed(self) -> bool:
        return self._warmed

    @property
    def warm_error(self) -> str | None:
        return self._warm_error

    def warm(self) -> None:
        """Download and build the routing checkpoints before the first question."""
        if self._warmed:
            return
        started = time.perf_counter()
        names = ", ".join(self._CHECKPOINTS)
        print(f"==> Loading Laya into memory ({names})...", flush=True)
        print("    The first startup downloads the checkpoints. Later questions reuse them.", flush=True)
        try:
            self._router_or_create().preload(list(self._CHECKPOINTS))
        except Exception as exc:
            self._warm_error = public_error(exc)
            print(f"==> Laya did not load: {self._warm_error}", flush=True)
            logger.warning("Laya preload failed: %s", exc.__class__.__name__)
            return
        self._warmed = True
        self._warm_error = None
        elapsed = time.perf_counter() - started
        print(f"==> Laya is in memory ({elapsed:.0f}s).", flush=True)

    def infer(self, state: Any, questions: dict[str, dict]) -> Any:
        return self._router_or_create().predict(state, questions)

    def _router_or_create(self):
        if self._router is not None:
            return self._router
        with self._lock:
            if self._router is None:
                from laya import Router

                # Hold both auto-routed checkpoints so a language switch does not
                # evict one and load it again on the next question.
                self._router = Router(max_loaded=len(self._CHECKPOINTS))
            return self._router


_RUNNERS: dict[str, ModelRunner] = {
    "typesafe": TypeSafeRunner(),
    "laya": LayaRunner(),
}


def warm_laya() -> None:
    runner = _RUNNERS["laya"]
    if isinstance(runner, LayaRunner):
        runner.warm()


def laya_memory_status() -> tuple[bool, str]:
    runner = _RUNNERS["laya"]
    if isinstance(runner, LayaRunner) and runner.warmed:
        return True, "In memory"
    if isinstance(runner, LayaRunner) and runner.warm_error:
        return False, "Load failed"
    try:
        import laya  # noqa: F401
    except ImportError:
        return False, "Not installed"
    return True, "Loading at startup"


def get_runner(model_id: str) -> ModelRunner:
    try:
        return _RUNNERS[model_id]
    except KeyError as exc:
        raise ValueError(f"Unknown model: {model_id}.") from exc


async def run_models(model_ids: list[str], state: Any, questions: list[dict]) -> list[dict]:
    runners = [get_runner(model_id) for model_id in model_ids]
    return list(
        await asyncio.gather(
            *[asyncio.to_thread(runner.run, state, questions) for runner in runners]
        )
    )


def public_error(exc: Exception) -> str:
    message = f"{exc.__class__.__name__}: {exc}"
    secret = os.environ.get("JEV_APIKEY") or ""
    if secret:
        message = message.replace(secret, "[redacted]")
    return message

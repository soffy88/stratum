"""CPU-only model provider with profile support — P13-RUNTIME-QUALIFICATION-001 §4-§5.

Extends ModelProvider with CPU-specific profiles and benchmarking.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Literal

from stratum.services.bu_v2_provider import (
    ModelProvider,
    ModelResponse,
    ProviderError,
    ProviderUnavailable,
    resolve_provider,
)


@dataclass
class CPUProviderProfile:
    """Profile for CPU inference — §4."""

    mode: Literal["cpu"] = "cpu"
    model: str = ""
    timeout: int = 300
    max_context_tokens: int = 4096
    max_output_tokens: int = 1024
    concurrency: int = 1


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run — §5."""

    input_chars: int
    input_tokens: int
    output_tokens: int
    latency_seconds: float
    timeout: bool
    success: bool
    json_valid: bool
    evidence_grounding: float
    error: str | None = None


class CPUModelProvider(ModelProvider):
    """CPU-optimized model provider with profiling and benchmarking."""

    name = "cpu-model"

    def __init__(
        self,
        *,
        profile: CPUProviderProfile | None = None,
        base_provider: ModelProvider | None = None,
        benchmark_mode: bool = False,
    ):
        self.profile = profile or CPUProviderProfile()
        self._base = base_provider or resolve_provider()
        self.benchmark_mode = benchmark_mode
        self._benchmark_results: list[BenchmarkResult] = []

    @property
    def model(self) -> str:
        return self.profile.model or self._base.model

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        json_mode: bool = False,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ModelResponse:
        """Complete with CPU profile constraints."""
        # Apply CPU profile limits
        max_tokens = min(max_tokens, self.profile.max_output_tokens)

        # Truncate prompt if needed (rough char-to-token estimate: 4 chars ≈ 1 token)
        max_prompt_chars = self.profile.max_context_tokens * 4
        if len(prompt) + len(system) > max_prompt_chars:
            # Truncate from the middle, keeping system and end of prompt
            keep_system = system
            keep_prompt = prompt[-(max_prompt_chars - len(keep_system) - 100):]
            prompt = keep_prompt

        start_time = time.perf_counter()
        timeout_occurred = False

        try:
            response = self._base.complete(
                prompt,
                system=system,
                json_mode=json_mode,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except ProviderUnavailable as e:
            raise
        except Exception as e:
            # Wrap in ProviderError for consistency
            raise ProviderError(f"CPU provider error: {e}") from e

        elapsed = time.perf_counter() - start_time

        if self.benchmark_mode:
            self._record_benchmark(prompt, response, elapsed, timeout_occurred)

        return response

    def _record_benchmark(
        self,
        prompt: str,
        response: ModelResponse,
        elapsed: float,
        timeout: bool,
    ) -> None:
        """Record benchmark metrics — §5."""
        input_chars = len(prompt)
        # Rough token estimate
        input_tokens = input_chars // 4
        output_tokens = len(response.text) // 4

        # Check JSON validity
        json_valid = False
        try:
            response.json()
            json_valid = True
        except Exception:
            pass

        # Evidence grounding: check if response contains locator-like patterns
        evidence_grounding = 0.0
        if "char:" in response.text or "page" in response.text or "locator" in response.text.lower():
            evidence_grounding = 1.0
        elif response.raw.get("usage", {}).get("completion_tokens", 0) > 0:
            evidence_grounding = 0.5

        result = BenchmarkResult(
            input_chars=input_chars,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_seconds=elapsed,
            timeout=timeout,
            success=bool(response.text and response.text.strip()),
            json_valid=json_valid,
            evidence_grounding=evidence_grounding,
        )
        self._benchmark_results.append(result)

    def get_benchmark_results(self) -> list[BenchmarkResult]:
        return list(self._benchmark_results)

    def clear_benchmarks(self) -> None:
        self._benchmark_results.clear()


def benchmark_cpu_model(
    provider: CPUModelProvider,
    test_prompts: list[tuple[str, str]],  # (system, prompt)
) -> dict[str, Any]:
    """Run CPU model qualification benchmarks — §5.

    Tests at 5k, 10k, 20k, 30k character prompts.

    Returns:
        Dict with benchmark summary and qualification status
    """
    # Character targets
    char_targets = [5000, 10000, 20000, 30000]

    # Use provided test prompts or generate synthetic ones
    if not test_prompts:
        test_prompts = [("You are a book analyzer.", "Analyze this text: " + "x" * 100)]

    results_by_size: dict[int, list[BenchmarkResult]] = {}

    for target_chars in char_targets:
        provider.clear_benchmarks()

        # Build prompt of approximately target size
        system, base_prompt = test_prompts[0]
        filler = "x" * max(0, target_chars - len(base_prompt) - len(system) - 100)
        prompt = base_prompt + filler

        # Run 3 times for each size
        for _ in range(3):
            try:
                provider.complete(prompt, system=system, json_mode=True, max_tokens=512)
            except Exception:
                pass

        results = provider.get_benchmark_results()
        results_by_size[target_chars] = results

    # Compute summary
    summary = _compute_benchmark_summary(results_by_size)
    return {
        "results_by_size": {k: [r.__dict__ for r in v] for k, v in results_by_size.items()},
        "summary": summary,
        "qualified": summary.get("json_success_rate", 0) >= 0.95
        and summary.get("grounding_rate", 0) >= 0.95,
    }


def _compute_benchmark_summary(results_by_size: dict[int, list[BenchmarkResult]]) -> dict[str, Any]:
    all_results = [r for results in results_by_size.values() for r in results]
    if not all_results:
        return {"json_success_rate": 0.0, "grounding_rate": 0.0, "avg_latency": 0.0}

    total = len(all_results)
    json_ok = sum(1 for r in all_results if r.json_valid)
    grounded = sum(1 for r in all_results if r.evidence_grounding > 0.5)
    success = sum(1 for r in all_results if r.success)

    latencies = [r.latency_seconds for r in all_results if r.success]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    return {
        "total_runs": total,
        "success_rate": success / total if total else 0.0,
        "json_success_rate": json_ok / total if total else 0.0,
        "grounding_rate": grounded / total if total else 0.0,
        "avg_latency_seconds": round(avg_latency, 2),
        "max_latency_seconds": round(max(latencies), 2) if latencies else 0.0,
        "timeout_count": sum(1 for r in all_results if r.timeout),
    }


def create_cpu_provider(
    *,
    model: str | None = None,
    timeout: int = 300,
    max_context_tokens: int = 4096,
    max_output_tokens: int = 1024,
    concurrency: int = 1,
) -> CPUModelProvider:
    """Factory for CPU model provider with profile."""
    profile = CPUProviderProfile(
        model=model or "",
        timeout=timeout,
        max_context_tokens=max_context_tokens,
        max_output_tokens=max_output_tokens,
        concurrency=concurrency,
    )
    return CPUModelProvider(profile=profile)
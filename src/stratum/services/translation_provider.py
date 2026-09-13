"""External PDFMathTranslate boundary. AGPL implementation is never imported into core."""

from __future__ import annotations
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import importlib.metadata


SUPPORTED_PDF2ZH = frozenset({"2.9.0"})
SUPPORTED_BABELDOC = frozenset({"0.6.2"})


class TranslationRuntimeIncompatible(RuntimeError):
    """The isolated PDF translation runtime is outside the tested contract."""


def verify_translation_runtime(python_executable: str | None = None) -> dict[str, str]:
    """Fail closed unless both external packages match the pinned contract."""
    executable = python_executable or sys.executable
    if executable != sys.executable:
        try:
            completed = subprocess.run(
                [
                    executable,
                    "-c",
                    "import importlib.metadata as m; print(m.version('pdf2zh-next')); print(m.version('babeldoc'))",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise TranslationRuntimeIncompatible(
                f"translation runtime cannot be inspected: {executable}"
            ) from exc
        versions = completed.stdout.strip().splitlines()
    else:
        versions = [
            importlib.metadata.version("pdf2zh-next"),
            importlib.metadata.version("babeldoc"),
        ]
    if (
        len(versions) != 2
        or versions[0] not in SUPPORTED_PDF2ZH
        or versions[1] not in SUPPORTED_BABELDOC
    ):
        raise TranslationRuntimeIncompatible(
            f"unsupported pdf2zh-next/BabelDOC runtime: {versions!r}"
        )
    return {"pdf2zh-next": versions[0], "babeldoc": versions[1], "python": executable}


@dataclass(frozen=True)
class TranslationResult:
    artifact_uri: str
    artifact_hash: str
    provider: str = "PDFMathTranslate"
    model: str | None = None


class TranslationProvider:
    def translate_pdf(
        self,
        source_path: str,
        target_language: str,
        output_path: str,
        *,
        options: dict | None = None,
    ) -> TranslationResult:
        raise NotImplementedError


class PDFMathTranslateProvider(TranslationProvider):
    """CLI adapter; deployments can replace this with an HTTP/MCP adapter."""

    def translate_pdf(
        self,
        source_path: str,
        target_language: str,
        output_path: str,
        *,
        options: dict | None = None,
    ) -> TranslationResult:
        command = shlex.split(os.environ.get("PDFMATH_TRANSLATE_COMMAND", "pdf2zh"))
        if not command:
            raise RuntimeError("PDFMathTranslate command is empty")
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        args = [*command, source_path, "--lang-in", "en", "--lang-out", target_language]
        opts = options or {}
        if opts.get("pages"):
            args += ["--pages", str(opts["pages"])]
        # pdf2zh-next writes named artifacts into an output directory.  Keep
        # that packaging detail inside the adapter; AII stores one immutable
        # artifact URI and never imports the AGPL implementation.
        next_mode = (
            any(Path(token).name in {"pdf2zh_next", "pdf2zh-next"} for token in command)
            or opts.get("output_mode") == "directory"
        )
        output_target = (output.parent / f".{output.stem}.pdfmath-output") if next_mode else output
        args += ["--output", str(output_target)]
        subprocess.run(args, check=True, timeout=1800)
        if next_mode:
            search_root = output_target
            candidates = sorted(
                search_root.rglob(f"{Path(source_path).stem}.{target_language}.*.pdf")
            )
            if not candidates:
                raise RuntimeError("PDFMathTranslate completed without a translated PDF artifact")
            # Prefer mono output for a stable single-artifact contract.
            selected = next((p for p in candidates if ".mono." in p.name), candidates[0])
            if selected != output:
                shutil.copyfile(selected, output)
        data = output.read_bytes()
        return TranslationResult(
            str(output),
            hashlib.sha256(data).hexdigest(),
            model=os.environ.get("PDFMATH_TRANSLATE_MODEL"),
        )

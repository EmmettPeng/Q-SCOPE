from __future__ import annotations

import os
import resource
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import IO

from .config import settings


class ExternalCommandError(RuntimeError):
    def __init__(self, message: str, code: str = "analysis_failed") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    wall_seconds: float
    peak_rss_kb: int


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (settings.worker_memory_bytes, settings.worker_memory_bytes))
    resource.setrlimit(resource.RLIMIT_CPU, (settings.worker_ttl, settings.worker_ttl))
    resource.setrlimit(resource.RLIMIT_NPROC, (settings.worker_processes, settings.worker_processes))
    resource.setrlimit(
        resource.RLIMIT_FSIZE,
        (settings.max_run_output_bytes, settings.max_run_output_bytes),
    )


def run_external(
    command: list[str],
    *,
    stdout: IO[str] | None = None,
    timeout: int | None = None,
) -> CommandResult:
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            command,
            stdout=stdout or subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            preexec_fn=_limits if os.name == "posix" else None,
        )
        try:
            captured_stdout, stderr = process.communicate(timeout=timeout or settings.worker_ttl)
        except subprocess.TimeoutExpired as error:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.communicate()
            raise ExternalCommandError(
                f"command exceeded {timeout or settings.worker_ttl} seconds",
                "analysis_timeout",
            ) from error
    except OSError as error:
        raise ExternalCommandError(f"unable to execute {command[0]}: {error}") from error
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return CommandResult(
        returncode=process.returncode,
        stdout=captured_stdout or "",
        stderr=stderr or "",
        wall_seconds=time.monotonic() - started,
        peak_rss_kb=int(usage.ru_maxrss),
    )

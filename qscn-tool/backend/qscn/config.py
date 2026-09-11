from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _integer(name: str, default: int) -> int:
    value = int(os.getenv(name, default))
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    builtin_database_dir: Path
    frontend_dir: Path
    redis_url: str
    max_upload_bytes: int
    max_extracted_bytes: int
    max_genomes: int
    max_archive_files: int
    worker_ttl: int
    builtin_examples_dir: Path = Path(__file__).resolve().parents[2] / "examples"
    max_compression_ratio: int = 100
    max_total_sequences: int = 5_000_000
    max_total_residues: int = 10_000_000_000
    max_run_output_bytes: int = 20 * 1024**3
    min_free_bytes: int = 5 * 1024**3
    worker_memory_bytes: int = 8 * 1024**3
    worker_processes: int = 64
    build_revision: str = "unknown"
    build_timestamp: str = "unknown"

    @classmethod
    def from_env(cls) -> "Settings":
        package_root = Path(__file__).resolve().parents[2]
        return cls(
            data_dir=Path(os.getenv("QSCN_DATA_DIR", package_root / "qscn-data")).resolve(),
            builtin_database_dir=Path(
                os.getenv("QSCN_BUILTIN_DATABASE_DIR", package_root / "databases")
            ).resolve(),
            builtin_examples_dir=Path(
                os.getenv("QSCN_BUILTIN_EXAMPLES_DIR", package_root / "examples")
            ).resolve(),
            frontend_dir=Path(
                os.getenv("QSCN_FRONTEND_DIR", package_root / "frontend-dist")
            ).resolve(),
            redis_url=os.getenv("QSCN_REDIS_URL", "redis://localhost:6379/0"),
            max_upload_bytes=_integer("QSCN_MAX_UPLOAD_BYTES", 2 * 1024**3),
            max_extracted_bytes=_integer("QSCN_MAX_EXTRACTED_BYTES", 10 * 1024**3),
            max_genomes=_integer("QSCN_MAX_GENOMES", 1000),
            max_archive_files=_integer("QSCN_MAX_ARCHIVE_FILES", 2000),
            worker_ttl=_integer("QSCN_WORKER_TTL", 24 * 60 * 60),
            max_compression_ratio=_integer("QSCN_MAX_COMPRESSION_RATIO", 100),
            max_total_sequences=_integer("QSCN_MAX_TOTAL_SEQUENCES", 5_000_000),
            max_total_residues=_integer("QSCN_MAX_TOTAL_RESIDUES", 10_000_000_000),
            max_run_output_bytes=_integer("QSCN_MAX_RUN_OUTPUT_BYTES", 20 * 1024**3),
            min_free_bytes=_integer("QSCN_MIN_FREE_BYTES", 5 * 1024**3),
            worker_memory_bytes=_integer("QSCN_WORKER_MEMORY_BYTES", 8 * 1024**3),
            worker_processes=_integer("QSCN_WORKER_PROCESSES", 64),
            build_revision=os.getenv("QSCN_BUILD_REVISION", "unknown"),
            build_timestamp=os.getenv("QSCN_BUILD_TIMESTAMP", "unknown"),
        )

    def ensure_directories(self) -> None:
        for directory in (
            self.data_dir,
            self.projects_dir,
            self.custom_databases_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"

    @property
    def custom_databases_dir(self) -> Path:
        return self.data_dir / "databases"

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "qscn.sqlite3"


settings = Settings.from_env()

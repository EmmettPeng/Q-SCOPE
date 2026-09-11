from __future__ import annotations

import json
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from redis import Redis
from rq import Queue, Worker
from rq.command import send_stop_job_command
from rq.job import Job

from . import SCHEMA_VERSION, __release__, __version__
from . import db
from .config import settings
from .completeness import validate_rules
from .databases import (
    DatabaseError,
    COMPONENT_TABLE_TEMPLATE,
    PATHWAY_TABLE_TEMPLATE,
    GUIDANCE_TABLE_TEMPLATE,
    delete_database,
    database_profile_summaries,
    get_database,
    import_custom_database,
    import_tabular_database,
    list_databases,
    load_manifest,
    register_builtins,
)
from .inputs import InputError, preflight_archive, rename_sample
from .examples import install_default_examples, list_examples, restore_pd10
from .pipeline import (
    build_export,
    create_interpretation,
    execute_run,
    get_completed_export,
    get_export_status,
    get_interpretation_artifact,
    mark_export_queued,
    project_dir,
)
from .result_views import (
    load_result,
    load_result_summary,
    result_summary,
    run_annotations,
    run_capabilities,
    run_edges,
    run_paged_hits,
)
from .schemas import (
    ANALYSIS_SCOPE_VERSION,
    CAPABILITY_RULE_VERSION,
    HIT_RULE_VERSION,
    InterpretationRequest,
    PreflightRequest,
    RenameInterpretationRequest,
    RenameSampleRequest,
    RunRequest,
)
from .scope import all_scope, normalize_scope
from .storage import ensure_storage_budget, sha256_file, write_json


PUBLIC_ERROR_CODES = {
    "project_zip_required", "upload_too_large", "project_not_found",
    "input_validation_failed", "invalid_sample_name", "active_run_blocks_delete",
    "project_not_ready", "input_kind_mismatch", "database_not_found",
    "ga_override_not_allowed", "conflicting_threshold_overrides",
    "invalid_capability_rules", "run_not_found", "run_not_active",
    "worker_unavailable", "run_not_complete", "results_not_found",
    "interpretation_not_found", "artifact_not_found", "database_zip_required",
    "database_files_required", "database_metadata_invalid", "database_table_invalid",
    "database_profile_mismatch", "database_threshold_invalid", "database_version_conflict",
    "database_guidance_invalid", "database_component_invalid",
    "database_bundle_too_large", "database_import_failed", "database_delete_blocked",
    "invalid_request", "analysis_failed", "stored_run_failed",
    "invalid_analysis_scope",
    "archive_compression_ratio_exceeded", "archive_resource_limit_exceeded",
    "sample_name_conflict", "ambiguous_sequence_alphabet", "disk_space_insufficient",
    "analysis_timeout", "incompatible_schema", "analysis_interrupted",
    "export_not_ready", "export_failed", "invalid_export_mode", "example_unavailable",
}


def _public_project(row: dict[str, Any]) -> dict[str, Any]:
    decoded = db.decode_project(row)
    decoded.pop("archive_path", None)
    for sample in decoded["samples"]:
        sample.pop("fasta_path", None)
    return decoded


def _public_run_row(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    diagnostic = result.pop("error", None)
    if diagnostic and not result.get("error_code"):
        result["error_code"] = "stored_run_failed"
    params = result.pop("error_params_json", None)
    result["error_params"] = json.loads(params) if params else {}
    thresholds = result.pop("hit_thresholds_json", None)
    result["hit_thresholds"] = json.loads(thresholds) if thresholds else None
    scope = result.pop("analysis_scope_json", None)
    result["analysis_scope"] = json.loads(scope) if scope else all_scope()
    result["progress_detail"] = _run_progress_detail(result)
    return result


def _interpretation_summary(rules: list[dict[str, Any]], scope: dict[str, Any]) -> str:
    scope_count = len(scope.get("resolved_pathway_ids") or scope.get("requested_values") or [])
    scope_label = "All pathways" if scope.get("mode") == "all" else f"{scope_count} scoped pathways"
    custom = sum(rule.get("strategy") == "required_profiles" for rule in rules)
    return f"{scope_label} · {'Strict' if not custom else f'{custom} custom criteria'}"


def _public_interpretation(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result.pop("result_path", None)
    rules = json.loads(result.pop("capability_rules_json"))
    scope = json.loads(result.pop("analysis_scope_json", "{}")) or all_scope()
    result["capability_rules"] = rules
    result["analysis_scope"] = scope
    result["automatic_summary"] = _interpretation_summary(rules, scope)
    result["display_name"] = result.get("name") or result["automatic_summary"]
    return result


def _run_progress_detail(run: dict[str, Any]) -> dict[str, Any]:
    stage = str(run.get("stage") or "queued")
    phase = stage.split(":", 1)[0]
    current_sample_id = stage.split(":", 1)[1] if ":" in stage else None
    project = db.get("projects", run["project_id"])
    samples = json.loads(project.get("samples_json") or "[]") if project else []
    total_samples = len(samples)
    progress = float(run.get("progress") or 0)
    ranges = {
        "queued": (0.0, 0.03),
        "preparing": (0.0, 0.05),
        "predicting": (0.05, 0.30),
        "reusing_predictions": (0.05, 0.30),
        "scanning": (0.30, 0.85) if run.get("input_kind") == "genome" else (0.05, 0.85),
        "interpreting": (0.85, 1.0),
        "complete": (1.0, 1.0),
        "cancelled": (progress, progress),
    }
    start, end = ranges.get(phase, (progress, progress))
    phase_progress = 1.0 if phase == "complete" else (
        0.0 if end <= start else max(0.0, min((progress - start) / (end - start), 1.0))
    )
    completed_samples = 0
    if phase in {"predicting", "reusing_predictions"}:
        completed_samples = min(total_samples, int(phase_progress * total_samples + 1e-9))
    elif phase == "scanning":
        completed_samples = min(total_samples, int(phase_progress * total_samples + 1e-9))
    if phase in {"interpreting", "complete"}:
        completed_samples = total_samples
    return {
        "phase": phase,
        "phase_progress": phase_progress,
        "current_sample_id": current_sample_id,
        "completed_samples": completed_samples,
        "total_samples": total_samples,
    }


def _error(status_code: int, code: str, **params: Any) -> HTTPException:
    if code not in PUBLIC_ERROR_CODES:
        raise ValueError(f"unregistered public error code: {code}")
    return HTTPException(status_code=status_code, detail={"code": code, "params": params})


def _queue() -> Queue:
    return Queue("qscn", connection=Redis.from_url(settings.redis_url), default_timeout=settings.worker_ttl)


def _enqueue(run_id: str) -> str:
    try:
        job = _queue().enqueue(execute_run, run_id, job_timeout=settings.worker_ttl, result_ttl=86400)
    except Exception as error:
        db.update(
            "runs",
            run_id,
            {
                "status": "failed",
                "stage": "queue_failed",
                "error": str(error)[:4000],
                "error_code": "worker_unavailable",
                "error_params_json": "{}",
            },
        )
        raise _error(503, "worker_unavailable") from error
    db.update("runs", run_id, {"rq_job_id": job.id})
    return job.id


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.ensure_directories()
    db.initialize()
    register_builtins()
    try:
        install_default_examples()
    except Exception:
        # An optional example must never prevent access to user-owned projects.
        pass
    reconcile_interrupted_runs()
    yield


def reconcile_interrupted_runs() -> None:
    try:
        connection = Redis.from_url(settings.redis_url)
        active_statuses = {"queued", "deferred", "scheduled", "started"}
        for interrupted in db.list_rows("runs", "status='running'"):
            active = False
            try:
                active = bool(
                    interrupted.get("rq_job_id")
                    and Job.fetch(interrupted["rq_job_id"], connection=connection).get_status(refresh=True)
                    in active_statuses
                )
            except Exception:
                active = False
            if not active:
                db.update(
                    "runs", interrupted["id"],
                    {
                        "status": "failed", "stage": "interrupted",
                        "progress": interrupted["progress"],
                        "error": "Analysis interrupted: no active worker job remained after Q-SCOPE restarted.",
                        "error_code": "analysis_interrupted", "error_params_json": "{}",
                    },
                )
    except Exception:
        # Readiness reports Redis/worker failures. Startup remains possible so
        # users can inspect and export completed local results.
        return


app = FastAPI(
    title="Q-SCOPE Local API",
    version=__version__,
    description="Local API for evidence-first analysis of potential quorum-sensing communication",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def request_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
    code = "invalid_analysis_scope" if any("analysis_scope" in item["loc"] for item in error.errors()) else "invalid_request"
    return JSONResponse(
        status_code=422,
        content={"detail": {"code": code, "params": {}}},
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok", "version": __version__, "release": __release__,
        "schema_version": SCHEMA_VERSION, "build_revision": settings.build_revision,
        "build_timestamp": settings.build_timestamp,
    }


@app.get("/api/readiness")
def readiness(response: Response) -> dict[str, Any]:
    checks: dict[str, bool] = {"sqlite": False, "redis": False, "worker": False, "databases": False}
    try:
        with db.connect() as connection:
            row = connection.execute(
                "SELECT value FROM application_metadata WHERE key='schema_version'"
            ).fetchone()
            checks["sqlite"] = bool(row and row["value"] == SCHEMA_VERSION)
    except Exception:
        pass
    try:
        redis = Redis.from_url(settings.redis_url)
        checks["redis"] = bool(redis.ping())
        checks["worker"] = bool(Worker.all(connection=redis))
    except Exception:
        pass
    try:
        registered = list_databases()
        checks["databases"] = bool(registered) and all(
            all(Path(db.get("databases", item["version_id"])["hmm_path"] + suffix).is_file()
                for suffix in (".h3f", ".h3i", ".h3m", ".h3p"))
            for item in registered
        )
    except Exception:
        pass
    ready = all(checks.values())
    response.status_code = 200 if ready else 503
    return {"status": "ready" if ready else "not_ready", "checks": checks}


@app.get("/api/projects")
def projects() -> list[dict[str, Any]]:
    return [_public_project(row) for row in db.list_rows("projects")]


@app.get("/api/examples")
def examples() -> list[dict[str, Any]]:
    return list_examples()


@app.post("/api/examples/pd10/restore", status_code=201)
def restore_pd10_example(response: Response) -> dict[str, Any]:
    already_installed = list_examples()[0]["installed"]
    try:
        restored = restore_pd10()
    except (FileNotFoundError, RuntimeError) as error:
        raise _error(503, "example_unavailable") from error
    if already_installed:
        response.status_code = 200
    return _public_project(restored)


@app.post("/api/projects", status_code=201)
async def create_project(name: str, archive: UploadFile = File(...)) -> dict[str, Any]:
    if not archive.filename or not archive.filename.lower().endswith(".zip"):
        raise _error(400, "project_zip_required")
    project_id = str(uuid.uuid4())
    target_dir = project_dir(project_id)
    target_dir.mkdir(parents=True)
    archive_path = target_dir / "input.zip"
    size = 0
    try:
        ensure_storage_budget(target_dir)
        with archive_path.open("wb") as output:
            while chunk := await archive.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise _error(413, "upload_too_large")
                output.write(chunk)
        timestamp = db.now()
        db.insert(
            "projects",
            {
                "id": project_id,
                "name": name.strip() or Path(archive.filename).stem,
                "archive_path": str(archive_path),
                "archive_sha256": sha256_file(archive_path),
                "input_kind": None,
                "status": "uploaded",
                "samples_json": None,
                "origin": "user",
                "example_id": None,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        )
    except Exception:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise
    return _public_project(db.get("projects", project_id) or {})


@app.post("/api/projects/{project_id}/preflight")
def preflight(project_id: str, request: PreflightRequest) -> dict[str, Any]:
    project = db.get("projects", project_id)
    if not project:
        raise _error(404, "project_not_found")
    try:
        samples = preflight_archive(
            Path(project["archive_path"]), project_dir(project_id) / "input", request.input_kind
        )
    except InputError as error:
        db.update("projects", project_id, {"status": "invalid"})
        raise _error(400, error.code) from error
    db.update(
        "projects",
        project_id,
        {
            "input_kind": request.input_kind.value,
            "samples_json": json.dumps(samples, ensure_ascii=False),
            "status": "ready",
        },
    )
    return _public_project(db.get("projects", project_id) or {})


@app.patch("/api/projects/{project_id}/samples/{sample_id}")
def update_sample(project_id: str, sample_id: str, request: RenameSampleRequest) -> dict[str, Any]:
    project = db.get("projects", project_id)
    if not project:
        raise _error(404, "project_not_found")
    try:
        samples = rename_sample(json.loads(project["samples_json"] or "[]"), sample_id, request.display_name)
    except InputError as error:
        raise _error(400, "invalid_sample_name") from error
    db.update("projects", project_id, {"samples_json": json.dumps(samples, ensure_ascii=False)})
    return _public_project(db.get("projects", project_id) or {})


@app.delete("/api/projects/{project_id}", status_code=204, response_class=Response)
def remove_project(project_id: str) -> Response:
    project = db.get("projects", project_id)
    if not project:
        raise _error(404, "project_not_found")
    active = db.list_rows("runs", "project_id=? AND status IN ('queued','running')", (project_id,))
    if active:
        raise _error(409, "active_run_blocks_delete")
    db.delete("projects", project_id)
    shutil.rmtree(project_dir(project_id), ignore_errors=True)
    return Response(status_code=204)


@app.get("/api/projects/{project_id}/runs")
def project_runs(project_id: str) -> list[dict[str, Any]]:
    if not db.get("projects", project_id):
        raise _error(404, "project_not_found")
    return [
        _public_run_row(row)
        for row in db.list_rows("runs", "project_id=?", (project_id,))
    ]


@app.get("/api/projects/{project_id}/analysis-tree")
def project_analysis_tree(project_id: str) -> dict[str, Any]:
    if not db.get("projects", project_id):
        raise _error(404, "project_not_found")
    database_rows = {row["version_id"]: row for row in db.list_rows("databases")}
    groups: dict[str, dict[str, Any]] = {}
    for raw_run in db.list_rows("runs", "project_id=?", (project_id,)):
        version_id = raw_run["database_version_id"]
        database = database_rows.get(version_id, {})
        group = groups.setdefault(version_id, {
            "database_version_id": version_id,
            "database_id": database.get("database_id", "unknown"),
            "name": database.get("name", version_id),
            "version": database.get("version", "unknown"),
            "runs": [],
        })
        run = _public_run_row(raw_run)
        run["capability_rules"] = json.loads(run.pop("capability_rules_json"))
        run["interpretations"] = [
            _public_interpretation(row)
            for row in db.list_rows("interpretations", "run_id=?", (run["id"],))
        ]
        group["runs"].append(run)
    ordered = sorted(
        groups.values(),
        key=lambda item: max((run["created_at"] for run in item["runs"]), default=""),
        reverse=True,
    )
    return {"project_id": project_id, "databases": ordered}


@app.post("/api/projects/{project_id}/runs", status_code=202)
def create_run(project_id: str, request: RunRequest) -> dict[str, Any]:
    project = db.get("projects", project_id)
    if not project:
        raise _error(404, "project_not_found")
    if project["status"] != "ready" or not project["samples_json"]:
        raise _error(409, "project_not_ready")
    if project["input_kind"] != request.input_kind.value:
        raise _error(400, "input_kind_mismatch")
    try:
        database = get_database(request.database_version_id)
    except DatabaseError as error:
        raise _error(404, "database_not_found") from error
    manifest = load_manifest(database)
    if database["threshold_type"] == "ga":
        if request.sequence_evalue_override is not None or request.hit_thresholds_override is not None:
            raise _error(400, "ga_override_not_allowed")
        sequence_evalue = None
        hit_thresholds = None
    else:
        if request.sequence_evalue_override is not None and request.hit_thresholds_override is not None:
            raise _error(400, "conflicting_threshold_overrides")
        if request.hit_thresholds_override is not None:
            hit_thresholds = request.hit_thresholds_override.model_dump(mode="json")
        elif request.sequence_evalue_override is not None:
            hit_thresholds = {
                "full_evalue_max": request.sequence_evalue_override,
                "domain_i_evalue_max": request.sequence_evalue_override,
            }
        else:
            policy = manifest.threshold_policy
            hit_thresholds = {
                "full_evalue_max": policy.default_full_evalue,
                "domain_i_evalue_max": policy.default_domain_i_evalue,
            }
        sequence_evalue = hit_thresholds["full_evalue_max"]
    try:
        rules = validate_rules(manifest, request.capability_rules)
    except ValueError as error:
        raise _error(400, "invalid_capability_rules") from error
    try:
        analysis_scope = normalize_scope(manifest, request.analysis_scope)
    except ValueError as error:
        raise _error(400, "invalid_analysis_scope") from error
    run_id = str(uuid.uuid4())
    timestamp = db.now()
    run_values = {
            "id": run_id,
            "project_id": project_id,
            "database_version_id": request.database_version_id,
            "input_kind": request.input_kind.value,
            "completeness_mode": "v2",
            "capability_rule_version": CAPABILITY_RULE_VERSION,
            "capability_rules_json": json.dumps(
                [rule.model_dump(mode="json") for rule in rules], ensure_ascii=False
            ),
            "sequence_evalue": sequence_evalue,
            "hit_rule_version": HIT_RULE_VERSION,
            "hit_thresholds_json": json.dumps(hit_thresholds) if hit_thresholds else None,
            "analysis_scope_version": ANALYSIS_SCOPE_VERSION,
            "analysis_scope_json": json.dumps(analysis_scope, ensure_ascii=False),
            "status": "queued",
            "stage": "queued",
            "progress": 0,
            "rq_job_id": None,
            "error": None,
            "error_code": None,
            "error_params_json": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    db.insert("runs", run_values)
    _enqueue(run_id)
    return get_run(run_id)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    run = db.get("runs", run_id)
    if not run:
        raise _error(404, "run_not_found")
    run = _public_run_row(run)
    run["interpretations"] = [
        _public_interpretation(row)
        for row in db.list_rows("interpretations", "run_id=?", (run_id,))
    ]
    run["capability_rules"] = json.loads(run.pop("capability_rules_json"))
    return run


@app.post("/api/runs/{run_id}/cancel")
def cancel_run(run_id: str) -> dict[str, Any]:
    run = db.get("runs", run_id)
    if not run:
        raise _error(404, "run_not_found")
    if run["status"] not in {"queued", "running"}:
        raise _error(409, "run_not_active")
    try:
        if run["rq_job_id"]:
            connection = Redis.from_url(settings.redis_url)
            job = Job.fetch(run["rq_job_id"], connection=connection)
            if job.get_status(refresh=True) in {"queued", "deferred", "scheduled"}:
                job.cancel()
            else:
                send_stop_job_command(connection, run["rq_job_id"])
    except Exception as error:
        raise _error(503, "worker_unavailable") from error
    db.update("runs", run_id, {"status": "cancelled", "stage": "cancelled", "error": None})
    return get_run(run_id)


@app.post("/api/runs/{run_id}/retry", status_code=202)
def retry_run(run_id: str) -> dict[str, Any]:
    old = db.get("runs", run_id)
    if not old:
        raise _error(404, "run_not_found")
    request = RunRequest(
        input_kind=old["input_kind"],
        database_version_id=old["database_version_id"],
        capability_rules=json.loads(old["capability_rules_json"]),
        hit_thresholds_override=(
            json.loads(old["hit_thresholds_json"])
            if old.get("hit_thresholds_json")
            else (
                {
                    "full_evalue_max": old["sequence_evalue"],
                    "domain_i_evalue_max": old["sequence_evalue"],
                }
                if old.get("sequence_evalue")
                else None
            )
        ),
        analysis_scope=json.loads(old["analysis_scope_json"]) if old.get("analysis_scope_json") else None,
    )
    return create_run(old["project_id"], request)


@app.post("/api/runs/{run_id}/interpretations", status_code=201)
def reinterpret(run_id: str, request: InterpretationRequest) -> dict[str, Any]:
    run = db.get("runs", run_id)
    if not run:
        raise _error(404, "run_not_found")
    if run["status"] != "complete":
        raise _error(409, "run_not_complete")
    try:
        return result_summary(create_interpretation(
            run_id,
            request.capability_rules,
            request.analysis_scope.model_dump(mode="json") if request.analysis_scope else None,
            request.name,
        ))
    except ValueError as error:
        message = str(error)
        code = "invalid_analysis_scope" if "scope" in message or "pathway IDs" in message or "signal names" in message else "invalid_capability_rules"
        raise _error(400, code) from error


@app.patch("/api/runs/{run_id}/interpretations/{interpretation_id}")
def rename_interpretation(
    run_id: str, interpretation_id: str, request: RenameInterpretationRequest
) -> dict[str, Any]:
    interpretation = db.get("interpretations", interpretation_id)
    if not interpretation or interpretation["run_id"] != run_id:
        raise _error(404, "interpretation_not_found")
    db.update("interpretations", interpretation_id, {"name": request.name})
    updated = db.get("interpretations", interpretation_id) or {}
    manifest_path = Path(updated["result_path"]).parent / "interpretation_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {
        "interpretation_id": interpretation_id,
        "run_id": run_id,
        "created_at": updated["created_at"],
    }
    manifest.update({"name": request.name, "updated_at": updated["updated_at"]})
    write_json(manifest_path, manifest)
    return _public_interpretation(updated)


@app.get("/api/runs/{run_id}/results")
def results(
    run_id: str,
    interpretation_id: str | None = Query(default=None),
    summary: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        return load_result_summary(run_id, interpretation_id) if summary else load_result(run_id, interpretation_id)
    except ValueError as error:
        raise _error(404, "results_not_found") from error


@app.get("/api/runs/{run_id}/results/capabilities")
def result_capabilities(
    run_id: str,
    interpretation_id: str,
    min_hmm_coverage: float = Query(default=0, ge=0, le=1),
    min_sequence_coverage: float = Query(default=0, ge=0, le=1),
    include_partial: bool = Query(default=True),
    biological_rule_id: str = Query(default=""),
) -> dict[str, Any]:
    try:
        return run_capabilities(
            run_id, interpretation_id, min_hmm_coverage, min_sequence_coverage,
            include_partial, biological_rule_id,
        )
    except ValueError as error:
        raise _error(404, "results_not_found") from error


@app.get("/api/runs/{run_id}/results/network-edges")
def result_network_edges(
    run_id: str,
    interpretation_id: str,
    min_hmm_coverage: float = Query(default=0, ge=0, le=1),
    min_sequence_coverage: float = Query(default=0, ge=0, le=1),
    include_partial: bool = Query(default=True),
    biological_rule_id: str = Query(default=""),
) -> dict[str, Any]:
    try:
        return run_edges(
            run_id, interpretation_id, min_hmm_coverage, min_sequence_coverage,
            include_partial, biological_rule_id,
        )
    except ValueError as error:
        raise _error(404, "results_not_found") from error


@app.get("/api/runs/{run_id}/results/annotations")
def result_annotations(run_id: str, interpretation_id: str) -> dict[str, Any]:
    try:
        return run_annotations(run_id, interpretation_id)
    except ValueError as error:
        raise _error(404, "results_not_found") from error


@app.get("/api/runs/{run_id}/results/hits")
def result_hits(
    run_id: str,
    interpretation_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=500),
    profile_id: list[str] | None = Query(default=None),
    min_hmm_coverage: float = Query(default=0, ge=0, le=1),
    min_sequence_coverage: float = Query(default=0, ge=0, le=1),
    include_partial: bool = Query(default=True),
    biological_rule_id: str = Query(default=""),
) -> dict[str, Any]:
    try:
        return run_paged_hits(
            run_id, interpretation_id, offset, limit, profile_id or [],
            min_hmm_coverage, min_sequence_coverage,
            include_partial, biological_rule_id,
        )
    except ValueError as error:
        raise _error(404, "results_not_found") from error


def _start_export(run_id: str, interpretation_id: str, mode: str) -> dict[str, Any]:
    if mode not in {"analysis", "full"}:
        raise _error(400, "invalid_export_mode")
    try:
        status = get_export_status(run_id, interpretation_id, mode)
    except ValueError as error:
        raise _error(404, "interpretation_not_found") from error
    if status["status"] in {"queued", "running", "complete"}:
        return status
    try:
        job = _queue().enqueue(
            build_export,
            run_id,
            interpretation_id,
            mode,
            job_timeout=settings.worker_ttl,
            result_ttl=86400,
        )
    except Exception as error:
        raise _error(503, "worker_unavailable") from error
    return mark_export_queued(run_id, interpretation_id, mode, job.id)


@app.post("/api/runs/{run_id}/exports", status_code=202)
def start_export(run_id: str, interpretation_id: str, mode: str = Query(default="analysis")) -> dict[str, Any]:
    return _start_export(run_id, interpretation_id, mode)


@app.get("/api/runs/{run_id}/exports/status")
def export_status(run_id: str, interpretation_id: str, mode: str = Query(default="analysis")) -> dict[str, Any]:
    if mode not in {"analysis", "full"}:
        raise _error(400, "invalid_export_mode")
    try:
        return get_export_status(run_id, interpretation_id, mode)
    except ValueError as error:
        raise _error(404, "interpretation_not_found") from error


@app.get("/api/runs/{run_id}/exports/download")
def download_export(run_id: str, interpretation_id: str, mode: str = Query(default="analysis")) -> FileResponse:
    if mode not in {"analysis", "full"}:
        raise _error(400, "invalid_export_mode")
    try:
        path = get_completed_export(run_id, interpretation_id, mode)
    except FileNotFoundError as error:
        raise _error(409, "export_not_ready") from error
    except ValueError as error:
        raise _error(404, "interpretation_not_found") from error
    return FileResponse(path, media_type="application/zip", filename=path.name)


@app.get("/api/runs/{run_id}/export")
def legacy_export(run_id: str, interpretation_id: str) -> Response:
    status = _start_export(run_id, interpretation_id, "full")
    if status["status"] == "complete":
        path = get_completed_export(run_id, interpretation_id, "full")
        return FileResponse(path, media_type="application/zip", filename=path.name)
    return JSONResponse(status_code=202, content=status)


@app.get("/api/runs/{run_id}/interpretations/{interpretation_id}/artifacts/{artifact}")
def interpretation_artifact(run_id: str, interpretation_id: str, artifact: str) -> FileResponse:
    try:
        path = get_interpretation_artifact(run_id, interpretation_id, artifact)
    except ValueError as error:
        raise _error(404, "artifact_not_found") from error
    return FileResponse(path, media_type="application/octet-stream", filename=artifact)


@app.get("/api/databases")
def databases() -> list[dict[str, Any]]:
    return list_databases()


@app.get("/api/databases/{version_id}/profiles")
def database_profiles(
    version_id: str,
    query: str = Query(default="", max_length=120),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    try:
        return database_profile_summaries(version_id, query, offset, limit)
    except DatabaseError as error:
        raise _error(404, "database_not_found") from error


@app.get("/api/databases/template")
def database_pathway_template() -> Response:
    return Response(
        content=PATHWAY_TABLE_TEMPLATE,
        media_type="text/tab-separated-values; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="qscn-pathways-template.tsv"'},
    )


@app.get("/api/databases/guidance-template")
def database_guidance_template() -> Response:
    return Response(
        content=GUIDANCE_TABLE_TEMPLATE,
        media_type="text/tab-separated-values; charset=utf-8",
        headers={
            "Content-Disposition":
                'attachment; filename="qscn-interpretation-guidance-template.tsv"'
        },
    )


@app.get("/api/databases/component-template")
def database_component_template() -> Response:
    return Response(
        content=COMPONENT_TABLE_TEMPLATE,
        media_type="text/tab-separated-values; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="qscn-component-names-template.tsv"'},
    )


@app.post("/api/databases", status_code=201)
async def create_database(
    archive: UploadFile | None = File(None),
    hmm_file: UploadFile | None = File(None),
    pathway_file: UploadFile | None = File(None),
    guidance_file: UploadFile | None = File(None),
    component_file: UploadFile | None = File(None),
    name: str | None = Form(None),
    version: str | None = Form(None),
    source: str | None = Form(None),
    classification_scheme: str | None = Form(None),
    threshold_type: str | None = Form(None),
    default_full_evalue: str | None = Form(None),
    default_domain_i_evalue: str | None = Form(None),
) -> dict[str, Any]:
    # FastAPI parameter defaults are marker objects when this handler is called
    # directly in unit tests rather than through request injection.
    if guidance_file is not None and not hasattr(guidance_file, "filename"):
        guidance_file = None
    if component_file is not None and not hasattr(component_file, "filename"):
        component_file = None
    legacy_mode = archive is not None
    tabular_mode = any(value is not None for value in (hmm_file, pathway_file, guidance_file, component_file))
    if legacy_mode and tabular_mode:
        raise _error(400, "database_files_required")
    if not legacy_mode and not (hmm_file and pathway_file):
        raise _error(400, "database_files_required")
    if legacy_mode and (not archive.filename or not archive.filename.lower().endswith(".zip")):
        raise _error(400, "database_zip_required")
    if tabular_mode:
        if (
            not hmm_file
            or not hmm_file.filename
            or not hmm_file.filename.lower().endswith(".hmm")
            or not pathway_file
            or not pathway_file.filename
            or Path(pathway_file.filename).suffix.lower() not in {".tsv", ".txt"}
        ):
            raise _error(400, "database_files_required")
        if guidance_file is not None and (
            not guidance_file.filename
            or Path(guidance_file.filename).suffix.lower() not in {".tsv", ".txt"}
        ):
            raise _error(400, "database_guidance_invalid", reason="file_type")
        if component_file is not None and (
            not component_file.filename
            or Path(component_file.filename).suffix.lower() not in {".tsv", ".txt"}
        ):
            raise _error(400, "database_component_invalid", reason="file_type")
        if not name or not name.strip() or not version or not version.strip() or threshold_type not in {"ga", "evalue"}:
            raise _error(400, "database_metadata_invalid")
    imports_dir = settings.data_dir / "imports"
    imports_dir.mkdir(parents=True, exist_ok=True)
    import_id = str(uuid.uuid4())
    targets: list[Path] = []
    size = 0

    async def save_upload(upload: UploadFile, target: Path) -> None:
        nonlocal size
        targets.append(target)
        with target.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise _error(413, "database_bundle_too_large")
                output.write(chunk)

    try:
        if legacy_mode:
            target = imports_dir / f"{import_id}.zip"
            await save_upload(archive, target)
            version_id = import_custom_database(target)
        else:
            hmm_target = imports_dir / f"{import_id}.hmm"
            table_suffix = Path(pathway_file.filename).suffix.lower()
            table_target = imports_dir / f"{import_id}{table_suffix}"
            await save_upload(hmm_file, hmm_target)
            await save_upload(pathway_file, table_target)
            guidance_target = None
            if guidance_file:
                guidance_target = imports_dir / f"{import_id}.guidance.tsv"
                await save_upload(guidance_file, guidance_target)
            component_target = None
            if component_file:
                component_target = imports_dir / f"{import_id}.components.tsv"
                await save_upload(component_file, component_target)
            try:
                full_evalue = float(default_full_evalue) if default_full_evalue not in {None, ""} else None
                domain_evalue = float(default_domain_i_evalue) if default_domain_i_evalue not in {None, ""} else None
            except ValueError as error:
                raise _error(400, "database_threshold_invalid") from error
            version_id = import_tabular_database(
                hmm_target,
                table_target,
                guidance_target,
                component_target,
                name=name or "",
                version=version or "",
                source=source or "User provided",
                classification_scheme=classification_scheme or "User-defined classification",
                threshold_type=threshold_type or "",
                default_full_evalue=full_evalue,
                default_domain_i_evalue=domain_evalue,
            )
    except DatabaseError as error:
        raise _error(400, error.public_code, **error.params) from error
    finally:
        for target in targets:
            target.unlink(missing_ok=True)
    return next(item for item in list_databases() if item["version_id"] == version_id)


@app.delete("/api/databases/{version_id:path}", status_code=204, response_class=Response)
def remove_database(version_id: str) -> Response:
    try:
        delete_database(version_id)
    except DatabaseError as error:
        raise _error(409, "database_delete_blocked") from error
    return Response(status_code=204)


if settings.frontend_dir.exists():
    assets = settings.frontend_dir / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{spa_path:path}", include_in_schema=False)
    def spa(spa_path: str) -> FileResponse:
        candidate = settings.frontend_dir / spa_path
        if spa_path and candidate.is_file() and candidate.resolve().is_relative_to(settings.frontend_dir):
            return FileResponse(candidate)
        return FileResponse(settings.frontend_dir / "index.html")

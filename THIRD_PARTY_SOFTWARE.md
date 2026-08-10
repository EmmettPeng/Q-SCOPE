# Third-party software

QSCN builds on FastAPI, Uvicorn, Pydantic, Redis/RQ, React, Cytoscape.js,
pdf-lib, Vite, HMMER, Prodigal, Python, Node.js, and the Debian/Alpine base
distributions. Each component remains under its own license.

The direct Python requirements are in `backend/requirements.txt`; the complete
resolved Python environment is `backend/requirements.lock`. The remaining
authoritative dependency versions are
`frontend/package-lock.json`, the pinned image digests in `Dockerfile`, and the
Redis image digest in `docker-compose.yml`. A release candidate must retain
the license files included by those distributions and record dependency and
container vulnerability scan results in its GitHub Actions run and release.

The Compose runtime is pinned to Redis 7.2.4, the last Redis release line
distributed under the BSD 3-Clause license. Do not move this pin to Redis 7.4+
without a new license and distribution review.

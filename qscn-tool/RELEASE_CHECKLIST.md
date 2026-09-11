# Q-SCOPE v1.0.0 release checklist

Status values are `PASS`, `FAIL`, `BLOCKED`, `PARTIAL`, or `NOT RUN`. Publication
requires every blocking gate to be `PASS`.

| Gate | Status | Evidence |
|---|---|---|
| Version and schema consistency | PASS | Source and focused tests report Q-SCOPE v1.0.0 / schema 5 |
| Backend unit and integration suite | PASS | 84 tests passed in the Python 3.12 release image |
| Frontend unit tests | PASS | 22 tests passed |
| TypeScript/Vite production build | PASS | Production build passed; known large-chunk warning remains |
| Frontend high-severity dependency audit | PASS | Container `npm ci` audited 84 packages with 0 vulnerabilities |
| Windows launcher syntax and behavior | NOT RUN | Pending |
| macOS and Linux launcher syntax | PASS | Both launchers pass `sh -n` |
| Release package generation and checksums | PASS | Three v1.0.0 packages and SHA256SUMS generated locally |
| amd64 image and database/tool checks | NOT RUN | Pending |
| arm64 image and database/tool checks | PASS | Local arm64 image built; 38 QSP and 281 KEGG profiles indexed; 84 tests passed |
| Compose fresh start and readiness | NOT RUN | Pending |
| Complete browser release flow | NOT RUN | Pending |
| PD10 example installation and restoration | NOT RUN | Pending |
| GHCR multi-architecture manifest | NOT RUN | Requires tagged publication |
| Container vulnerability gate | NOT RUN | Requires release workflow |
| Repository content and large-file audit | NOT RUN | Pending |

# QSCN for macOS

Requirements: Docker Desktop for a supported Intel or Apple Silicon Mac, at
least 16 GB host memory recommended, and 40 GB free disk space recommended.

1. Install and start Docker Desktop.
2. On first launch, control-click `QSCN.command` and choose **Open**, or run
   `./macos/qscn.sh start` in Terminal.
3. QSCN opens at `http://127.0.0.1:8000` after all readiness checks pass.

Useful commands:

```text
./macos/qscn.sh status
./macos/qscn.sh logs
./macos/qscn.sh stop
./macos/qscn.sh update
./macos/qscn.sh backup
./macos/qscn.sh restore /path/to/qscn-backup
```

Edit `.env` to change `QSCN_PORT` or resource limits. Project data and imported
databases remain in named Docker volumes. Normal stop and update operations do
not delete them. Never use `docker compose down -v` unless you intentionally
want to destroy all QSCN data.

To upgrade from v0.3.2, extract the v0.4.0 package to a new directory and copy
your old `.env` only if you customized it. On first launch QSCN removes the
obsolete `QSCN_IMAGE` line and saves the original as `.env.v0.3.2.bak`. Existing
projects remain in `qscn_qscn_v03_data` and `qscn_qscn_v03_redis`.

# Q-SCOPE for Windows

Requirements: Windows 10/11 x64, Docker Desktop using the WSL 2 Linux-container
backend, at least 16 GB host memory recommended, and 40 GB free disk space
recommended.

1. Install and start Docker Desktop with Linux containers enabled.
   A separate Ubuntu or other WSL distribution is not required for Q-SCOPE.
2. Double-click `Q-SCOPE.cmd`, or run `windows\qscn.ps1 start` in PowerShell.
3. Q-SCOPE opens at `http://127.0.0.1:8000` after all readiness checks pass.

Useful commands:

```text
windows\qscn.ps1 status
windows\qscn.ps1 logs
windows\qscn.ps1 stop
windows\qscn.ps1 update
windows\qscn.ps1 backup
windows\qscn.ps1 restore -Path C:\path\to\qscn-backup
```

Edit `.env` to change `QSCN_PORT` or resource limits. Project data and imported
databases remain in named Docker volumes. Normal stop and update operations do
not delete them. Never use `docker compose down -v` unless you intentionally
want to destroy all Q-SCOPE data.

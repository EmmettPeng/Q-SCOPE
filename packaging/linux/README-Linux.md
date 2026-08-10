# QSCN for Ubuntu Linux

Officially tested hosts are Ubuntu 22.04 and 24.04 LTS on amd64 or arm64.
Other Linux distributions may work when they provide a compatible Linux Docker
Engine and Docker Compose v2, but they are not part of the v0.4.0 host matrix.

Recommended host resources are 4 CPU, 16 GB memory, and 40 GB free disk space.

1. Install Docker Engine and Docker Compose v2 from Docker's official Ubuntu
   instructions: https://docs.docker.com/engine/install/ubuntu/
2. Ensure Docker is running and your user can run `docker info`.
3. Run `./linux/QSCN.sh` from the extracted release directory.
4. QSCN opens at `http://127.0.0.1:8000` after all readiness checks pass.

Useful commands:

```text
./linux/QSCN.sh status
./linux/QSCN.sh logs
./linux/QSCN.sh stop
./linux/QSCN.sh update
./linux/QSCN.sh backup
./linux/QSCN.sh restore /path/to/qscn-backup
```

Edit `.env` to change `QSCN_PORT` or resource limits. Project data and imported
databases remain in the named Docker volumes `qscn_qscn_v03_data` and
`qscn_qscn_v03_redis`. Normal stop and update operations do not delete them.
Never use `docker compose down -v` unless you intentionally want to destroy all
QSCN data.

To upgrade from v0.3.2, extract the v0.4.0 package to a new directory and copy
your old `.env` only if you customized it. On first launch QSCN removes the
obsolete `QSCN_IMAGE` line and saves the original as `.env.v0.3.2.bak`. Existing
projects remain in the same named volumes.

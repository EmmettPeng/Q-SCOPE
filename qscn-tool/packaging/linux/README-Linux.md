# Q-SCOPE for Ubuntu Linux

Officially tested hosts are Ubuntu 22.04 and 24.04 LTS on amd64 or arm64.
Other Linux distributions may work when they provide a compatible Linux Docker
Engine and Docker Compose v2, but they are not part of the v1.0.0 host matrix.

Recommended host resources are 4 CPU, 16 GB memory, and 40 GB free disk space.

1. Install Docker Engine and Docker Compose v2 from Docker's official Ubuntu
   instructions: https://docs.docker.com/engine/install/ubuntu/
2. Ensure Docker is running and your user can run `docker info`.
3. Run `./linux/Q-SCOPE.sh` from the extracted release directory.
4. Q-SCOPE opens at `http://127.0.0.1:8000` after all readiness checks pass.

Useful commands:

```text
./linux/Q-SCOPE.sh status
./linux/Q-SCOPE.sh logs
./linux/Q-SCOPE.sh stop
./linux/Q-SCOPE.sh update
./linux/Q-SCOPE.sh backup
./linux/Q-SCOPE.sh restore /path/to/qscn-backup
```

Edit `.env` to change `QSCN_PORT` or resource limits. Project data and imported
databases remain in the named Docker volumes `qscope_data` and
`qscope_redis`. Normal stop and update operations do not delete them.
Never use `docker compose down -v` unless you intentionally want to destroy all
Q-SCOPE data.

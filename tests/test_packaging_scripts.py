import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGING_DIR = ROOT / "packaging"


def write_stub(path: Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")
    path.chmod(0o755)


def run_packaging_script(
    tmp_path: Path,
    script_name: str,
    *args: str,
    getent_exit: int = 0,
    id_exit: int = 0,
    fail_restart: bool = False,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    log_path = tmp_path / "command.log"

    write_stub(
        stub_dir / "getent",
        f"""#!/bin/sh
printf '%s\\n' "getent $*" >> "$COMMAND_LOG"
exit {getent_exit}
""",
    )
    write_stub(
        stub_dir / "id",
        f"""#!/bin/sh
printf '%s\\n' "id $*" >> "$COMMAND_LOG"
exit {id_exit}
""",
    )
    write_stub(
        stub_dir / "addgroup",
        """#!/bin/sh
printf '%s\n' "addgroup $*" >> "$COMMAND_LOG"
exit 0
""",
    )
    write_stub(
        stub_dir / "adduser",
        """#!/bin/sh
printf '%s\n' "adduser $*" >> "$COMMAND_LOG"
exit 0
""",
    )
    restart_exit = 1 if fail_restart else 0
    write_stub(
        stub_dir / "systemctl",
        f"""#!/bin/sh
printf '%s\\n' "systemctl $*" >> "$COMMAND_LOG"
if [ "$1" = "restart" ]; then
    exit {restart_exit}
fi
exit 0
""",
    )

    env = os.environ.copy()
    env["COMMAND_LOG"] = str(log_path)
    env["PATH"] = f"{stub_dir}:{env['PATH']}"

    completed = subprocess.run(
        ["/bin/sh", str(PACKAGING_DIR / script_name), *args],
        capture_output=True,
        text=True,
        env=env,
    )

    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    return completed, log_lines


def test_postinst_initial_install_keeps_service_disabled(tmp_path):
    completed, log_lines = run_packaging_script(
        tmp_path,
        "postinst",
        "configure",
        getent_exit=1,
        id_exit=1,
    )

    assert completed.returncode == 0
    assert "The service is still stopped and disabled." in completed.stdout
    assert "sudoedit /etc/adsb-forwarder/forwarder.env" in completed.stdout
    assert "systemctl daemon-reload" in log_lines
    assert "systemctl restart adsb-forwarder.service" not in log_lines
    assert "addgroup --system adsb-forwarder" in log_lines
    assert (
        "adduser --system --ingroup adsb-forwarder --no-create-home --home /usr/lib/adsb-forwarder "
        "--shell /usr/sbin/nologin adsb-forwarder"
    ) in log_lines


def test_postinst_upgrade_restarts_service(tmp_path):
    completed, log_lines = run_packaging_script(
        tmp_path,
        "postinst",
        "configure",
        "1.2.3",
    )

    assert completed.returncode == 0
    assert completed.stdout == ""
    assert "systemctl daemon-reload" in log_lines
    assert "systemctl restart adsb-forwarder.service" in log_lines


def test_postinst_upgrade_fails_when_restart_fails(tmp_path):
    completed, log_lines = run_packaging_script(
        tmp_path,
        "postinst",
        "configure",
        "1.2.3",
        fail_restart=True,
    )

    assert completed.returncode != 0
    assert "systemctl daemon-reload" in log_lines
    assert "systemctl restart adsb-forwarder.service" in log_lines
    assert "failed to restart adsb-forwarder.service during package upgrade" in completed.stderr


def test_prerm_stops_service_before_upgrade(tmp_path):
    completed, log_lines = run_packaging_script(tmp_path, "prerm", "upgrade")

    assert completed.returncode == 0
    assert "systemctl stop adsb-forwarder.service" in log_lines

import subprocess
import threading
from pathlib import Path
from typing import Callable

from app.db import ROOT_DIR
from app.models import SessionStatus

LOGS_DIR = ROOT_DIR / "logs"
_processes: dict[str, subprocess.Popen] = {}


def start_test_session(session_id: str, on_complete: Callable[[str, SessionStatus], None]) -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"{session_id}.log"

    command = [
        "python",
        "-c",
        "import time; print('SimpleTS session started', flush=True); time.sleep(3); print('SimpleTS session complete', flush=True)",
    ]

    log_file = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT)
    _processes[session_id] = process

    def wait_for_process() -> None:
        try:
            return_code = process.wait()
            status = SessionStatus.COMPLETED if return_code == 0 else SessionStatus.ERRORED
            on_complete(session_id, status)
        finally:
            log_file.close()
            _processes.pop(session_id, None)

    threading.Thread(target=wait_for_process, daemon=True).start()
    return log_path


def stop_session(session_id: str) -> bool:
    process = _processes.get(session_id)
    if not process:
        return False
    process.terminate()
    _processes.pop(session_id, None)
    return True

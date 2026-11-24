import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock


SETTINGS_PATH = Path(__file__).resolve().parents[1] / ".agent-print-settings.json"
_SETTINGS_LOCK = Lock()


def auto_print_enabled() -> bool:
    with _SETTINGS_LOCK:
        try:
            config = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return False
    return config.get("auto_print") is True


def save_auto_print(enabled: bool) -> None:
    with _SETTINGS_LOCK:
        temporary_path = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=SETTINGS_PATH.parent,
                prefix=".agent-print-settings-", suffix=".tmp", delete=False,
            ) as file:
                temporary_path = Path(file.name)
                json.dump({"auto_print": enabled}, file, indent=2)
            temporary_path.replace(SETTINGS_PATH)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

import json
import logging
import re
from pathlib import Path

from django.utils import timezone

from nhcx.settings import plugin_settings

logger = logging.getLogger(__name__)

_FILENAME_SAFE = re.compile(r"[^\w.-]+")


def _sanitize(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return "unknown"
    return _FILENAME_SAFE.sub("_", value)


def _request_log_dir() -> Path:
    logs_root = Path(plugin_settings.LOGS_DIR)
    return logs_root / "requests" / timezone.localdate().isoformat()


def log_fhir_bundle(
    *,
    bundle_type: str,
    workflow_id: str,
    correlation_id: str,
    bundle: dict,
) -> Path | None:
    """
    Persist a decrypted FHIR bundle under
    ``{LOGS_DIR}/requests/{date}/{type}_{workflow_id}_{correlation_id}.json``.

    If that path already exists (e.g. Celery retry), a numeric suffix is appended
    so earlier bundles are never overwritten.

    No-op unless ``NHCX_DEBUG`` is enabled (env var or plugin config).
    """
    if not plugin_settings.NHCX_DEBUG:
        return None

    try:
        directory = _request_log_dir()
        directory.mkdir(parents=True, exist_ok=True)

        base_name = (
            f"{_sanitize(bundle_type)}_{_sanitize(workflow_id)}_{_sanitize(correlation_id)}"
        )
        path = directory / f"{base_name}.json"

        counter = 1
        while path.exists():
            path = directory / f"{base_name}_{counter}.json"
            counter += 1

        with path.open("w", encoding="utf-8") as handle:
            json.dump(bundle, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

        logger.info("Logged FHIR bundle to %s", path)
        return path
    except Exception:
        logger.exception(
            "Failed to log FHIR bundle type=%s correlation_id=%s",
            bundle_type,
            correlation_id,
        )
        return None

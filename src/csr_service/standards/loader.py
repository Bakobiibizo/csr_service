"""Standards set loader.

Scans a directory for JSON files, validates each against the StandardsSet
schema, and returns a dict keyed by standards_set ID. Invalid files are
logged and skipped without affecting other sets.
"""

import json
from pathlib import Path

from ..logging import logger
from ..schemas.standards import StandardsSet


def load_standards(standards_dir: str) -> dict[str, StandardsSet]:
    path = Path(standards_dir)
    if not path.exists():
        logger.warning(f"Standards directory not found: {standards_dir}")
        return {}

    sets: dict[str, StandardsSet] = {}
    for file in sorted(path.glob("*.json")):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            ss = StandardsSet.model_validate(data)
            sets[ss.standards_set] = ss
            logger.info(f"Loaded standards set '{ss.standards_set}' with {len(ss.rules)} rules")
        except Exception as e:
            logger.error(f"Failed to load standards file {file}: {e}")

    return sets

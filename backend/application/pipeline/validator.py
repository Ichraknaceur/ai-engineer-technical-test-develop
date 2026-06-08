"""Validation pipeline step: enforce JSON Schema v2.0.0 on the final record."""

import json
import logging
from functools import lru_cache
from pathlib import Path

import jsonschema

from backend.domain.exceptions import ValidationError

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent.parent.parent / "schemas" / "site_schema.json"


@lru_cache(maxsize=1)
def _load_schema() -> dict:
    """Load and cache the JSON Schema from disk."""
    return json.loads(_SCHEMA_PATH.read_text())


class ValidatorStep:
    """Validates a quarry record dict against JSON Schema v2.0.0.

    Loads the schema from ``backend/schemas/site_schema.json`` once at
    construction time (via lru_cache) and reuses it for every call.

    Raises:
        ValidationError: If the record does not conform to the schema.
                         This is a hard failure — the record must not be persisted.
    """

    def run(self, record: dict) -> dict:
        """Validate the record and return it unchanged if valid.

        Args:
            record: The fully assembled quarry record dict.

        Returns:
            The same record dict, unchanged, if validation passes.

        Raises:
            ValidationError: If any required field is missing or has the wrong type.
        """
        schema = _load_schema()

        try:
            jsonschema.validate(instance=record, schema=schema)
        except jsonschema.ValidationError as exc:
            path = " → ".join(str(p) for p in exc.absolute_path) or "root"
            message = f"Schema validation failed at '{path}': {exc.message}"
            logger.error(message)
            raise ValidationError(message) from exc

        logger.debug("Record %s passed schema validation", record.get("site_id", "?"))
        return record

"""Validation pipeline step: enforce JSON Schema v2.0.0 on the final record."""


class ValidatorStep:
    """Validates a quarry record dict against JSON Schema v2.0.0.

    Loads the schema from ``backend/schemas/site_schema.json`` once at
    construction and reuses it for every call.

    Raises:
        ValidationError: If the record does not conform to the schema.
                         This is a hard failure — the record is not persisted.
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
        raise NotImplementedError

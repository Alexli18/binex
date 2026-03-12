"""Output schema validation for node results."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import jsonschema


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def validate_output(output: Any, schema: dict[str, Any]) -> ValidationResult:
    """Validate node output against a JSON Schema.

    Handles:
    - dict output: validate directly
    - string output: try to parse as JSON first
    - None/empty: validation failure
    """
    import json

    # Parse string to dict if needed
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            return ValidationResult(
                valid=False,
                errors=[f"Output is not valid JSON: {output[:100]}"],
            )

    if output is None:
        return ValidationResult(valid=False, errors=["Output is None"])

    # Validate against schema
    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema)
    error_messages = [e.message for e in validator.iter_errors(output)]

    if error_messages:
        return ValidationResult(valid=False, errors=error_messages)
    return ValidationResult(valid=True)

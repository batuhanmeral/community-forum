from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from .countries import COUNTRY_CODES

# Mentions and API paths rely on this charset, so the model enforces it too.
username_validator = RegexValidator(
    regex=r"^[A-Za-z0-9_]{3,30}\Z",
    message="Use 3-30 characters: letters, digits and underscores.",
)


def validate_country_code(value: str) -> None:
    if value and value not in COUNTRY_CODES:
        raise ValidationError("Choose a country from the list.")

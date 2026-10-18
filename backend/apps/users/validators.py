from django.core.validators import RegexValidator

# Mentions and API paths rely on this charset, so the model enforces it too.
username_validator = RegexValidator(
    regex=r"^[A-Za-z0-9_]{3,30}\Z",
    message="Use 3-30 characters: letters, digits and underscores.",
)

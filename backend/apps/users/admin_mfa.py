"""Second factor for the Django admin login (it bypasses the JWT flow otherwise)."""

from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from rest_framework.exceptions import Throttled

from . import mfa
from .models import MfaDevice


class MfaAdminAuthenticationForm(AdminAuthenticationForm):
    otp = forms.CharField(
        required=False,
        strip=True,
        label="Authenticator or recovery code",
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code"}),
    )

    def clean(self):
        cleaned = super().clean()  # checks the password and staff status first
        user = self.get_user()
        if (
            user is not None
            and MfaDevice.objects.filter(user=user, confirmed_at__isnull=False).exists()
        ):
            ip = self.request.META.get("REMOTE_ADDR") if self.request else None
            try:
                method = mfa.verify_second_factor(user, cleaned.get("otp", ""), ip=ip, kind="admin")
            except Throttled as exc:
                raise forms.ValidationError(str(exc.detail), code="throttled") from exc
            if method is None:
                raise forms.ValidationError("Invalid or missing verification code.", code="mfa")
        return cleaned

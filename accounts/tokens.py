from datetime import timedelta

from django.core import signing

CONFIRMATION_SALT = "accounts.registration-confirmation"
CONFIRMATION_MAX_AGE = timedelta(hours=72)


def create_confirmation_token(pending_registration):
    return signing.dumps(
        {"pending_registration_id": pending_registration.pk},
        salt=CONFIRMATION_SALT,
    )


def decode_confirmation_token(token):
    return signing.loads(
        token,
        salt=CONFIRMATION_SALT,
        max_age=CONFIRMATION_MAX_AGE,
    )



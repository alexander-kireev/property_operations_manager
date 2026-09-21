import secrets

from django.forms.utils import ErrorDict
from django.http import QueryDict


FORM_STATE_QUERY_PARAMETER = "form_state"
FORM_STATE_SESSION_PREFIX = "form_state:"


def serialise_form_data(post_data, *, exclude=()):
    excluded_fields = {"csrfmiddlewaretoken", *exclude}
    return {
        name: list(values)
        for name, values in post_data.lists()
        if name not in excluded_fields
    }


def deserialise_form_data(data):
    query_data = QueryDict("", mutable=True)
    for name, values in data.items():
        query_data.setlist(name, values)
    return query_data


def serialise_form_errors(form):
    return {
        name: [error["message"] for error in errors]
        for name, errors in form.errors.get_json_data().items()
    }


def restore_form_errors(form, errors):
    form.errors
    form._errors = ErrorDict()
    for name, messages in errors.items():
        field = None if name == "__all__" else name
        for message in messages:
            form.add_error(field, message)
    return form


def store_form_state(request, state):
    token = secrets.token_urlsafe(16)
    request.session[f"{FORM_STATE_SESSION_PREFIX}{token}"] = state
    return token


def pop_form_state(request):
    token = request.GET.get(FORM_STATE_QUERY_PARAMETER, "")
    if not token:
        return None
    return request.session.pop(f"{FORM_STATE_SESSION_PREFIX}{token}", None)

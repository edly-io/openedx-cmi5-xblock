"""Openedx CMI5 xblock utility functions."""
import hashlib
import json

from django.core.validators import URLValidator
from webob import Response


def json_response(data):
    """Generate a JSON response."""
    return Response(json.dumps(data), content_type='application/json', charset='utf8')


def is_url(path):
    """Checks if the given path is a valid URL."""
    try:
        validator = URLValidator(verify_exists=False)
        validator(path)
    except Exception as err:
        return False
    return True


def is_cmi5_object(categories):
    """Checks if the given categories include the cmi5 category."""
    if categories is None:
        return False
    cmi5_category = 'https://w3id.org/xapi/cmi5/context/categories/cmi5'
    return any([category['id'] == cmi5_category for category in categories])


def is_params_exist(url):
    """Checks if query parameters exist in the given URL."""
    return '?' in url


def get_request_body(request):
    """Gets the JSON body from an HTTP request."""
    return json.loads(request.body.decode('utf-8'))


def get_sha1(file_descriptor):
    """Get file hex digest (fingerprint)."""
    block_size = 8 * 1024
    sha1 = hashlib.sha1()
    while True:
        block = file_descriptor.read(block_size)
        if not block:
            break
        sha1.update(block)
    file_descriptor.seek(0)
    return sha1.hexdigest()


def parse_int(value, default):
    """
    Parses an integer.

    returning the parsed value or a default if unsuccessful.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_float(value, default):
    """
    Parses a float.

    Returning the parsed value or a default if unsuccessful.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_validate_positive_float(value, name):
    """Parse and validate a given value as a positive float."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError('Could not parse value of "{}" (must be float): {}'.format(name, value))
    if parsed < 0:
        raise ValueError('Value of "{}" must not be negative: {}'.format(name, value))
    return parsed

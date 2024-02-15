"""Openedx CMI5 xblock utility functions."""
import hashlib
import json
import logging

import requests
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from requests.auth import HTTPBasicAuth
from webob import Response

logger = logging.getLogger(__name__)


def json_response(data):
    """Generate a JSON response."""
    return Response(json.dumps(data), content_type='application/json', charset='utf8')


def is_url(path):
    """Checks if the given path is a valid URL."""
    try:
        validator = URLValidator()
        validator(path)
    except ValidationError as err:
        logger.debug("Invalid URL (%s): %s", path, err)
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


def send_xapi_to_external_lrs(xapi_data, lrs_url, LRS_AUTH_KEY, LRS_AUTH_SECRET):
    """Send xAPI data to the specified LRS URL."""
    timeout = 10
    headers = {
        'Content-Type': 'application/json',
        'X-Experience-API-Version': '1.0.3'
    }
    if not lrs_url.endswith(('statements', 'statements/')):
        lrs_url += '/statements'

    try:
        response = requests.post(
            lrs_url,
            headers=headers,
            auth=HTTPBasicAuth(LRS_AUTH_KEY, LRS_AUTH_SECRET),
            data=json.dumps(xapi_data),
            timeout=timeout
        )
        response.raise_for_status()

        logger.info("Successfully sent xAPI data to LRS.")
        logger.info(f"Response Status Code: {response.status_code}")
        logger.info(f"Response Content: {response.text}")

    except requests.exceptions.HTTPError as errh:
        logger.error("HTTP Error: %s", errh)

    except requests.exceptions.ConnectionError as errc:
        logger.error("Error Connecting: %s", errc)

    except requests.exceptions.Timeout as errt:
        logger.error("Timeout Error: %s", errt)

    except requests.exceptions.RequestException as err:
        logger.error("Error: %s", err)


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

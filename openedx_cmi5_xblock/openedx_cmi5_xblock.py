"""Openedx CMI5 XBlock implementation."""

import hashlib
import json
import logging
import os
import urllib
import uuid
import xml.etree.ElementTree as ET
import zipfile

import pkg_resources
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.validators import URLValidator
from django.template import Context, Template
from django.utils import timezone
from django.utils.module_loading import import_string
from six import string_types
from webob import Response
from xblock.completable import CompletableXBlockMixin
from xblock.core import XBlock
from xblock.fields import Boolean, DateTime, Dict, Float, Integer, Scope, String
from xblock.fragment import Fragment

logger = logging.getLogger(__name__)

CMI5XML_FILENAME = 'cmi5.xml'


def _(text):
    return text


@XBlock.wants('i18n')
@XBlock.wants('user')
@XBlock.wants('settings')
@XBlock.wants('enrollments')
class CMI5XBlock(XBlock, CompletableXBlockMixin):
    """The main xblock class with all the members defined."""

    display_name = String(
        display_name=_('Display Name'),
        help=_('Display name'),
        default='CMI5 module',
        scope=Scope.settings,
    )

    index_page_path = String(
        display_name=_('Path to the index page in CMI5 file'),
        scope=Scope.settings
    )

    package_meta = Dict(scope=Scope.content)

    course_data = Dict(
        scope=Scope.content,
        default={},
        help=_('Save course id, title and description')
    )

    lesson_status = String(
        scope=Scope.user_state,
        default='unknown'
    )

    lesson_score = Float(
        scope=Scope.user_state,
        default=0,
        help=_('Latest passed attempt Score')
    )

    state_data = Dict(
        scope=Scope.user_state,
        default={},
        help=_('Save course state such as bookmark')
    )

    has_score = Boolean(
        display_name=_('Scored'),
        help=_('Select False if this component will not receive a numerical score from the CMI5'),
        default=True,
        scope=Scope.settings
    )

    weight = Float(
        default=1,
        display_name=_('Weight'),
        help=_('Weight/Maximum grade'),
        scope=Scope.settings,
    )

    width = Integer(
        display_name=_('Display width (px)'),
        help=_('Width of iframe (default: 100%)'),
        scope=Scope.settings,
    )

    height = Integer(
        display_name=_('Display height (px)'),
        help=_('Height of iframe'),
        default=450,
        scope=Scope.settings,
    )

    has_author_view = True

    def render_template(self, template_path, context):
        """Render a template with the provided context."""
        template_str = self.resource_string(template_path)
        template = Template(template_str)
        return template.render(Context(context))

    @staticmethod
    def resource_string(path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode('utf8')

    @staticmethod
    def json_response(data):
        """Generate a JSON response."""
        return Response(json.dumps(data), content_type='application/json', charset='utf8')

    def get_current_user_attr(self, attr: str):
        """Get the value of a specific attribute for the current user."""
        return self.get_current_user().opt_attrs.get(attr)

    def get_current_user(self):
        """Get the current user."""
        return self.runtime.service(self, 'user').get_current_user()

    def author_view(self, context=None):
        """View for authors to preview content."""
        context = context or {}
        if not self.index_page_path:
            context['message'] = 'Click "Edit" to modify this module and upload a new CMI5 package.'
        return self.student_view(context=context)

    def studio_view(self, context=None):
        """
        It generates the studio view.

        Including the display of various fields related to the CMI5 XBlock,
        and initializes the required CSS and JavaScript.
        """
        studio_context = {
            'field_display_name': self.fields['display_name'],
            'field_has_score': self.fields['has_score'],
            'field_weight': self.fields['weight'],
            'field_width': self.fields['width'],
            'field_height': self.fields['height'],
            'cmi5_xblock': self
        }

        studio_context.update(context or {})
        template = self.render_template('static/html/studio.html', studio_context)
        frag = Fragment(template)
        frag.add_css(self.resource_string('static/css/openedx_cmi5_xblock.css'))
        frag.add_javascript(self.resource_string('static/js/src/studio.js'))
        frag.initialize_js('CMI5StudioXBlock')
        return frag

    def student_view(self, context=None):
        """The primary view of the CMI5XBlock, shown to students when viewing courses."""
        student_context = {
            'title': self.display_name,
            'index_page_url': self.index_page_url,
            'cmi5_xblock': self,
        }
        student_context.update(context or {})
        template = self.render_template('static/html/openedx_cmi5_xblock.html', student_context)
        frag = Fragment(template)

        frag.add_css(self.resource_string('static/css/openedx_cmi5_xblock.css'))
        frag.add_javascript(self.resource_string('static/js/src/openedx_cmi5_xblock.js'))
        frag.initialize_js(
            'CMI5XBlock', json_args={
                'popup_width': self.width or 800,
                'popup_height': self.height or 800,
            },
        )
        return frag

    @property
    def index_page_url(self):
        """
        Gets the URL of the CMI5 index page.

        Returns an empty string if the package metadata or index page path is not available.
        """
        if not self.package_meta or not self.index_page_path:
            return ''

        folder = self.extract_folder_path
        if self.storage.exists(os.path.join(self.extract_folder_base_path, self.index_page_path)):
            # For backward-compatibility, we must handle the case when the xblock data
            # is stored in the base folder.
            folder = self.extract_folder_base_path
            logger.warning('Serving CMI5 content from old-style path: %s', folder)

        lms_cmi5_url = requests.utils.unquote(self.storage.url(os.path.join(folder, self.index_page_path)))
        if self.is_url(self.index_page_path):
            lms_cmi5_url = self.index_page_path
        params_joining_symbol = '&' if self.is_params_exist(lms_cmi5_url) else '?'
        lms_cmi5_url = lms_cmi5_url + params_joining_symbol
        return lms_cmi5_url + self.get_launch_url_params()

    @property
    def extract_folder_path(self):
        """
        It needs to depend on the content of the cmi5 package.

        Otherwise, served media files might become stale when the package is update.
        """
        return os.path.join(self.extract_folder_base_path, self.package_meta['sha1'])

    @property
    def extract_folder_base_path(self):
        """Path to the folder where packages will be extracted."""
        return os.path.join(self.cmi5_location(), self.location.block_id)

    def is_url(self, path):
        """Checks if the given path is a valid URL."""
        try:
            validator = URLValidator(verify_exists=False)
            validator(path)
        except Exception as err:
            return False
        return True

    def is_params_exist(self, url):
        """Checks if query parameters exist in the given URL."""
        return '?' in url

    def get_launch_url_params(self):
        """Constructs and returns launch URL parameters for CMI5 integration."""
        parameters = {
            'fetch': urllib.parse.quote_plus(self.runtime.handler_url(self, 'lrs_auth_endpoint', thirdparty=True)),
            'endpoint': urllib.parse.quote_plus(
                self.runtime.handler_url(self, 'lrs_endpoint', thirdparty=True).replace('?', '')
                ),
            'actor': json.dumps(
                {
                    'objectType': 'Agent',
                    'name': self.get_current_user_attr('edx-platform.username'),
                    'account': {'homePage': settings.LMS_ROOT_URL, 'name': self.get_enrollment_uuid()}
                }
            ),
            'activityId': self.course_data.get('course_id', 'http://lms.io'),
            'registration': self.get_enrollment_uuid(),
        }

        all_parameters = ''
        for index, parameter in enumerate(parameters.items()):
            all_parameters += parameter[0] + '=' + parameter[1]
            if index != len(parameters) - 1:
                all_parameters += '&'

        return all_parameters

    @XBlock.handler
    def studio_submit(self, request, _suffix):
        """Handles the submission of the CMI5 XBlock studio form."""
        self.display_name = request.params['display_name']
        self.width = parse_int(request.params['width'], None)
        self.height = parse_int(request.params['height'], None)
        self.has_score = request.params['has_score'] == '1'
        self.weight = parse_float(request.params['weight'], 1)
        self.icon_class = 'problem' if self.has_score else 'video'

        response = {'result': 'success', 'errors': []}
        if not hasattr(request.params['file'], 'file'):
            # File not uploaded
            return self.json_response(response)

        package_file = request.params['file'].file
        self.update_package_meta(package_file)

        # Clean storage folder, if it already exists
        self.clean_storage()

        # Extract zip file
        try:
            self.extract_package(package_file)
            self.update_package_fields()
        except CMI5Error as e:
            response['errors'].append(e.args[0])
        return self.json_response(response)

    def update_package_meta(self, package_file):
        """Updates the package metadata based on the provided package file."""
        self.package_meta['sha1'] = self.get_sha1(package_file)
        self.package_meta['name'] = package_file.name
        self.package_meta['last_updated'] = timezone.now().strftime(DateTime.DATETIME_FORMAT)
        self.package_meta['size'] = package_file.seek(0, 2)
        package_file.seek(0)

    def clean_storage(self):
        """Cleans the storage by removing the previously unzipped content."""
        if self.storage.exists(self.extract_folder_base_path):
            logger.info('Removing previously unzipped "%s"', self.extract_folder_base_path)
            self.recursive_delete(self.extract_folder_base_path)

    def recursive_delete(self, root):
        """
        Recursively delete the contents of a directory in the Django default storage.

        Unfortunately, this will not delete empty folders, as the default FileSystemStorage
        implementation does not allow it.
        """
        directories, files = self.storage.listdir(root)
        for directory in directories:
            self.recursive_delete(os.path.join(root, directory))
        for f in files:
            self.storage.delete(os.path.join(root, f))

    def extract_package(self, package_file):
        """Extracts content from the provided CMI5 package file."""
        ext = package_file.name.split('.')[-1].lower()
        if ext == 'zip':
            self.extract_zip_file(package_file)
        elif ext == 'xml':
            self.save_xml_file(package_file)
        else:
            raise CMI5Error(f'Could not support {ext} file')

    def extract_zip_file(self, package_file):
        """Extracts content from a zip file within the CMI5 package."""
        with zipfile.ZipFile(package_file, 'r') as cmi5_zipfile:
            zipinfos = cmi5_zipfile.infolist()
            root_path = None
            root_depth = -1

            # Find root folder which contains cmi5.xml
            for zipinfo in zipinfos:
                if os.path.basename(zipinfo.filename) == CMI5XML_FILENAME:
                    depth = len(os.path.split(zipinfo.filename))
                    if depth < root_depth or root_depth < 0:
                        root_path = os.path.dirname(zipinfo.filename)
                        root_depth = depth

            if root_path is None:
                raise CMI5Error('Could not find "cmi5.xml" file in the cmi5 package')

            for zipinfo in zipinfos:
                if zipinfo.filename.startswith(root_path):
                    if not zipinfo.filename.endswith('/'):
                        dest_path = os.path.join(self.extract_folder_path, os.path.relpath(zipinfo.filename, root_path))
                        self.storage.save(dest_path, ContentFile(cmi5_zipfile.read(zipinfo.filename)))

    def save_xml_file(self, package_file):
        """Saves an XML file from the CMI5 package."""
        dest_path = os.path.join(self.extract_folder_path, package_file.filename)
        self.storage.save(dest_path, ContentFile(package_file.filename))

    def update_package_fields(self):
        """Update version and index page path fields."""
        cmi5_path = self.find_file_path(CMI5XML_FILENAME)
        cmi5_file = self.storage.open(cmi5_path)
        tree = ET.parse(cmi5_file)
        cmi5_file.seek(0)
        namespace = ''
        for _, node in ET.iterparse(cmi5_file, events=['start-ns']):
            if node[0] == '':
                namespace = node[1]
                break
        root = tree.getroot()

        prefix = '{' + namespace + '}' if namespace else ''
        self.set_course_detail(prefix, root)

        au_url = root.find('.//{prefix}au/{prefix}url'.format(prefix=prefix))
        if au_url is not None:
            self.index_page_path = au_url.text
        else:
            self.index_page_path = self.find_relative_file_path('index.html')

    def set_course_detail(self, prefix, root):
        """Extracts course details from the provided XML root."""
        course_data = {}

        try:
            course_structure = root.find('{prefix}course'.format(prefix=prefix))
            course_data['course_id'] = course_structure.attrib['id']

            course_title = course_structure.find('{prefix}title/{prefix}langstring'.format(prefix=prefix))
            course_data['title'] = course_title.text if course_title is not None else None

            course_description = course_structure.find('{prefix}description/{prefix}langstring'.format(prefix=prefix))
            course_data['description'] = course_description.text if course_description is not None else None
        except Exception as err:
            logger.error('Error occurred while parsing course xml: %s', err)

        self.course_data = course_data

    @XBlock.handler
    def lrs_endpoint(self, request, _suffix):
        """Handles requests related to the Learning Record Store (LRS) endpoint."""
        if request.params.get('statementId') and request.method == 'PUT':
            statement_data = self.get_request_body(request)

            lesson_status = statement_data.get('verb').get('display').get('en')
            object_categories = statement_data.get('context', {}).get('contextActivities', {}).get('category')

            if lesson_status == 'failed' and self.lesson_status in ['passed', 'completed']:
                return Response(status=204)
            elif lesson_status in ['passed', 'failed']:
                self.lesson_status = lesson_status
                self.lesson_score = statement_data.get('result').get('score', {}).get('scaled', self.weight)
                self.publish_grade()
            elif lesson_status == 'completed' and self.is_cmi5_object(object_categories):
                self.lesson_status = lesson_status
                self.emit_completion(1.0)
            return Response(status=204)

        elif request.params.get('stateId'):
            state_id = request.params.get('stateId')

            if state_id == 'LMS.LaunchData':
                return Response(json.dumps(self.get_launch_state_data()), status=200)
            elif state_id == 'suspendData' and request.method == 'GET':
                return self.json_response(self.state_data)
            elif state_id == 'suspendData' and request.method == 'PUT':
                self.state_data = self.get_request_body(request)
                return Response(status=204)

        return self.json_response({'success': True})

    def get_request_body(self, request):
        """Gets the JSON body from an HTTP request."""
        return json.loads(request.body.decode('utf-8'))

    def publish_grade(self):
        """Publishes the grade to the XBlock runtime."""
        self.runtime.publish(self, 'grade', {'value': self.get_grade(), 'max_value': self.weight})

    def get_grade(self):
        """Calculates and returns the normalized grade."""
        lesson_score = 0 if self.is_failed else self.lesson_score
        return lesson_score * self.weight

    @property
    def is_failed(self):
        """Checks if the lesson is in a failed status."""
        return self.lesson_status == 'failed'

    def is_cmi5_object(self, categories):
        """Checks if the given categories include the cmi5 category."""
        if categories is None:
            return False
        cmi5_category = 'https://w3id.org/xapi/cmi5/context/categories/cmi5'
        return any([category['id'] == cmi5_category for category in categories])

    def get_launch_state_data(self):
        """Generates and returns launch state data for the XBlock."""
        return {
            'contextTemplate': {
                'registration': self.get_enrollment_uuid(),
                'contextActivities': {
                    'parent': [
                        {
                            'id': self.course_data['course_id'],
                            'definition': {
                                'name': {
                                    'en-US': self.course_data['title']
                                },
                                'description': {
                                    'en-US': self.course_data['description']
                                },
                            }
                        }
                    ]
                }
            },
            'launchMode': 'Normal',
            'launchParameters': ''
        }

    @XBlock.handler
    def lrs_auth_endpoint(self, request, _suffix):
        """Handles requests to the LRS authentication endpoint."""
        user_id = self.get_current_user_attr('edx-platform.user_id')
        session_id = request.cookies.get('sessionid', 'auth-session-id')
        authtoken = 'user-id:{0}_session-id:{1}'.format(user_id, session_id)

        authtoken = hashlib.sha256(authtoken.encode()).hexdigest()
        return self.json_response({'auth-token': authtoken})

    def get_erollment_id(self):
        """Retrieves the enrollment ID of the current user for the XBlock's course."""
        user_id = self.get_current_user_attr('edx-platform.user_id')
        course_id = self.runtime.course_id
        try:
            enrollment = self.runtime.service(self, 'enrollments').get_active_enrollment_of_user_by_course(
                user_id, course_id
            )
            return enrollment.id
        except Exception as err:
            return 'anonymous'

    def get_enrollment_uuid(self):
        """Generates and returns the enrollment UUID based on the enrollment ID."""
        base_id = uuid.UUID('2af01743-8d97-423e-988a-25c69fa4ea66')
        enrollment_uuid = uuid.uuid5(base_id, 'openedx-enrollment-id:{0}'.format(self.get_erollment_id()))
        return str(enrollment_uuid)

    def find_relative_file_path(self, filename):
        """Finds the relative file path within the XBlock's extract folder."""
        return os.path.relpath(self.find_file_path(filename), self.extract_folder_path)

    def find_file_path(self, filename):
        """
        Search recursively in the extracted folder for a given file.

        Path of the first found file will be returned.
        Raise a CMI5Error if file cannot be found.
        """
        path = self.get_file_path(filename, self.extract_folder_path)
        if path is None:
            raise CMI5Error('Invalid package: could not find "{}" file'.format(filename))
        return path

    def get_file_path(self, filename, root):
        """Same as `find_file_path`, but don't raise error on file not found."""
        subfolders, files = self.storage.listdir(root)
        for f in files:
            if f == filename:
                return os.path.join(root, filename)
        for subfolder in subfolders:
            path = self.get_file_path(filename, os.path.join(root, subfolder))
            if path is not None:
                return path
        return None

    def cmi5_location(self):
        """
        Unzipped files will be stored in a media folder with this name.

        thus accessible at a url with that also includes this name.
        """
        default_cmi5_location = 'cmi5'
        return self.xblock_settings.get('LOCATION', default_cmi5_location)

    @staticmethod
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

    @property
    def storage(self):
        """
        Return the storage backend used to store the assets of this xblock.

        This is a cached property.
        """
        if not getattr(self, '_storage', None):
            def get_default_storage(_xblock):
                return default_storage

            storage_func = self.xblock_settings.get('STORAGE_FUNC', get_default_storage)
            if isinstance(storage_func, string_types):
                storage_func = import_string(storage_func)
            self._storage = storage_func(self)

        return self._storage

    @property
    def xblock_settings(self):
        """Return a dict of settings associated to this XBlock."""
        settings_service = self.runtime.service(self, 'settings') or {}
        if not settings_service:
            return {}
        return settings_service.get_settings_bucket(self)

    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ('CMI5XBlock',
             '''<openedx_cmi5_xblock/>
             '''),
            ('Multiple CMI5XBlock',
             '''<vertical_demo>
                <openedx_cmi5_xblock/>
                <openedx_cmi5_xblock/>
                <openedx_cmi5_xblock/>
                </vertical_demo>
             '''),
        ]


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


class CMI5Error(Exception):
    """Base exception class for CMI5-related errors."""

    pass

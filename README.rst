Openedx CMI5 XBlock
#############################

Xblock to play CMI5 content inside Open edX


Testing with Docker
********************

This XBlock comes with a Docker test environment ready to build, based on the xblock-sdk workbench. To build and run it::

    $ make dev.run

The XBlock SDK Workbench, including this XBlock, will be available on the list of XBlocks at http://localhost:8000

Installation for tutor
**********************

This method works with `tutor <https://github.com/overhangio/tutor/>`__.

First, go to your requirements directory::

    cd $(tutor config printroot)/env/build/openedx/requirements/


add the `openedx-cmi5-xblock` repo to  the `private.txt`::

    echo "git+https://github.com/edly-io/openedx-cmi5-xblock.git" >> private.txt


and build a new image::

    tutor images build openedx


In your studio, in your desired course, go to Advanced Settings and add `"openedx_cmi5_xblock"` in the Advanced Module List.

If you want to test the cmi5 content, then `here <https://xapi.com/cmi5/example-course-templates/>`__ you can get demo files to test: 

Development
***********

There's no need to build a new image, if you just want to play with the xblock.

First, clone the repo in the requirements directory::

    cd $(tutor config printroot)/env/build/openedx/requirements/
    git clone git@github.com:edly-io/openedx-cmi5-xblock.git


exec to the lms container and install the XBlock::

    tutor dev exec -it lms bash
    cd ../requirements
    pip install -e openedx-cmi5-xblock

If you struggle with lms not displaying your cmi5 content in IFrame, then ``X_FRAME_OPTIONS = "SAMEORIGIN"`` is the settings you need to add a patch for to give access to your lms domain.

Note: This is not the best practice to develop an XBlock, but it works if you don't want to build dev image.


Advanced Configuration For External LRS
***************************************

The cmi5 Xblock may be configured to enable Third-party Learning Record Store to keep record of xapi statements outside of LMS. To configure that, add the following to Tutor by creating a `plugin <https://docs.tutor.overhang.io/plugins/>`__::

    hooks.Filters.ENV_PATCHES.add_item(
        (
        "openedx-common-settings",
        """
    XBLOCK_SETTINGS["CMI5XBlock"] = {
        "LRS_AUTH_KEY": "<LRS-activity-provider-key>",
        "LRS_AUTH_SECRET": "<LRS-secret-key>",
        "LRS_ENDPOINT": "<domain>/lrs/<LRS-app-id>/statements/"
        # ... other settings
    }"""
        )
    )

Note: This method is for enabling External LRS for CMI5-Xblock in Tutor.


Translating
*************

Internationalization (i18n) is when a program is made aware of multiple languages.
Localization (l10n) is adapting a program to local language and cultural habits.

Use the locale directory to provide internationalized strings for your XBlock project.
For more information on how to enable translations, visit the
`Open edX XBlock tutorial on Internationalization <https://edx.readthedocs.org/projects/xblock-tutorial/en/latest/edx_platform/edx_lms.html>`_.

This cookiecutter template uses `django-statici18n <https://django-statici18n.readthedocs.io/en/latest/>`_
to provide translations to static javascript using ``gettext``.

The included Makefile contains targets for extracting, compiling and validating translatable strings.
The general steps to provide multilingual messages for a Python program (or an XBlock) are:

1. Mark translatable strings.
2. Run i18n tools to create raw message catalogs.
3. Create language specific translations for each message in the catalogs.
4. Use ``gettext`` to translate strings.

1. Mark translatable strings
=============================

Mark translatable strings in python::


    from django.utils.translation import ugettext as _

    # Translators: This comment will appear in the `.po` file.
    message = _("This will be marked.")

See `edx-developer-guide <https://edx.readthedocs.io/projects/edx-developer-guide/en/latest/internationalization/i18n.html#python-source-code>`__
for more information.

You can also use ``gettext`` to mark strings in javascript::


    // Translators: This comment will appear in the `.po` file.
    var message = gettext("Custom message.");

See `edx-developer-guide <https://edx.readthedocs.io/projects/edx-developer-guide/en/latest/internationalization/i18n.html#javascript-files>`__
for more information.

2. Run i18n tools to create Raw message catalogs
=================================================

This cookiecutter template offers multiple make targets which are shortcuts to
use `edx-i18n-tools <https://github.com/openedx/i18n-tools>`_.

After marking strings as translatable we have to create the raw message catalogs.
These catalogs are created in ``.po`` files. For more information see
`GNU PO file documentation <https://www.gnu.org/software/gettext/manual/html_node/PO-Files.html>`_.
These catalogs can be created by running::


    $ make extract_translations

The previous command will create the necessary ``.po`` files under
``openedx-cmi5-xblock/openedx_cmi5_xblock/locale/en/LC_MESSAGES/text.po``.
The ``text.po`` file is created from the ``django-partial.po`` file created by
``django-admin makemessages`` (`makemessages documentation <https://docs.djangoproject.com/en/3.2/topics/i18n/translation/#message-files>`_),
this is why you will not see a ``django-partial.po`` file.

3. Create language specific translations
==============================================

3.1 Add translated strings
---------------------------

After creating the raw message catalogs, all translations should be filled out by the translator.
One or more translators must edit the entries created in the message catalog, i.e. the ``.po`` file(s).
The format of each entry is as follows::

    #  translator-comments
    A. extracted-comments
    #: reference…
    #, flag…
    #| msgid previous-untranslated-string
    msgid 'untranslated message'
    msgstr 'mensaje traducido (translated message)'

For more information see
`GNU PO file documentation <https://www.gnu.org/software/gettext/manual/html_node/PO-Files.html>`_.

To use translations from transifex use the follow Make target to pull translations::

    $ make pull_translations

See `config instructions <https://github.com/openedx/i18n-tools#transifex-commands>`_ for information on how to set up your
transifex credentials.

See `transifex documentation <https://docs.transifex.com/integrations/django>`_ for more details about integrating
django with transiflex.

3.2 Compile translations
-------------------------

Once translations are in place, use the following Make target to compile the translation catalogs ``.po`` into
``.mo`` message files::

    $ make compile_translations

The previous command will compile ``.po`` files using
``django-admin compilemessages`` (`compilemessages documentation <https://docs.djangoproject.com/en/3.2/topics/i18n/translation/#compiling-message-files>`_).
After compiling the ``.po`` file(s), ``django-statici18n`` is used to create language specific catalogs. See
``django-statici18n`` `documentation <https://django-statici18n.readthedocs.io/en/latest/>`_ for more information.

To upload translations to transiflex use the follow Make target::

    $ make push_translations

See `config instructions <https://github.com/openedx/i18n-tools#transifex-commands>`_ for information on how to set up your
transifex credentials.

See `transifex documentation <https://docs.transifex.com/integrations/django>`_ for more details about integrating
django with transiflex.

 **Note:** The ``dev.run`` make target will automatically compile any translations.

 **Note:** To check if the source translation files (``.po``) are up-to-date run::

     $ make detect_changed_source_translations

4. Use ``gettext`` to translate strings
========================================

Django will automatically use ``gettext`` and the compiled translations to translate strings.

Troubleshooting
****************

If there are any errors compiling ``.po`` files run the following command to validate your ``.po`` files::

    $ make validate

See `django's i18n troubleshooting documentation
<https://docs.djangoproject.com/en/3.2/topics/i18n/translation/#troubleshooting-gettext-incorrectly-detects-python-format-in-strings-with-percent-signs>`_
for more information.

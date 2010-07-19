#!/usr/bin/env python
# -*- coding: utf-8 -*-
""".. currentmodule:: gpypi2.config
Configuration module

Implements :class:`Config` and :class:`ConfigManager` to be used as
"configuration holders" and validators.

"""

import os
import shutil
import logging
from ConfigParser import SafeConfigParser

from portage.output import colorize

from gpypi2.utils import asbool
from gpypi2.exc import *

log = logging.getLogger(__name__)
HERE = os.path.dirname(os.path.abspath(__file__))

class Config(dict):
    """Holds config values retrieved from various sources. To load
    configuration from a source use one of :meth:`from_*` methods.
    Class also defines specification for supported options in :attr:`allowed_options`.

    Values are retrieved with help of :meth:`Config.validator` method.

    Example::

        >>> Config.from_pypi({'homepage': 'foobar'})
        <Config {'homepage': 'foobar'}>

    :attr:`allowed_options` format::

        'name': ('Question ..', obj_type, default_value)

    """

    allowed_options = {
        'pn': ('Specify PN to use when naming ebuild', str, False),
        'pv': ('Specify PV to use when naming ebuild', str, False),
        'my_pv': ('Specify MY_PV used in ebuild', str, False),
        'my_pn': ('Specify MY_PN used in ebuild', str, False),
        'my_p': ('Specify MY_P used in ebuild', str, False),
        'uri': ('Specify SRC_URI of the package', str, ""),
        'index_url': ('Base URL for PyPi', str, "http://pypi.python.org/pypi"),
        'overlay': ('Specify overlay to use by name (stored in $OVERLAY/profiles/repo_name)', str, "local"),
        'overwrite': ('Overwrite existing ebuild', bool, False),
        'no_deps': ("Don't create ebuilds for any needed dependencies", bool, False),
        'category': ("Specify portage category to use when creating ebuild", str, "dev-python"),
        'format': ("Format when printing to stdout (use pygments identifier)", str, "none"),
        'package': ("Package name for ebuild actions", str, None),
        'version': ("Package version for ebuild actions", str, None),
        'command': ("Name of command that was invoked on CLI", str, None),
        'nocolors': ("Disable colorful output", bool, False),
        'background': ("Background of terminal when using formatting", str, 'dark')
    }

    def __repr__(self):
        return "<Config %s>" % dict.__repr__(self)

    ##  from_config

    @classmethod
    def from_pypi(cls, metadata):
        """Load config from :term:`PyPi`

        :param metadata: Metadata retrieved from :term:`PyPi` query
        :type metadata: dict
        :returns: :class:`Config` instance

        """
        return cls(metadata)

    @classmethod
    def from_ini(cls, path_to_ini, section='config'):
        """Load config from .ini

        :param path_to_ini: Retrieve dictionary from `path_to_ini` file, from `section`
        :type path_to_ini: file path
        :param section: Name of the section to be used
        :type section: string
        :returns: :class:`Config` instance

        """
        config = SafeConfigParser()
        config.read(path_to_ini)
        d = map(lambda i: (i[0], cls.validate(i[0], i[1])), config.items(section))
        return cls(d)

    @classmethod
    def from_setup_py(cls, keywords):
        """Load config from setup.py

        :param keywords: option passed to :func:`setup` function in **setup.y** file.
        :type keywords: dict
        :returns: :class:`Config` instance

        """
        return cls(keywords)

    @classmethod
    def from_argparse(cls, options):
        """Load config from argparse options.

        :param options: Arguments retrieved from `parser.parse_args()`
        :type options: `argparse.Namespace` instance
        :returns: :class:`Config` instance

        """
        return cls(filter(lambda i: i[1] is not None, options.__dict__.iteritems()))

    ## validate types

    @classmethod
    def validate(cls, name, value):
        """Validates and parses config value. Will dispatch calls to 
        subvalidators based on type of the config option.

        :param name: key from :attr:`Config.allowed_options`
        :type name: string
        :param value: Value to be validated and parsed
        :type value: everything

        """
        validator = cls.allowed_options[name][1]
        if isinstance(validator, type):
            f = getattr(cls, 'validate_%s' % validator.__name__)
        else:
            f = getattr(cls, 'validate_%s' % validator)
        return f(value)

    @classmethod
    def validate_bool(cls, value):
        """Subvalidator which handles string values into bool"""
        try:
            return asbool(value)
        except ValueError:
            raise GPyPiValidationError("Not a boolean (write y/n): %r" % value)

    @classmethod
    def validate_str(cls, value, encoding='utf-8'):
        """Subvalidator for string. Also converts to unicode"""
        if isinstance(value, basestring):
            if isinstance(value, str):
                value = unicode(value, encoding)
            return value
        else:
            raise GPyPiValidationError("Not a string: %r" % value)


class ConfigManager(object):
    """Holds multiple :class:`Config` instances and retrieves
    values from them.

    :param use: Order of configuration taken in account
    :type use: list of strings
    :param questionnaire_options: What options will not use default if not
        given, but rather invoke interactive :class:`Questionnaire`
    :type questionnaire_options: list of strings
    :param questionnaire_class: class to be used for questionnaire,
        defaults to :class:`Questionnaire`
    :type questionnaire_class: class
    :raises: :exc:`gpypi2.exc.GPyPiConfigurationError` when:

        * no config is set
        * when option is retrieved that does not exist in :attr:`Config.allowed_options`
        * `use` does not have unique elements

    :attr:`INI_TEMPLATE_PATH` -- Absolute path to .ini template file

    Example::

        >>> mgr = ConfigManager(['pypi', 'setup_py'])
        >>> mgr.configs['pypi'] = (Config.from_pypi({}))
        >>> mgr.configs['setup_py'] = (Config.from_setup_py({'overlay': 'foobar'}))
        >>> print mgr.overlay
        foobar

    """
    INI_TEMPLATE_PATH = os.path.join(HERE, 'templates', 'gpypi2.ini')

    def __init__(self, use, questionnaire_options=None, questionnaire_class=None):
        for config in use:
            if use.count(config) != 1:
                raise GPyPiConfigurationError("ConfigManager could not be setup"
                    ", config order has non-unique member: %s" % config)
        self.use = use
        self.questionnaire_options =  questionnaire_options or []
        self.q = (questionnaire_class or Questionnaire)(self)
        self.configs = {}

    def __repr__(self):
        return "<ConfigManager configs(%s) use(%s)>" % (self.configs.keys(), self.use)

    def __getattr__(self, name):
        if not self.configs:
            raise GPyPiConfigurationError("At least one config file must be used.")

        if name not in Config.allowed_options:
            raise GPyPiConfigurationError("No such option in Config.allowed_options: %s" % name)

        for config_name in self.use:
            value = self.configs.get(config_name, {}).get(name, None)
            log.debug("Got %r from %s", value, config_name)

            if value is not None:
                return value
            else:
                continue

        return self.default_or_question(name)

    def default_or_question(self, name):
        """When no value is retrieved from :attr:`ConfigManager.configs`,
        :class:`Questionnaire` is used for interactive request if ``name``
        is in :attr:`ConfigManager.questionnaire_options`. Otherwise, default
        is used.

        :param name: Option name to be processed
        :param type: string
        :returns: config value

        """
        if name in self.questionnaire_options:
            return self.q.ask(name)
        else:
            return Config.allowed_options[name][2]

    @classmethod
    def load_from_ini(cls, path_to_ini, section="config_manager"):
        """Load :class:`ConfigManager` from ini file. Also populates
        ``Config.configs[ini]``.

        :param path_to_ini: Filesystem path to ini file
        :type path_to_ini: string
        :param section: ini section to be used for :class:`ConfigManager` configuration
        :type section: string
        """
        if not os.path.exists(path_to_ini):
            shutil.copy(cls.INI_TEMPLATE_PATH, path_to_ini)
            log.info('Config was generated at %s', path_to_ini)

        config = SafeConfigParser()
        config.read(path_to_ini)
        config_mgr = dict(config.items(section))

        use = config_mgr.get('use', '').split()
        q_options = config_mgr.get('questionnaire_options', '').split()

        mgr = cls(use, q_options)
        mgr.configs['ini'] = Config.from_ini(path_to_ini)
        return mgr


class Questionnaire(object):
    """Class that handles interactive shell questions when
    no :class:`Config` instance provides the value for requested
    option.
    """
    IS_FIRST_QUESTION = True

    def __init__(self, options):
        self.options = options

    def ask(self, name, input_f=raw_input):
        """Ask for a config value.

        :param name: Name of config option to be retrieved
        :type name: string
        :param input_f: function to do the asking
        :type: input_f: function
        :returns: Config value or if given option not valid, ask again.

        """
        if self.IS_FIRST_QUESTION:
            self.print_help()

        # TODO: integrate in logging
        if self.options.nocolors:
            msg = "%s [%r]: "
        else:
            msg = colorize("GOOD", " * ") + "%s" + colorize("BRACKET", " [")\
                + "%r" + colorize("BRACKET", ']') + ": "

        option = Config.allowed_options[name]
        answer = input_f(msg % (option[0].title(), option[2])) or option[2]

        try:
            return Config.validate(name, answer)
        except GPyPiValidationError, e:
            log.error(e)
            return self.ask(name, input_f)

    def print_help(self):
        """Print short description that interactive mode is turned on.

        Will print only once.
        """
        log.info("You are using interactive mode for configuration.")
        log.info("Answer questions with configuration value or press enter")
        log.info("to use default value printed in brackets.")

        self.IS_FIRST_QUESTION = False
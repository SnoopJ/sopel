"""Useful miscellaneous tools and shortcuts for Sopel plugins

*Availability: 3+*
"""

# tools.py - Sopel misc tools
# Copyright 2008, Sean B. Palmer, inamidst.com
# Copyright © 2012, Elad Alfassa <elad@fedoraproject.org>
# Copyright 2012, Elsie Powell, embolalia.com
# Licensed under the Eiffel Forum License 2.

# https://sopel.chat

from __future__ import annotations

import codecs
from collections import defaultdict
import logging
import os
import re
import sys
import threading
from typing import Callable

from sopel.lifecycle import deprecated  # Don't delete; maintains backward compatibility with pre-8.0 API
from ._events import events  # NOQA
from .identifiers import Identifier
from . import time, web  # NOQA


IdentifierFactory = Callable[[str], Identifier]

# Can be implementation-dependent
_regex_type = type(re.compile(''))


# Long kept for Python compatibility, but it's time we let these go.
raw_input = deprecated(  # pragma: no cover
    'Use the `input` function directly.',
    version='8.0',
    removed_in='8.1',
    func=input)
iteritems = deprecated(  # pragma: no cover
    "Use the dict object's `.items()` method directly.",
    version='8.0',
    removed_in='8.1',
    func=dict.items)
itervalues = deprecated(  # pragma: no cover
    "Use the dict object's `.values()` method directly.",
    version='8.0',
    removed_in='8.1',
    func=dict.values)
iterkeys = deprecated(  # pragma: no cover
    "Use the dict object's `.keys()` method directly.",
    version='8.0',
    removed_in='8.1',
    func=dict.keys)


@deprecated('Shim for Python 2 cross-compatibility, no longer needed. '
            'Use built-in `input()` instead.',
            version='7.1',
            warning_in='8.0',
            removed_in='8.1')
def get_input(prompt):
    """Get decoded input from the terminal (equivalent to Python 3's ``input``).

    :param str prompt: what to display as a prompt on the terminal
    :return: the user's input
    :rtype: str

    .. deprecated:: 7.1

        Use of this function will become a warning when Python 2 support is
        dropped in Sopel 8.0. The function will be removed in Sopel 8.1.

    """
    return input(prompt)


def get_sendable_message(text, max_length=400):
    """Get a sendable ``text`` message, with its excess when needed.

    :param str txt: text to send (expects Unicode-encoded string)
    :param int max_length: maximum length of the message to be sendable
    :return: a tuple of two values, the sendable text and its excess text
    :rtype: (str, str)

    We're arbitrarily saying that the max is 400 bytes of text when
    messages will be split. Otherwise, we'd have to account for the bot's
    hostmask, which is hard.

    The ``max_length`` is the max length of text in **bytes**, but we take
    care of Unicode 2-byte characters by working on the Unicode string,
    then making sure the bytes version is smaller than the max length.

    .. versionadded:: 6.6.2
    """
    unicode_max_length = max_length
    excess = ''

    while len(text.encode('utf-8')) > max_length:
        last_space = text.rfind(' ', 0, unicode_max_length)
        if last_space == -1:
            # No last space, just split where it is possible
            excess = text[unicode_max_length:] + excess
            text = text[:unicode_max_length]
            # Decrease max length for the unicode string
            unicode_max_length = unicode_max_length - 1
        else:
            # Split at the last best space found
            excess = text[last_space:]
            text = text[:last_space]

    return text, excess.lstrip()


class OutputRedirect:
    """Redirect the output to the terminal and a log file.

    A simplified object used to write to both the terminal and a log file.
    """

    def __init__(self, logpath, stderr=False, quiet=False):
        """Create an object which will log to both a file and the terminal.

        :param str logpath: path to the log file
        :param bool stderr: write output to stderr if ``True``, or to stdout
                            otherwise
        :param bool quiet: write to the log file only if ``True`` (and not to
                           the terminal)

        Create an object which will log to the file at ``logpath`` as well as
        the terminal.
        """
        self.logpath = logpath
        self.stderr = stderr
        self.quiet = quiet

    def write(self, string):
        """Write the given ``string`` to the logfile and terminal.

        :param str string: the string to write
        """
        if not self.quiet:
            try:
                if self.stderr:
                    sys.__stderr__.write(string)
                else:
                    sys.__stdout__.write(string)
            except Exception:  # TODO: Be specific
                pass

        with codecs.open(self.logpath, 'ab', encoding="utf8",
                         errors='xmlcharrefreplace') as logfile:
            try:
                logfile.write(string)
            except UnicodeDecodeError:
                # we got an invalid string, safely encode it to utf-8
                logfile.write(str(string, 'utf8', errors="replace"))

    def flush(self):
        """Flush the file writing buffer."""
        if self.stderr:
            sys.__stderr__.flush()
        else:
            sys.__stdout__.flush()


def stderr(string):
    """Print the given ``string`` to stderr.

    :param str string: the string to output

    This is equivalent to ``print >> sys.stderr, string``
    """
    print(string, file=sys.stderr)


def check_pid(pid):
    """Check if a process is running with the given ``PID``.

    :param int pid: PID to check
    :return bool: ``True`` if the given PID is running, ``False`` otherwise

    *Availability: POSIX systems only.*

    .. note::
        Matching the :py:func:`os.kill` behavior this function needs on Windows
        was rejected in
        `Python issue #14480 <https://bugs.python.org/issue14480>`_, so
        :py:func:`check_pid` cannot be used on Windows systems.
    """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def get_hostmask_regex(mask):
    """Get a compiled regex pattern for an IRC hostmask

    :param str mask: the hostmask that the pattern should match
    :return: a compiled regex pattern matching the given ``mask``
    :rtype: :ref:`re.Pattern <python:re-objects>`
    """
    mask = re.escape(mask)
    mask = mask.replace(r'\*', '.*')
    return re.compile(mask + '$', re.I)


def get_logger(plugin_name):
    """Return a logger for a plugin.

    :param str plugin_name: name of the plugin
    :return: the logger for the given plugin

    This::

        from sopel import tools
        LOGGER = tools.get_logger('my_custom_plugin')

    is equivalent to this::

        import logging
        LOGGER = logging.getLogger('sopel.externals.my_custom_plugin')

    Internally, Sopel configures logging for the ``sopel`` namespace, so
    external plugins can't benefit from it with ``logging.getLogger(__name__)``
    as they won't be in the same namespace. This function uses the
    ``plugin_name`` with a prefix inside this namespace.

    .. versionadded:: 7.0
    """
    return logging.getLogger('sopel.externals.%s' % plugin_name)


class SopelMemory(dict):
    """A simple thread-safe ``dict`` implementation.

    In order to prevent exceptions when iterating over the values and changing
    them at the same time from different threads, we use a blocking lock in
    ``__setitem__`` and ``__contains__``.

    .. versionadded:: 3.1
        As ``Willie.WillieMemory``
    .. versionchanged:: 4.0
        Moved to ``tools.WillieMemory``
    .. versionchanged:: 6.0
        Renamed from ``WillieMemory`` to ``SopelMemory``
    """
    def __init__(self, *args):
        dict.__init__(self, *args)
        self.lock = threading.Lock()

    def __setitem__(self, key, value):
        """Set a key equal to a value.

        The dict is locked for other writes while doing so.
        """
        self.lock.acquire()
        result = dict.__setitem__(self, key, value)
        self.lock.release()
        return result

    def __contains__(self, key):
        """Check if a key is in the dict.

        The dict is locked for writes while doing so.
        """
        self.lock.acquire()
        result = dict.__contains__(self, key)
        self.lock.release()
        return result

    # Needed to make it explicit that we don't care about the `lock` attribute
    # when comparing/hashing SopelMemory objects.
    __eq__ = dict.__eq__
    __ne__ = dict.__ne__
    __hash__ = dict.__hash__


class SopelMemoryWithDefault(defaultdict):
    """Same as SopelMemory, but subclasses from collections.defaultdict.

    .. versionadded:: 4.3
        As ``WillieMemoryWithDefault``
    .. versionchanged:: 6.0
        Renamed to ``SopelMemoryWithDefault``
    """
    def __init__(self, *args):
        defaultdict.__init__(self, *args)
        self.lock = threading.Lock()

    def __setitem__(self, key, value):
        """Set a key equal to a value.

        The dict is locked for other writes while doing so.
        """
        self.lock.acquire()
        result = defaultdict.__setitem__(self, key, value)
        self.lock.release()
        return result

    def __contains__(self, key):
        """Check if a key is in the dict.

        The dict is locked for writes while doing so.
        """
        self.lock.acquire()
        result = defaultdict.__contains__(self, key)
        self.lock.release()
        return result


class SopelIdentifierMemory(SopelMemory):
    """Special Sopel memory that stores ``Identifier`` as key.

    This is a convenient subclass of :class:`SopelMemory` that always casts its
    keys as instances of :class:`~.identifiers.Identifier`::

        >>> from sopel import tools
        >>> memory = tools.SopelIdentifierMemory()
        >>> memory['Exirel'] = 'king'
        >>> list(memory.items())
        [(Identifier('Exirel'), 'king')]
        >>> tools.Identifier('exirel') in memory
        True
        >>> 'exirel' in memory
        True

    As seen in the example above, it is possible to perform various operations
    with both ``Identifier`` and :class:`str` objects, taking advantage of the
    case-insensitive behavior of ``Identifier``.

    As it works with :class:`~.identifiers.Identifier`, it accepts an
    identifier factory. This factory usually comes from a bot instance (see
    :meth:`bot.make_identifier()<sopel.irc.AbstractBot.make_identifier>`), like
    in the example of a plugin setup function::

        def setup(bot):
            bot.memory['my_plugin_storage'] = SopelIdentifierMemory(
                identifier_factory=bot.make_identifier,
            )

    .. note::

        Internally, it will try to do ``key = self.make_identifier(key)``,
        which will raise an exception if it cannot instantiate the key
        properly::

            >>> memory[1] = 'error'
            AttributeError: 'int' object has no attribute 'translate'

    .. versionadded:: 7.1

    .. versionchanged:: 8.0

        The parameter ``identifier_factory`` has been added to properly
        transform ``str`` into :class:`~.identifiers.Identifier`. This factory
        is stored and accessible through :attr:`make_identifier`.

    """
    def __init__(
        self,
        *args,
        identifier_factory: IdentifierFactory = Identifier,
    ) -> None:
        super().__init__(*args)
        self.make_identifier = identifier_factory
        """A factory to transform keys into identifiers."""

    def __getitem__(self, key):
        return super().__getitem__(self.make_identifier(key))

    def __contains__(self, key):
        return super().__contains__(self.make_identifier(key))

    def __setitem__(self, key, value):
        super().__setitem__(self.make_identifier(key), value)


def chain_loaders(*lazy_loaders):
    """Chain lazy loaders into one.

    :param lazy_loaders: one or more lazy loader functions
    :type lazy_loaders: :term:`function`
    :return: a lazy loader that combines all of the given ones
    :rtype: :term:`function`

    This function takes any number of lazy loaders as arguments and merges them
    together into one. It's primarily a helper for lazy rule decorators such as
    :func:`sopel.plugin.url_lazy`.

    .. important::

        This function doesn't check the uniqueness of regexes generated by
        all the loaders.

    """
    def chained_loader(settings):
        return [
            regex
            for lazy_loader in lazy_loaders
            for regex in lazy_loader(settings)
        ]
    return chained_loader

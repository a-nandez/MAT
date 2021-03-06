#!/usr/bin/env python

""" Metadata anonymisation toolkit library
"""

import logging
import mimetypes
import os
import platform
import subprocess
import xml.sax
import mimetypes

import hachoir_core.cmd_line
import hachoir_parser

import libmat.exceptions

__version__ = '0.5.4'
__author__ = 'jvoisin'

# Silence
LOGGING_LEVEL = logging.CRITICAL
hachoir_core.config.quiet = True
fname = ''

# Verbose
# LOGGING_LEVEL = logging.DEBUG
# hachoir_core.config.quiet = False
# logname = 'report.log'

logging.basicConfig(filename=fname, level=LOGGING_LEVEL)

import strippers  # this is loaded here because we need LOGGING_LEVEL


def get_logo():
    """ Return the path to the logo
    """
    if os.path.isfile(os.path.join(os.path.curdir, 'data/mat.png')):
        return os.path.join(os.path.curdir, 'data/mat.png')
    elif os.path.isfile('/usr/share/pixmaps/mat.png'):
        return '/usr/share/pixmaps/mat.png'
    elif os.path.isfile('/usr/local/share/pixmaps/mat.png'):
        return '/usr/local/share/pixmaps/mat.png'


def get_datafile_path(filename):
    """ Return the path to the given ressource
    """
    if os.path.isfile(os.path.join(os.path.curdir, 'data', filename)):
        return os.path.join(os.path.curdir, 'data', filename)
    elif os.path.isfile(os.path.join('/usr/local/share/mat/', filename)):
        return os.path.join('/usr/local/share/mat/', filename)
    elif os.path.isfile(os.path.join('/usr/share/mat/', filename)):
        return os.path.join('/usr/share/mat/', filename)


def list_supported_formats():
    """ Return a list of all locally supported fileformat.
        It parses that FORMATS file, and removes locally
        non-supported formats.
    """
    handler = XMLParser()
    parser = xml.sax.make_parser()
    parser.setContentHandler(handler)
    path = get_datafile_path('FORMATS')
    with open(path, 'r') as xmlfile:
        parser.parse(xmlfile)

    localy_supported = []
    for item in handler.list:
        if item['mimetype'].split(',')[0] in strippers.STRIPPERS:
            localy_supported.append(item)

    return localy_supported


class XMLParser(xml.sax.handler.ContentHandler):
    """ Parse the supported format xml, and return a corresponding
        list of dict
    """

    def __init__(self):
        self.dict = {}
        self.list = []
        self.content, self.key = '', ''
        self.between = False

    def startElement(self, name, attrs):
        """ Called when entering into xml tag
        """
        self.between = True
        self.key = name
        self.content = ''

    def endElement(self, name):
        """ Called when exiting a xml tag
        """
        if name == 'format':  # leaving a fileformat section
            self.list.append(self.dict.copy())
            self.dict.clear()
        else:
            content = self.content.replace('\s', ' ')
            self.dict[self.key] = content
            self.between = False

    def characters(self, characters):
        """ Concatenate the content between opening and closing tags
        """
        if self.between:
            self.content += characters


def secure_remove(filename):
    """ Securely remove the file
    """
    # I want the file removed, even if it's read-only
    try:
        os.chmod(filename, 220)
    except OSError:
        logging.error('Unable to add write rights to %s' % filename)
        raise libmat.exceptions.UnableToWriteFile

    try:
        shred = 'shred'
        if platform.system() == 'MacOS':
            shred = 'gshred'
        if not subprocess.call([shred, '--remove', filename]):
            return True
        else:
            raise OSError
    except OSError:
        logging.error('Unable to securely remove %s' % filename)

    try:
        os.remove(filename)
    except OSError:
        logging.error('Unable to remove %s' % filename)
        raise libmat.exceptions.UnableToRemoveFile

    return True


def create_class_file(name, backup, **kwargs):
    """ Return a $FILETYPEStripper() class,
        corresponding to the filetype of the given file
    """
    if not os.path.isfile(name):  # check if the file exists
        logging.error('%s is not a valid file' % name)
        return None

    if not os.access(name, os.R_OK):  # check read permissions
        logging.error('%s is is not readable' % name)
        return None

    if not os.path.getsize(name):
        # check if the file is not empty (hachoir crash on empty files)
        logging.error('%s is empty' % name)
        return None

    try:
        filename = hachoir_core.cmd_line.unicodeFilename(name)
    except TypeError:  # get rid of "decoding Unicode is not supported"
        filename = name

    parser = hachoir_parser.createParser(filename)
    if not parser:
        logging.info('Unable to parse %s with hachoir' % filename)

    mime = mimetypes.guess_type(filename)[0]
    if not mime:
        logging.info('Unable to find mimetype of %s' % filename)
        return None

    if mime == 'application/zip':  # some formats are zipped stuff
        if mimetypes.guess_type(name)[0]:
            mime = mimetypes.guess_type(name)[0]

    if mime.startswith('application/vnd.oasis.opendocument'):
        mime = 'application/opendocument'  # opendocument fileformat
    elif mime.startswith('application/vnd.openxmlformats-officedocument'):
        mime = 'application/officeopenxml'  # office openxml

    is_writable = os.access(name, os.W_OK)

    try:
        stripper_class = strippers.STRIPPERS[mime]
    except KeyError:
        logging.info('Don\'t have stripper for %s format' % mime)
        return None

    return stripper_class(filename, parser, mime, backup, is_writable, **kwargs)

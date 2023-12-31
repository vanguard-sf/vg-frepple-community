#!/usr/bin/env python

#
# Copyright (C) 2007-2013 by Johan De Taeye, frePPLe bvba
#
# This library is free software; you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
# General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import sys, os, os.path
sys.path.append(os.path.join(os.path.split(__file__)[0],'..','django'))
import py2exe, django, freppledb
from freppledb import VERSION
from distutils.core import setup

# Add default command lines
if len(sys.argv) == 1:
    sys.argv.append("py2exe")

# Figure out where the django and frepple directories are
djangodirectory = django.__path__[0]
freppledirectory = freppledb.__path__[0]

# Define what is to be included and excluded
packages = [# Required for django standalone deployment
            'django', 'email', 'cherrypy.wsgiserver', 'csv',
            'htmlentitydefs', 'HTMLParser', 'markupbase',
            # Added for PostgreSQL
            'psycopg2', 'psycopg2.extensions',
            # Added to be able to connect to SQL Server
            'adodbapi',
            # Required for the python initialization
            'site',
            # Required for reading and writing spreadsheets
            'openpyxl',
            # Added to package a more complete python library with frePPLe
            'ftplib', 'poplib', 'imaplib', 'telnetlib', 'xmlrpclib',
            'gzip', 'bz2','zipfile', 'tarfile', 'SimpleXMLRPCServer',
            # Added for unicode and internationalization
            'encodings',
           ]
includes = []
excludes = ['pydoc', 'Tkinter', 'tcl', 'Tkconstants', 'freppledb', 'cx_Oracle', 'MySQLdb']
ignores = [# Not using docutils
           'docutils', 'docutils.core', 'docutils.nodes', 'docutils.parsers.rst.roles',
           # Not using psycopg (using psycopg2 instead)
           'psycopg',
           # Not using pysqlite2 (using pysqlite3 instead)
           'pysqlite2',
           # Not using mod_python
           'mod_python', 'mod_python.util',
           # Not using memcache
           'cmemcache', 'memcache',
           # Not using markdown tags of django
           'markdown', 'textile',
           # Not using WSCGI
           'flup', 'flup.server.fcgi', 'flup.server.fcgi_fork',
           # Not using ImageFields
           'PIL', 'ImageFile',
           # Not needing special datetime handling
           'mx', 'mx.TextTools',
           # Not using yaml serialization
           'yaml',
           # Not storing templates in python eggs
           'pkg_resources', 'resource',
           # Not using the python interactive interpreter
           'IPython',
           # Not sure where django references these...
           'crypt',
           # Not using SSL
           'OpenSSL',
           # Not needed to include frePPLe's own python interface
           'frepple',
           ]

# Collect all static files to be included in the distribution.
# This includes our custom python code as well.
from distutils.command.install import INSTALL_SCHEMES
for scheme in INSTALL_SCHEMES.values(): scheme['data'] = scheme['purelib']
data_files = []
for srcdir, targetdir in [
   (os.path.join(djangodirectory,'contrib','admin','templates'), 'templates'),
   (os.path.join(djangodirectory,'contrib','admin','static'), 'static'),
   (os.path.join(djangodirectory,'conf','locale'), os.path.join('locale','django')),
   (os.path.join(djangodirectory,'contrib','auth','locale'), os.path.join('locale','auth')),
   (os.path.join(djangodirectory,'contrib','contenttypes','locale'), os.path.join('locale','contenttypes')),
   (os.path.join(djangodirectory,'contrib','sessions','locale'), os.path.join('locale','sessions')),
   (os.path.join(djangodirectory,'contrib','admin','locale'), os.path.join('locale','admin')),
   (os.path.join(djangodirectory,'contrib','messages','locale'), os.path.join('locale','messages')),
   (freppledirectory, os.path.join('custom','freppledb')),
   ]:
   root_path_length = len(srcdir) + 1
   for dirpath, dirnames, filenames in os.walk(os.path.join(srcdir)):
     # Ignore dirnames that start with '.'
     for i, dirname in enumerate(dirnames):
       if dirname.startswith('.'): del dirnames[i]
     # Append data files for this subdirectory
     data_files.append([
       os.path.join(targetdir, dirpath[root_path_length:]),
       [os.path.join(dirpath, f) for f in filenames if not f.endswith(".pyc") and not f.endswith(".pyo")]
       ])

# Run the py2exe program
setup(
    # Options
    options = {"py2exe": {
          # create a compressed zip archive
          "compressed": 1,
          # optimize the bytecode
          "optimize": 2,
          # Next option is commented out: Gives a cleaner install, but doesn't work for sqlite
          # bundle python modules in the zip file as well.
          #"bundle_files": 2,
          # content of the packaged python
          "packages": packages,
          "excludes": excludes,
          "includes": includes,
          "ignores": ignores,
          "dll_excludes": [
            # Ignore this file that is useful only in archaic windows versions
            'w9xpopen.exe',
            # Ignore these files which are windows-specific, and exist by default
            # in the Windows system folders if they are required. The files are not
            # present on windows 10 anyway.
            'api-ms-win-core-processthreads-l1-1-2.dll',
            'api-ms-win-core-sysinfo-l1-2-1.dll',
            'api-ms-win-core-heap-l2-1-0.dll',
            'api-ms-win-core-delayload-l1-1-1.dll',
            'api-ms-win-core-errorhandling-l1-1-1.dll',
            'api-ms-win-core-profile-l1-1-0.dll',
            'api-ms-win-core-libraryloader-l1-2-0.dll',
            'api-ms-win-core-string-obsolete-l1-1-0.dll',
            'api-ms-win-security-activedirectoryclient-l1-1-0.dll'
            ],
          }},
    data_files = data_files,
    # Attributes
    version = VERSION,
    description = "frePPLe web application",
    name = "frePPLe",
    author = "www.frepple.com",
    url = "http://www.frepple.com",
    # Target to build a Windows service
    service = [{
       "modules":["freppleservice"],
       "icon_resources": [(1, os.path.join("..","..","src","frepple.ico"))],
       "cmdline_style": 'pywin32',
       }],
    # Target to build the system tray application
    windows = [{
       "script": "freppleserver.py",
       "icon_resources": [(1, os.path.join("..","..","src","frepple.ico"))],
       }],
    # Target to build a console application
    console = [{
       "script": "frepplectl.py",
       "icon_resources": [(1, os.path.join("..","..","src","frepple.ico"))],
       }],
    # Name of the zip file with the bytecode of the Python library.
    # This zip file with the name mentioned below is automatically included
    # in the Python search path (while the default output file "library.zip"
    # isn't)
    zipfile = "python%d%d.zip" % (sys.version_info[0], sys.version_info[1])
    )

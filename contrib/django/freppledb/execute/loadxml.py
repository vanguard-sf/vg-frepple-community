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

from __future__ import print_function
import os
import sys
from datetime import datetime

from django.db import DEFAULT_DB_ALIAS
from django.conf import settings

# Send the output to a logfile
try:
  db = os.environ['FREPPLE_DATABASE'] or DEFAULT_DB_ALIAS
except:
  db = DEFAULT_DB_ALIAS
if db == DEFAULT_DB_ALIAS:
  frepple.settings.logfile = os.path.join(settings.FREPPLE_LOGDIR, 'frepple.log')
else:
  frepple.settings.logfile = os.path.join(settings.FREPPLE_LOGDIR, 'frepple_%s.log' % db)

# Use the test database if we are running the test suite
if 'FREPPLE_TEST' in os.environ:
  settings.DATABASES[db]['NAME'] = settings.DATABASES[db]['TEST_NAME']
  if 'TEST_CHARSET' in os.environ:
    settings.DATABASES[db]['CHARSET'] = settings.DATABASES[db]['TEST_CHARSET']
  if 'TEST_COLLATION' in os.environ:
    settings.DATABASES[db]['COLLATION'] = settings.DATABASES[db]['TEST_COLLATION']
  if 'TEST_USER' in os.environ:
    settings.DATABASES[db]['USER'] = settings.DATABASES[db]['TEST_USER']

# Welcome message
if settings.DATABASES[db]['ENGINE'] == 'django.db.backends.sqlite3':
  print("frePPLe on %s using sqlite3 database '%s'" % (
    sys.platform,
    'NAME' in settings.DATABASES[db] and settings.DATABASES[db]['NAME'] or ''
    ))
else:
  print("frePPLe on %s using %s database '%s' as '%s' on '%s:%s'" % (
    sys.platform,
    'ENGINE' in settings.DATABASES[db] and settings.DATABASES[db]['ENGINE'] or '',
    'NAME' in settings.DATABASES[db] and settings.DATABASES[db]['NAME'] or '',
    'USER' in settings.DATABASES[db] and settings.DATABASES[db]['USER'] or '',
    'HOST' in settings.DATABASES[db] and settings.DATABASES[db]['HOST'] or '',
    'PORT' in settings.DATABASES[db] and settings.DATABASES[db]['PORT'] or ''
    ))

print("\nStart exporting static model to the database at", datetime.now().strftime("%H:%M:%S"))
from freppledb.execute.export_database_static import exportStaticModel
exportStaticModel(database=db).run()

print("\nFinished loading XML data at", datetime.now().strftime("%H:%M:%S"))

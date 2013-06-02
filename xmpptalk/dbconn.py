#
# (C) Copyright 2012-2013 lilydjwg <lilydjwg@gmail.com>
#
# This file is part of xmpptalk.
#
# xmpptalk is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# xmpptalk is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with xmpptalk.  If not, see <http://www.gnu.org/licenses/>.
#

'''keep a database connection'''

import logging

from pymongo.connection import Connection

_db = None
logger = logging.getLogger(__name__)

def connect(*args, **kwargs):
  '''connect to the database and initilize the global ``_db`` variable'''
  global _db
  logger.info('connecting to database...')
  logger.debug('database args are: %r, %r', *args, **kwargs)
  _db = Connection(*args, **kwargs)
  logger.info('database connected')

  #TODO Auth

def get_db():
  return _db

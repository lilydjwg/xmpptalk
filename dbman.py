#
# (C) Copyright 2012 lilydjwg <lilydjwg@gmail.com>
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
import models
models.init()

from models import connection
from models import User, Log, Group
import config

def setup_user_collection():
  col = connection[User.__database__][User.__collection__]
  User.generate_index(col)

def setup_log_collection():
  db = connection[Log.__database__]
  #http://www.mongodb.org/display/DOCS/Capped+Collections
  db.create_collection(
    Log.__collection__,
    capped=True,
    size=getattr(config, 'log_size', 524288),
)

def setup_group_collection():
  col = connection[Group.__database__][Group.__collection__]
  col.insert({'welcome': '', 'status': ''})

if __name__ == '__main__':
  setup_user_collection()
  setup_log_collection()
  setup_group_collection()

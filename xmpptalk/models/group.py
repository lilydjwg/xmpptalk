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

from .dbconn import get_db

_colname = 'group'

class GroupInfo:
  welcome = None
  status = None

  def __init__(self, default_welcome):
    self.col = get_db()[_colname]
    self.default_welcome = default_welcome

  @property
  def welcome(self):
    if self.welcome is not None:
      return self.welcome

    info = self.col.find_one()
    if info is None:
      welcome = self.default_welcome
    else:
      welcome = info['welcome']
    self.welcome = welcome
    return welcome

  @welcome.setter
  def welcome(self, welcome):
    self.col.update({}, {'$set': {'welcome': welcome}}, upsert=True)
    self.welcome = welcome

  @property
  def status(self):
    if self.status is not None:
      return self.status

    info = self.col.find_one()
    if info is None:
      status = ''
    else:
      status = info['status']
    self.status = status
    return status

  @status.setter
  def status(self, status):
    self.col.update({}, {'$set': {'status': status}}, upsert=True)
    self.status = status

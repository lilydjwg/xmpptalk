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
import re
import datetime
import unicodedata
import logging

from pymongo.errors import DuplicateKeyError, OperationFailure
from mongokit import Connection
from mongokit import Document as Doc
from mongokit.schema_document import ValidationError

from misc import *
import config

logger = logging.getLogger(__name__)
collection_prefix = getattr(config, 'connection_prefix', '')

def validate_jid(jid):
  if not re_jid.match(jid):
    raise ValidationError(_('wrong jid format: %s') % jid)
  return True

def validate_nick(nick):
  '''`nick` should be already stripped if you only allow spaces in between'''
  if not nick:
    raise ValidationError(_('no nickname provided'))
  l = width(nick)
  if l > config.nick_maxwidth:
    raise ValidationError(_('nickname too long (%d-character width), max is %d') \
                         % (l, config.nick_maxwidth))
  for i in nick:
    cat = unicodedata.category(i)
    # Lt & Lm are special chars
    if (not (cat.startswith('L') or cat.startswith('N')) or cat in ('Lm', 'Lt')) \
       and i not in config.nick_allowed_symbol:
      raise ValidationError(_("nickname `%s' contains disallowed character: '%c'") \
                            % (nick, i))
  return True

class Document(Doc):
  __database__ = config.database
  use_dot_notation = True

  @classmethod
  def generate_index(cls, collection):
    # creating index if needed
    for index in cls.indexes:
      unique = False
      if 'unique' in index.keys():
        unique = index['unique']
      ttl = 300
      if 'ttl' in index.keys():
        ttl = index['ttl']
      if isinstance(index['fields'], tuple):
        fields = [index['fields']]
      elif isinstance(index['fields'], str):
        fields = [(index['fields'], 1)]
      else:
        fields = []
        for field in index['fields']:
          if isinstance(field, str):
            field = (field, 1)
          fields.append(field)
      logger.debug('Creating index for %s' % index['fields'])
      collection.ensure_index(fields, unique=unique, ttl=ttl)
      err = collection.database.command('getLastError')
      if err['err']:
        raise DuplicateKeyError(err['err'], err['code'])

class User(Document):
  __collection__ = collection_prefix + 'user'
  use_schemaless = True
  structure = {
    # name it 'pm' as it's why it exists
    'allow_pm': bool,
    # accept pm except these people:
    'badpeople': [str],
    'flag': int,
    'jid': str,
    'join_date': datetime.datetime,
    'stop_until': datetime.datetime,
    'mute_until': datetime.datetime,
    'last_seen': datetime.datetime,
    'last_speak': datetime.datetime,
    'msg_chars': int,
    'msg_count': int,
    'nick': str,
    'nick_changes': int,
    'nick_lastchange': datetime.datetime,
  }
  indexes = [{
    'fields': 'jid',
    'unique': True,
  }, {
    'fields': 'nick',
    # we can have a lot of users without nicknames
    'unique': False,
  }]
  default_values = {
    'flag': PERM_USER,
    'allow_pm': True,
    'join_date': datetime.datetime.utcnow,
    'stop_until': datetime.datetime.utcnow,
    'mute_until': datetime.datetime.utcnow,
    'msg_chars': 0,
    'msg_count': 0,
    'nick_changes': 0,
  }
  required_fields = ['jid']
  validators = {
    'badpeople': lambda x: all(validate_jid(y) for y in x),
    'jid': validate_jid,
    'nick': validate_nick,
  }

class Log(Document):
  __collection__ = collection_prefix + 'log'
  structure = {
    'time': datetime.datetime,
    'jid': str,
    # This should contain the nickname in case of type == 'msg'
    'msg': str,
  }
  validators = {
    'jid': validate_jid,
  }
  default_values = {
    'time': datetime.datetime.utcnow,
  }

  def find(self, n, in_=None):
    '''
    find `n` recent messages in `in_` minutes in chronological order.
    '''
    if in_ is not None:
      if isinstance(in_, datetime.datetime):
        after = in_
      else:
        after = datetime.datetime.utcnow() - datetime.timedelta(minutes=in_)
      query = {'time': {'$gt': after}}
    else:
      query = None
    l = list(super().find(query).sort('$natural', -1).limit(n))
    l.reverse()
    return l

class Group(Document):
  __collection__ = collection_prefix + 'group'
  use_schemaless = True
  structure = {
    'welcome': str,
    'status': str,
  }

def init():
  global connection
  logger.info('connecting to database...')
  conn_args = getattr(config, 'connection', {})
  connection = Connection(**conn_args)
  logger.info('database connected')

  if getattr(config, 'database_auth', None):
    logger.info('authenticating...')
    connection[config.database].authenticate(*config.database_auth)
  try:
    connection[config.database].collection_names()
  except OperationFailure:
    logger.error('database authentication failed')
    raise
  connection.register([User, Log, Group])

def logmsg(jid=None, msg=None):
  u = connection.Log()
  u.jid = str(jid)
  u.msg = msg
  u.save()

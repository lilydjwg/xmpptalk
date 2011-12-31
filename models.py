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
    'msg_chars': int,
    'msg_count': int,
    'nick': str,
    'nick_changes': int,
    'nick_lastchange': datetime.datetime,
    'prefix': str,
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
    'join_date': NOW,
    'stop_until': NOW,
    'mute_until': NOW,
    'msg_chars': 0,
    'msg_count': 0,
    'nick_changes': 0,
    'prefix': config.user_default_prefix,
  }
  required_fields = ['jid']
  validators = {
    'badpeople': lambda x: all(validate_jid(y) for y in x),
    'jid': validate_jid,
    'nick': validate_nick,
    'prefix': lambda x: 0 < len(x) < 3,
  }

def validate_logtype(t):
  '''
  msg: conversation log
  nick: nick change
  sys: system up/down
  '''
  #TODO: use sys
  return t in ('msg', 'member', 'sys')

class Log(Document):
  __collection__ = collection_prefix + 'log'
  structure = {
    'time': datetime.datetime,
    'type': str,
    'jid': str,
    # This should contain the nickname in case of type == 'msg'
    'msg': str,
  }
  validators = {
    'jid': validate_jid,
    'type': validate_logtype,
  }
  default_values = {
    'time': NOW,
  }
  required_fields = ['type']

  def find(self, n, in_=None):
    '''
    find `n` recent messages in `in_` minutes in chronological order.
    '''
    if in_ is not None:
      after = NOW() - datetime.timedelta(minutes=in_)
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

def init_models():
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

init_models()
del init_models

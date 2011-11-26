import re
import datetime
import unicodedata
import logging

from pymongo.errors import DuplicateKeyError
from mongokit import Connection
from mongokit import Document as Doc
from mongokit.schema_document import ValidationError

from misc import *
import config

log = logging.getLogger(__name__)

def validate_jid(jid):
  if not re_jid.match(jid):
    raise ValidationError(_('wrong jid format: %s') % jid)
  return True

def validate_nick(nick):
  '''`nick` should be already stripped if you only allow spaces in between'''
  if not nick:
    raise ValidationError(_('no nickname provided'))
  if len(nick) > config.nick_maxlen:
    raise ValidationError(_('nickname too long (%d characters), max is %d') \
                         % (len(nick), config.nick_maxlen))
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
      log.debug('Creating index for %s' % index['fields'])
      collection.ensure_index(fields, unique=unique, ttl=ttl)
      err = collection.database.command('getLastError')
      if err['err']:
        raise DuplicateKeyError(err['err'], err['code'])

class User(Document):
  __collection__ = getattr(config, 'collection_user', 'user')
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
    'msg_bytes': int,
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
    # we can have a lot user without nicknames
    'unique': False,
  }]
  default_values = {
    'flag': PERM_USER,
    'join_date': datetime.datetime.utcnow,
    'stop_until': datetime.datetime.utcnow,
    'mute_until': datetime.datetime.utcnow,
    'msg_bytes': 0,
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
  #TODO: use nick and sys
  return t in ('msg', 'nick', 'sys')

class Log(Document):
  __collection__ = getattr(config, 'collection_log', 'log')
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
    'time': datetime.datetime.utcnow,
  }
  required_fields = ['type']

  def find(self, n=20, in_=None):
    '''
    find `n` recent messages in `in_` minutes in chronological order.
    `n` defaults to 20, `in_` 60 (minutes).
    '''
    if in_ is None:
      in_ = 60
    after = datetime.datetime.utcnow() - datetime.timedelta(minutes=in_)
    l = list(super().find({'time': {'$gt': after}},
                          sort=[('$natural', -1)]).limit(n))
    l.reverse()
    return l

connection = Connection()
connection.register([User, Log])

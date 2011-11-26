from pyxmpp2.jid import JID

from models import Log, connection

def log(msg, type, jid=None):
  u = connection.Log()
  u.type = type
  if isinstance(jid, JID):
    jid = str(jid)
  u.jid = jid
  u.msg = msg
  u.save()

def logmsg(jid, msg):
  log(msg, 'msg', jid)

def lognick(jid, msg):
  '''log nick changes'''
  log(msg, 'nick', jid)

def logsys(msg):
  log(msg, 'sys')

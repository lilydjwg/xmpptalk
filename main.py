#!/usr/bin/python
# -*- coding: utf-8 -*-

'''
An 'echo bot' – simple client that just confirms any presence subscriptions
and echoes incoming messages.
'''

import sys
import logging
import hashlib
from functools import lru_cache
from collections import defaultdict

from pyxmpp2.jid import JID
from pyxmpp2.message import Message
from pyxmpp2.presence import Presence
from pyxmpp2.client import Client
from pyxmpp2.settings import XMPPSettings
from pyxmpp2.interfaces import EventHandler, event_handler, QUIT
from pyxmpp2.streamevents import AuthorizedEvent, DisconnectedEvent
from pyxmpp2.interfaces import XMPPFeatureHandler
from pyxmpp2.interfaces import presence_stanza_handler, message_stanza_handler
from pyxmpp2.ext.version import VersionProvider

import config

@lru_cache()
def hashjid(jid):
  '''
  return a representation of the jid with least conflict but still keep
  confidential
  '''
  m = hashlib.md5()
  bare = '%s/%s' % (jid.local, jid.domain)
  m.update(bare.encode())
  m.update(config.salt)
  domain = m.hexdigest()[:6]
  return '%s@%s' % (jid.local, domain)

class ChatBot(EventHandler, XMPPFeatureHandler):
  '''Echo Bot implementation.'''
  def __init__(self, my_jid, settings):
    version_provider = VersionProvider(settings)
    self.client = Client(my_jid, [self, version_provider], settings)
    self.presence = defaultdict(dict)

  def run(self):
    '''Request client connection and start the main loop.'''
    self.client.connect()
    self.jid = self.client.jid
    self.client.run()

  def disconnect(self):
    '''Request disconnection and let the main loop run for a 2 more
    seconds for graceful disconnection.'''
    self.client.disconnect()
    self.client.run(timeout = 2)

  @presence_stanza_handler('subscribe')
  def handle_presence_subscribe(self, stanza):
    logging.info('{0} requested presence subscription'
                 .format(stanza.from_jid))
    presence = Presence(to_jid = stanza.from_jid.bare(),
                        stanza_type = 'subscribe')
    return [stanza.make_accept_response(), presence]

  @presence_stanza_handler('subscribed')
  def handle_presence_subscribed(self, stanza):
    logging.info('{0!r} accepted our subscription request'
                 .format(stanza.from_jid))
    return True

  @presence_stanza_handler('unsubscribe')
  def handle_presence_unsubscribe(self, stanza):
    logging.info('{0} canceled presence subscription'
                 .format(stanza.from_jid))
    presence = Presence(to_jid = stanza.from_jid.bare(),
                        stanza_type = 'unsubscribe')
    return [stanza.make_accept_response(), presence]

  @presence_stanza_handler('unsubscribed')
  def handle_presence_unsubscribed(self, stanza):
    logging.info('{0!r} acknowledged our subscrption cancelation'
                 .format(stanza.from_jid))
    return True

  @presence_stanza_handler()
  def handle_presence_available(self, stanza):
    if stanza.stanza_type not in ('available', None):
      return False

    jid = stanza.from_jid
    self.presence[jid.bare()][jid.resource] = {
      'show': stanza.show,
      'status': stanza.status,
      'priority': stanza.priority,
    }
    logging.info('%s[%s]', jid, stanza.show or 'available')
    return True

  @presence_stanza_handler('unavailable')
  def handle_presence_unavailable(self, stanza):
    jid = stanza.from_jid
    try:
      del self.presence[jid.bare()][jid.resource]
      logging.info('%s[unavailable]', jid)
    except KeyError:
      pass

  @message_stanza_handler()
  def handle_message(self, stanza):
    if stanza.body is None:
      # She's typing
      return True

    sender = stanza.from_jid
    bare = sender.bare()

    if stanza.body.startswith('-nick '):
      nick = stanza.body.split(None, 1)[1]
      old_nick = self.get_name(sender)
      self.client.roster_client.update_item(bare, nick)
      self.send_message(sender, '昵称更新成功！')
      msg = '%s 的昵称已更新为 %s。' % (old_nick, nick)
      for u in self.get_online_users():
        if u.jid != bare:
          self.send_message(u.jid, msg)
      return True

    # from cli import repl
    # repl(locals(), 'cmd.txt')
    self.send_to_all(bare, stanza.body)
    return True

  @event_handler(DisconnectedEvent)
  def handle_disconnected(self, event):
    '''Quit the main loop upon disconnection.'''
    return QUIT

  @event_handler()
  def handle_all(self, event):
    '''Log all events.'''
    logging.info('-- {0}'.format(event))

  def get_online_users(self):
    ret = [x for x in self.roster if x.subscription == 'both' and \
           self.presence[x.jid]]
    logging.debug('online buddies: %r', ret)
    return ret

  def send_to_all(self, sender, msg):
    msg = '[%s] %s' % (self.get_name(sender), msg)
    for u in self.get_online_users():
      if u.jid != sender:
        self.send_message(u.jid, msg)

  def send_message(self, receiver, msg):
      m = Message(
        stanza_type = 'chat',
        from_jid = self.jid,
        to_jid = receiver,
        body = msg,
      )
      self.send(m)

  def send(self, stanza):
    self.client.stream.send(stanza)

  def get_name(self, jid):
    if isinstance(jid, str):
      jid = JID(jid)
    else:
      jid = jid.bare()
    return self.roster[jid].name or hashjid(jid)

  @property
  def roster(self):
    return self.client.roster

def main():
  logging.basicConfig(level=logging.DEBUG)

  settings = XMPPSettings({
    'software_name': 'ChatBot',
    'password': config.password,
  })

  if config.trace:
    logging.info('enabling trace')
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    for logger in ('pyxmpp2.IN', 'pyxmpp2.OUT'):
      logger = logging.getLogger(logger)
      logger.setLevel(logging.DEBUG)
      logger.addHandler(handler)

  for logger in (
    'pyxmpp2.mainloop.base', 'pyxmpp2.expdict',
    'pyxmpp2.mainloop.poll', 'pyxmpp2.mainloop.events',
    'pyxmpp2.transport', 'pyxmpp2.mainloop.events',
  ):
      logger = logging.getLogger(logger)
      logger.setLevel(logging.INFO)

  bot = ChatBot(JID(config.jid), settings)
  try:
    bot.run()
  except KeyboardInterrupt:
    bot.disconnect()

if __name__ == '__main__':
  main()

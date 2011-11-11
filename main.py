#!/usr/bin/env python3
# vim:fileencoding=utf-8

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
from pyxmpp2.roster import RosterReceivedEvent
from pyxmpp2.interfaces import EventHandler, event_handler, QUIT, NO_CHANGE
from pyxmpp2.streamevents import AuthorizedEvent, DisconnectedEvent
from pyxmpp2.interfaces import XMPPFeatureHandler
from pyxmpp2.interfaces import presence_stanza_handler, message_stanza_handler
from pyxmpp2.ext.version import VersionProvider

import config
from messages import MessageMixin

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

class ChatBot(MessageMixin, EventHandler, XMPPFeatureHandler):
  def __init__(self, jid, settings):
    version_provider = VersionProvider(settings)
    self.client = Client(jid, [self, version_provider], settings)
    self.presence = defaultdict(dict)
    self.got_roster = False
    self.message_queue = None

  def run(self):
    self.client.connect()
    self.jid = self.client.jid
    self.client.run()

  def disconnect(self):
    '''Request disconnection and let the main loop run for a 2 more
    seconds for graceful disconnection.'''
    self.client.disconnect()
    self.client.run(timeout = 2)

  @event_handler(RosterReceivedEvent)
  def roster_received(self, stanze):
    self.got_roster = True
    q = self.message_queue
    for i in q:
      self.handle_message(*i)
    self.message_queue = None
    return True

  @message_stanza_handler()
  def message_received(self, stanza):
    if stanza.body is None:
      # She's typing
      return False

    sender = stanza.from_jid
    body = stanza.body
    self.current_jid = sender

    logging.info('[%s] %s', bare, stanza.body)

    if not self.got_roster:
      if not self.message_queue:
        self.message_queue = []
      self.message_queue.append((sender, body))
    else:
      self.handle_message(sender, body)

    return True

  def send_message(self, receiver, msg):
    m = Message(
      stanza_type = 'chat',
      from_jid = self.jid,
      to_jid = receiver,
      body = msg,
    )
    self.send(m)

  def reply(self, msg):
    self.send_message(self.current_jid, msg)

  def send(self, stanza):
    self.client.stream.send(stanza)

  @event_handler(DisconnectedEvent)
  def handle_disconnected(self, event):
    #TODO: notify admins
    return QUIT

  @property
  def roster(self):
    return self.client.roster

  def get_online_users(self):
    ret = [x for x in self.roster if x.subscription == 'both' and \
           self.presence[x.jid]]
    logging.info('%d online buddies: %r', len(ret), [x.jid for x in ret])
    return ret

  def update_roster(self, jid, name=NO_CHANGE, groups=NO_CHANGE):
    self.client.roster_client.update_item(jid, name, groups)

  @presence_stanza_handler('subscribe')
  def handle_presence_subscribe(self, stanza):
    if not self.handle_userjoin_before(stanza.from_jid):
      return False

    presence = Presence(to_jid = stanza.from_jid.bare(),
                        stanza_type = 'subscribe')
    return [stanza.make_accept_response(), presence]

  @presence_stanza_handler('subscribed')
  def handle_presence_subscribed(self, stanza):
    self.handle_userjoin(stanza.from_jid())
    return True

  @presence_stanza_handler('unsubscribe')
  def handle_presence_unsubscribe(self, stanza):
    presence = Presence(to_jid = stanza.from_jid.bare(),
                        stanza_type = 'unsubscribe')
    return [stanza.make_accept_response(), presence]

  @presence_stanza_handler('unsubscribed')
  def handle_presence_unsubscribed(self, stanza):
    self.handle_userleave(stanza.from_jid)
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
    return True

  @event_handler()
  def handle_all(self, event):
    '''Log all events.'''
    logging.info('-- {0}'.format(event))

  def send_to_all(self, sender, msg):
    msg = '[%s] %s' % (self.get_name(sender), msg)
    for u in self.get_online_users():
      if u.jid != sender:
        self.send_message(u.jid, msg)

  def get_name(self, jid):
    if isinstance(jid, str):
      jid = JID(jid)
    else:
      jid = jid.bare()
    try:
      return self.roster[jid].name or hashjid(jid)
    except KeyError:
      return hashjid(jid)

def main():
  logging.basicConfig(level=config.logging_level)

  settings = dict(
    software_name = 'ChatBot',
    # deliver here even if the admin logs in
    initial_presence = Presence(priority=30),
  )
  settings.update(config.settings)
  settings = XMPPSettings(settings)

  if config.trace:
    logging.info('enabling trace')
    for logger in ('pyxmpp2.IN', 'pyxmpp2.OUT'):
      logger = logging.getLogger(logger)
      logger.setLevel(config.logging_level)

  for logger in (
    'pyxmpp2.mainloop.base', 'pyxmpp2.expdict',
    'pyxmpp2.mainloop.poll', 'pyxmpp2.mainloop.events',
    'pyxmpp2.transport', 'pyxmpp2.mainloop.events',
  ):
      logger = logging.getLogger(logger)
      logger.setLevel(max((logging.INFO, config.logging_level)))

  bot = ChatBot(JID(config.jid), settings)
  try:
    bot.run()
  except KeyboardInterrupt:
    bot.disconnect()

if __name__ == '__main__':
  main()

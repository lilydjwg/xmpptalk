#!/usr/bin/env python3
# vim:fileencoding=utf-8

import sys
import logging
from collections import defaultdict
from xml.etree import ElementTree as ET

import pyxmpp2.exceptions
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
from pyxmpp2.iq import Iq

import config
from messages import MessageMixin
from user import UserMixin
from misc import *

#TODO: subscription 部分的处理顺序

class ChatBot(MessageMixin, UserMixin,
              EventHandler, XMPPFeatureHandler):
  got_roster = False

  def __init__(self, jid, settings):
    if 'software_name' not in settings:
      settings['software_name'] = self.__class__.__name__
    if 'software_version' not in settings:
      settings['software_version'] = __version__
    version_provider = VersionProvider(settings)
    self.client = Client(jid, [self, version_provider], settings)
    self.presence = defaultdict(dict)

  def run(self):
    self.client.connect()
    self.jid = self.client.jid
    self.client.run()

  def disconnect(self):
    '''Request disconnection and let the main loop run for a 2 more
    seconds for graceful disconnection.'''
    self.client.disconnect()
    while True:
      try:
        self.client.run(timeout = 2)
      except pyxmpp2.exceptions.StreamParseError:
        # we raise Systemexit to exit, expat says XML_ERROR_FINISHED
        pass
      else:
        break

  def handle_early_message(self):
    self.got_roster = True
    q = self.message_queue
    if q:
      for sender, msg in q:
        self.current_jid = sender
        self._cached_jid = None
        self.handle_message(msg)
      self.message_queue = None

  @event_handler(RosterReceivedEvent)
  def roster_received(self, stanze):
    self.delayed_call(2, self.handle_early_message)
    return True

  @message_stanza_handler()
  def message_received(self, stanza):
    if stanza.body is None:
      # She's typing
      return False

    sender = stanza.from_jid
    body = stanza.body
    self.current_jid = sender

    logging.info('[%s] %s', sender, stanza.body)

    if not self.got_roster:
      if not self.message_queue:
        self.message_queue = []
      self.message_queue.append((sender, body))
    else:
      self.handle_message(body)

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

  def delayed_call(self, seconds, func):
    self.client.main_loop.delayed_call(seconds, func)

  @event_handler(DisconnectedEvent)
  def handle_disconnected(self, event):
    return QUIT

  @property
  def roster(self):
    return self.client.roster

  def get_online_users(self):
    ret = [x.jid for x in self.roster if x.subscription == 'both' and \
           self.presence[x.jid]]
    logging.info('%d online buddies: %r', len(ret), ret)
    return ret

  def get_xmpp_status(self, jid):
    return sorted(self.presence[jid].values(), key=lambda x: x['priority'], reverse=True)[0]

  def update_roster(self, jid, name=NO_CHANGE, groups=NO_CHANGE):
    self.client.roster_client.update_item(jid, name, groups)

  @presence_stanza_handler('subscribe')
  def handle_presence_subscribe(self, stanza):
    sender = stanza.from_jid
    self.current_jid = sender
    if not self.handle_userjoin_before():
      return stanza.make_deny_response()

    self.handle_userjoin(action=stanza.stanza_type)

    if stanza.stanza_type.endswith('ed'):
      return True

    presence = Presence(to_jid=stanza.from_jid.bare(),
                        stanza_type='subscribe')
    return [stanza.make_accept_response(), presence]

  @presence_stanza_handler('subscribed')
  def handle_presence_subscribed(self, stanza):
    # use the same function
    return self.handle_presence_subscribe(stanza)

  @presence_stanza_handler('unsubscribe')
  def handle_presence_unsubscribe(self, stanza):
    sender = stanza.from_jid
    self.current_jid = sender
    self.handle_userleave(action=stanza.stanza_type)

    if stanza.stanza_type.endswith('ed'):
      return True

    presence = Presence(to_jid=stanza.from_jid.bare(),
                        stanza_type='unsubscribe')
    return [stanza.make_accept_response(), presence]

  presence_stanza_handler('unsubscribed')
  def handle_presence_unsubscribed(self, stanza):
    # use the same function
    return self.handle_presence_unsubscribe(stanza)

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

  def get_name(self, jid):
    if isinstance(jid, str):
      jid = JID(jid)
    else:
      jid = jid.bare()
    try:
      return self.roster[jid].name or hashjid(jid)
    except KeyError:
      return hashjid(jid)

  def get_vcard(self, jid, callback):
    '''callback is used as both result handler and error handler'''
    q = Iq(
      to_jid = jid,
      stanza_type = 'get'
    )
    vc = ET.Element("{vcard-temp}vCard")
    q.add_payload(vc)
    self.stanza_processor.set_response_handlers(q, callback, callback)
    self.send(q)

def main():
  logging.basicConfig(level=config.logging_level)

  settings = dict(
    # deliver here even if the admin logs in
    initial_presence = Presence(priority=30),
    poll_interval = 3,
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
  except (KeyboardInterrupt, SystemExit):
    pass
  finally:
    bot.disconnect()

if __name__ == '__main__':
  main()

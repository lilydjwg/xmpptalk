#!/usr/bin/env python3
# vim:fileencoding=utf-8
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

import sys
import os
import logging
import datetime
from collections import defaultdict
from functools import partial
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
from pyxmpp2.expdict import ExpiringDictionary
from pyxmpp2.iq import Iq

from misc import *
import config
import models
from models import ValidationError
from messages import MessageMixin
from user import UserMixin

class ChatBot(MessageMixin, UserMixin, EventHandler, XMPPFeatureHandler):
  got_roster = False
  message_queue = None

  def __init__(self, jid, settings):
    if 'software_name' not in settings:
      settings['software_name'] = self.__class__.__name__
    if 'software_version' not in settings:
      settings['software_version'] = __version__
    version_provider = VersionProvider(settings)
    self.client = Client(jid, [self, version_provider], settings)
    self.presence = defaultdict(dict)
    self.subscribes = ExpiringDictionary(default_timeout=5)
    self.invited = {}

  def run(self):
    self.client.connect()
    self.jid = self.client.jid.bare()
    logger.info('self jid: %r', self.jid)
    self.update_on_setstatus = set()
    self.client.run()

  def disconnect(self):
    '''Request disconnection and let the main loop run for a 2 more
    seconds for graceful disconnection.'''
    self.client.disconnect()
    while True:
      try:
        self.client.run(timeout = 2)
      except pyxmpp2.exceptions.StreamParseError:
        # we raise SystemExit to exit, expat says XML_ERROR_FINISHED
        pass
      else:
        break

  def handle_early_message(self):
    self.got_roster = True
    q = self.message_queue
    if q:
      self.now = datetime.datetime.utcnow()
      for sender, stanza in q:
        self.current_jid = sender
        self._cached_jid = None
        try:
          timestamp = stanza.as_xml().find('{urn:xmpp:delay}delay').attrib['stamp']
        except AttributeError:
          timestamp = None
        self.handle_message(stanza.body, timestamp)
      self.message_queue = None

  @event_handler(RosterReceivedEvent)
  def roster_received(self, stanze):
    self.delayed_call(2, self.handle_early_message)
    return True

  @message_stanza_handler()
  def message_received(self, stanza):
    if stanza.body is None:
      # She's typing
      return True

    sender = stanza.from_jid
    body = stanza.body
    self.current_jid = sender
    self.now = datetime.datetime.utcnow()

    logging.info('[%s] %s', sender, stanza.body)

    if not self.got_roster:
      if not self.message_queue:
        self.message_queue = []
      self.message_queue.append((sender, stanza))
    else:
      self.handle_message(body)

    logging.info('done with new message')
    return True

  def send_message(self, receiver, msg):
    if isinstance(receiver, str):
      receiver = JID(receiver)

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

  def delayed_call(self, seconds, func, *args, **kwargs):
    self.client.main_loop.delayed_call(seconds, partial(func, *args, **kwargs))

  @event_handler(DisconnectedEvent)
  def handle_disconnected(self, event):
    return QUIT

  @property
  def roster(self):
    return self.client.roster

  def get_online_users(self):
    ret = [x.jid for x in self.roster if x.subscription == 'both' and \
           str(x.jid) in self.presence]
    logging.info('%d online buddies: %r', len(ret), ret)
    return ret

  def get_xmpp_status(self, jid):
    return sorted(self.presence[str(jid)].values(), key=lambda x: x['priority'], reverse=True)[0]

  def xmpp_add_user(self, jid):
    presence = Presence(to_jid=jid, stanza_type='subscribe')
    self.send(presence)

  def xmpp_setstatus(self, status, to_jid=None):
    if isinstance(to_jid, str):
      to_jid = JID(to_jid)

    presence = Presence(status=status, to_jid=to_jid)
    self.send(presence)

  def update_roster(self, jid, name=NO_CHANGE, groups=NO_CHANGE):
    self.client.roster_client.update_item(jid, name, groups)

  def unsubscribe(self, jid, type='unsubscribe'):
    presence = Presence(to_jid=jid, stanza_type=type)
    self.send(presence)

  def subscribe(self, jid):
    self.invited[jid] = 2
    presence = Presence(to_jid=jid, stanza_type='subscribe')
    self.send(presence)

  @presence_stanza_handler('subscribe')
  def handle_presence_subscribe(self, stanza):
    logging.info('%s subscribe', stanza.from_jid)
    sender = stanza.from_jid
    bare = sender.bare()

    invited = self.invited.get(bare, False)
    if invited is not False:
      if invited is 2:
        self.invited[bare] = 1
      else:
        del self.invited[bare]
        return stanza.make_accept_response()
      # We won't deny inivted members
      self.handle_userjoin_before()
    else:
      if config.private and str(bare) != config.root:
        return stanza.make_deny_response()
      if not self.handle_userjoin_before():
        return stanza.make_deny_response()

    # avoid repeated request
    if bare not in self.subscribes:
      self.current_jid = sender
      self.now = datetime.datetime.utcnow()
      try:
        self.handle_userjoin(action=stanza.stanza_type)
      except ValidationError:
        #The server is subscribing
        pass
      self.subscribes[bare] = True

    if stanza.stanza_type.endswith('ed'):
      return stanza.make_accept_response()

    if invited is False:
      presence = Presence(to_jid=stanza.from_jid.bare(),
                          stanza_type='subscribe')
      return [stanza.make_accept_response(), presence]

  @presence_stanza_handler('subscribed')
  def handle_presence_subscribed(self, stanza):
    # use the same function
    logging.info('%s subscribed', stanza.from_jid)
    return self.handle_presence_subscribe(stanza)

  @presence_stanza_handler('unsubscribe')
  def handle_presence_unsubscribe(self, stanza):
    logging.info('%s unsubscribe', stanza.from_jid)
    sender = stanza.from_jid
    self.current_jid = sender
    self.now = datetime.datetime.utcnow()
    self.handle_userleave(action=stanza.stanza_type)

    if stanza.stanza_type.endswith('ed'):
      return stanza.make_accept_response()

    presence = Presence(to_jid=stanza.from_jid.bare(),
                        stanza_type='unsubscribe')
    return [stanza.make_accept_response(), presence]

  presence_stanza_handler('unsubscribed')
  def handle_presence_unsubscribed(self, stanza):
    # use the same function
    logging.info('%s unsubscribed', stanza.from_jid)
    return self.handle_presence_unsubscribe(stanza)

  @presence_stanza_handler()
  def handle_presence_available(self, stanza):
    if stanza.stanza_type not in ('available', None):
      return False

    jid = stanza.from_jid
    plainjid = str(jid.bare())
    self.now = datetime.datetime.utcnow()
    if plainjid not in self.presence:
      logging.info('%s[%s] (new)', jid, stanza.show or 'available')
      self.user_update_presence(plainjid)
    else:
      logging.info('%s[%s]', jid, stanza.show or 'available')

    self.presence[plainjid][jid.resource] = {
      'show': stanza.show,
      'status': stanza.status,
      'priority': stanza.priority,
    }

    if self.get_user_by_jid(plainjid) is None and plainjid != str(self.jid):
      self.current_jid = jid
      try:
        self.handle_userjoin()
      except ValidationError:
        #The server is subscribing
        pass

    if config.warnv105 and jid.resource and jid.resource.startswith('Talk.v105'):
      # No need to translate; GTalk only has a v105 for Chinese.
      self.send_message(jid, '警告：你正在使用非加密版的 GTalk v105。网络上的其它人可能会截获您的消息。这样不安全！请使用 GTalk v104 英文版或者其它 XMPP 客户端。\nGTalk 英文版: http://www.google.com/talk/index.html\nPidgin: http://www.pidgin.im/')

    return True

  @presence_stanza_handler('unavailable')
  def handle_presence_unavailable(self, stanza):
    jid = stanza.from_jid
    plainjid = str(jid.bare())
    if plainjid in self.presence:
      try:
        del self.presence[plainjid][jid.resource]
      except KeyError:
        pass
      if self.presence[plainjid]:
        logging.info('%s[unavailable] (partly)', jid)
      else:
        del self.presence[plainjid]
        self.user_disappeared(plainjid)
        logging.info('%s[unavailable] (totally)', jid)
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
      to_jid = jid.bare(),
      stanza_type = 'get'
    )
    vc = ET.Element("{vcard-temp}vCard")
    q.add_payload(vc)
    self.stanza_processor.set_response_handlers(q, callback, callback)
    self.send(q)

def runit(settings):
  bot = ChatBot(JID(config.jid), settings)
  try:
    bot.run()
    # Connection resets
    raise Exception
  except SystemExit as e:
    if e.code == CMD_RESTART:
      # restart
      bot.disconnect()
      models.connection.disconnect()
      try:
        os.close(lock_fd[0])
      except:
        pass
      logging.info('restart...')
      os.execv(sys.executable, [sys.executable] + sys.argv)
  except KeyboardInterrupt:
    pass
  finally:
    bot.disconnect()

def main():
  gp = models.connection.Group.one()
  if gp and gp.status:
    st = gp.status
  else:
    st = None
  settings = dict(
    # deliver here even if the admin logs in
    initial_presence = Presence(priority=30, status=st),
    poll_interval = 3,
  )
  settings.update(config.settings)
  settings = XMPPSettings(settings)

  if config.trace:
    logging.info('enabling trace')
    for logger in ('pyxmpp2.IN', 'pyxmpp2.OUT'):
      logger = logging.getLogger(logger)
      logger.setLevel(logging.DEBUG)

  for logger in (
    'pyxmpp2.mainloop.base', 'pyxmpp2.expdict',
    'pyxmpp2.mainloop.poll', 'pyxmpp2.mainloop.events',
    'pyxmpp2.transport', 'pyxmpp2.mainloop.events',
  ):
      logger = logging.getLogger(logger)
      logger.setLevel(max((logging.INFO, config.logging_level)))

  if config.logging_level > logging.DEBUG:
    restart_if_failed(runit, 3, args=(settings,))
  else:
    runit(settings)

if __name__ == '__main__':
  setup_logging()
  models.init()
  main()

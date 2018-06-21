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
import base64
import hashlib
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

try:
  from xmpp_receipt import ReceiptSender
except ImportError:
  ReceiptSender = None

from misc import *
import config
import models
from models import ValidationError
from messages import MessageMixin
from user import UserMixin

if getattr(config, 'conn_lost_interval_minutes', False):
  conn_lost_interval = datetime.timedelta(minutes=config.conn_lost_interval_minutes)
else:
  conn_lost_interval = None

class ChatBot(MessageMixin, UserMixin, EventHandler, XMPPFeatureHandler):
  got_roster = False
  message_queue = None
  receipt_sender = None
  ignore = set()

  def __init__(self, jid, settings, botsettings=None):
    if 'software_name' not in settings:
      settings['software_name'] = self.__class__.__name__
    if 'software_version' not in settings:
      settings['software_version'] = __version__
    version_provider = VersionProvider(settings)

    handlers = []
    if ReceiptSender:
      self.receipt_sender = rs = ReceiptSender()
      handlers.append(rs)

    handlers.extend([self, version_provider])
    self.client = Client(jid, handlers, settings)

    self.presence = defaultdict(dict)
    self.subscribes = ExpiringDictionary(default_timeout=5)
    self.invited = {}
    self.avatar_hash = None
    self.settings = botsettings

  def run(self):
    self.client.connect()
    self.jid = self.client.jid.bare()
    logger.info('self jid: %r', self.jid)
    self.update_on_setstatus = set()

    if self.receipt_sender:
      self.receipt_sender.stream = self.client.stream
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
      self.message_queue = self.__class__.message_queue = None

  @event_handler(RosterReceivedEvent)
  def roster_received(self, stanze):
    self.delayed_call(2, self.handle_early_message)
    self.delayed_call(getattr(config, 'reconnect_timeout', 24 * 3600), self.signal_connect)
    nick, avatar_type, avatar_file = (getattr(config, x, None) for x in ('nick', 'avatar_type', 'avatar_file'))
    if nick or (avatar_type and avatar_file):
      self.set_vcard(nick, (avatar_type, avatar_file))
    return True

  def signal_connect(self):
    logging.info('Schedule to re-connecting...')
    self.client.disconnect()

  @message_stanza_handler()
  def message_received(self, stanza):
    if stanza.stanza_type != 'chat':
      return True
    if not stanza.body:
      logging.info("%s message: %s", stanza.from_jid, stanza.serialize())
      return True

    sender = stanza.from_jid
    body = stanza.body
    self.current_jid = sender
    self.now = datetime.datetime.utcnow()

    logging.info('[%s] %s', sender, stanza.body)
    if '@' not in str(sender.bare()):
      logging.info('(server messages ignored)')
      return True

    if str(sender.bare()) in self.ignore:
      logging.info('(The above message is ignored on purpose)')
      return True

    if getattr(config, 'ban_russian'):
      if str(sender.bare()).endswith('.ru'):
        logging.info('(Russian messager banned)')
        return True
      elif is_russian(body):
        logging.info('(Russian message banned)')
        return True

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

  def xmpp_setstatus(self, status, to_jid=None):
    if isinstance(to_jid, str):
      to_jid = JID(to_jid)

    presence = Presence(status=status, to_jid=to_jid)
    self.send(presence)

  def update_roster(self, jid, name=NO_CHANGE, groups=NO_CHANGE):
    self.client.roster_client.update_item(jid, name, groups)

  def removeInvitation(self):
    for ri in self.roster.values():
      if ri.ask is not None:
        self.client.roster_client.remove_item(ri.jid)
        logging.info('%s removed', ri.jid)

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

    # avoid repeated request
    invited = False
    if bare not in self.subscribes:
      invited = self.invited.get(bare, False)
      if invited is not False:
        if invited == 2:
          self.invited[bare] = 1
        else:
          del self.invited[bare]
          return stanza.make_accept_response()
        # We won't deny inivted members
        self.handle_userjoin_before()
      else:
        if config.private and str(bare) != config.root:
          self.send_message(sender, _('Sorry, this is a private group, and you are not invited.'))
          return stanza.make_deny_response()
        if not self.handle_userjoin_before():
          return stanza.make_deny_response()

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

  @presence_stanza_handler('unsubscribed')
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
    if plainjid == str(self.jid):
      return

    self.now = datetime.datetime.utcnow()
    if plainjid not in self.presence:
      type = 'new'
      self.current_jid = jid
      self.user_update_presence(plainjid)
      if conn_lost_interval and self.current_user and self.current_user.last_seen and \
         self.now - self.current_user.last_seen < conn_lost_interval:
        type = 'reconnect'
        self.send_lost_message()
      logging.info('%s[%s] (%s)', jid, stanza.show or 'available', type)

      if self.roster and jid.bare() not in self.roster:
        presence = Presence(to_jid=jid.bare(), stanza_type='subscribe')
        self.send(presence)
        presence = Presence(to_jid=jid.bare(), stanza_type='subscribed')
        self.send(presence)
    else:
      if jid.resource not in self.presence[plainjid]:
        self.user_update_presence(plainjid)
      logging.info('%s[%s]', jid, stanza.show or 'available')

    self.presence[plainjid][jid.resource] = {
      'show': stanza.show,
      'status': stanza.status,
      'priority': stanza.priority,
    }

    if self.get_user_by_jid(plainjid) is None:
      try:
        self.current_jid = jid
        self.handle_userjoin()
      except ValidationError:
        #The server is subscribing
        pass

    if config.warnv105 and jid.resource and \
       jid.resource.startswith('Talk.') and not jid.resource.startswith('Talk.v104'):
      # Got a Talk.v107...
      # No need to translate; GTalk only has a v105 for Chinese.
      self.send_message(jid, '警告：你正在使用的可能是不加密的 GTalk v105 版本。网络上的其它人可能会截获您的消息。这样不安全！请使用 GTalk v104 英文版或者其它 XMPP 客户端。\nGTalk 英文版: http://www.google.com/talk/index.html\nPidgin: http://www.pidgin.im/')

    return True

  @presence_stanza_handler('unavailable')
  def handle_presence_unavailable(self, stanza):
    jid = stanza.from_jid
    plainjid = str(jid.bare())
    if plainjid in self.presence and plainjid != str(self.jid):
      try:
        del self.presence[plainjid][jid.resource]
      except KeyError:
        pass
      if self.presence[plainjid]:
        logging.info('%s[unavailable] (partly)', jid)
      else:
        del self.presence[plainjid]
        self.now = datetime.datetime.utcnow()
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

  def get_vcard(self, jid=None, callback=None):
    '''callback is used as both result handler and error handler'''
    q = Iq(
      to_jid = jid and jid.bare(),
      stanza_type = 'get',
    )
    vc = ET.Element("{vcard-temp}vCard")
    q.add_payload(vc)
    if callback:
      self.stanza_processor.set_response_handlers(q, callback, callback)
    self.send(q)

  def set_vcard(self, nick=None, avatar=None):
    self.get_vcard(callback=partial(self._set_vcard, nick, avatar))

  def _set_vcard(self, nick=None, avatar=None, stanza=None):
    #FIXME: This doesn't seem to work with jabber.org
    q = Iq(
      from_jid = self.jid,
      stanza_type = 'set',
    )
    vc = ET.Element("{vcard-temp}vCard")
    if nick is not None:
      n = ET.SubElement(vc, '{vcard-temp}FN')
      n.text = nick
    if avatar is not None:
      type, picfile = avatar
      photo = ET.SubElement(vc, '{vcard-temp}PHOTO')
      t = ET.SubElement(photo, '{vcard-temp}TYPE')
      t.text = type
      d = ET.SubElement(photo, '{vcard-temp}BINVAL')
      data = open(picfile, 'rb').read()
      d.text = base64.b64encode(data).decode('ascii')
      self.avatar_hash = hashlib.new('sha1', data).hexdigest()

    q.add_payload(vc)
    self.stanza_processor.set_response_handlers(
      q, self._set_vcard_callback, self._set_vcard_callback)
    self.send(q)

  def _set_vcard_callback(self, stanza):
    if stanza.stanza_type == 'error':
      logging.error('failed to set my vCard.')
    else:
      logging.info('my vCard set.')
      self.update_presence()

  def update_presence(self):
    #TODO: update for individual users
    presence = self.settings['presence']
    x = ET.Element('{vcard-temp:x:update}x')
    if self.avatar_hash:
      photo = ET.SubElement(x, '{vcard-temp:x:update}photo')
      photo.text = self.avatar_hash
    presence.add_payload(x)
    self.send(presence)

def runit(settings, mysettings):
  bot = ChatBot(JID(config.jid), settings, mysettings)
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
    ChatBot.message_queue = bot.message_queue
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
  botsettings = {
    'presence': settings['initial_presence'],
  }
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
    restart_if_failed(runit, 3, args=(settings, botsettings))
  else:
    runit(settings, botsettings)

if __name__ == '__main__':
  setup_logging()
  models.init()
  main()

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
import logging
import urllib.request
import urllib.parse
import traceback

import config

logger = logging.getLogger(__name__)

re_youren = re.compile(r'有人在?吗.{,3}')
re_link = re.compile(r' <https?://(?!i.imgur.com/)[^>]+>')
re_link_js = re.compile(r' <javascript:[^>]+>')

filtered_message_func = (
  lambda s: s.startswith("I'm currently away and will reply as soon as I return to eBuddy on my "),
)
filtered_message = {
  'This is an autoreply: I am currently not available. Please leave your message, and I will get back to you as soon as possible.',
  '你好，我现在有事情不在，一会再和您联系',
  'A music messaging session has been requested. Please click the MM icon to accept.',
  '请求了音乐信使会话。请单击 MM 图标接受。',
  '<ding>', # Smack 客户端的「抖屏」
  '我已通过IM+登录在我的iPad。现在IM+已关闭，我会在IM+下次启动时看到你的消息。',
}

def cache_clear(self, msg):
  if msg == 'cache_clear':
    self.user_get_nick.cache_clear()
    self.reply('ok.')
    return True

def autoreply(self, msg):
  msg = msg.strip()
  if msg in ('test', '测试'):
    self.reply(msg + ' ok.')
  elif len(msg) < 8 and re_youren.match(msg):
    self.reply('查看在线用户请使用 %sonline 命令。' % config.prefix)
  else:
    return False
  return True

def filter_autoreply(self, msg):
  if msg in filtered_message:
    self.reply('请不要设置自动回复或者其它自动发送的消息。')
    return True
  else:
    for f in filtered_message_func:
      if f(msg):
        return True
    return False

def remove_links(self, msg):
  '''remove massive links cause by pasting'''
  links = re_link.findall(msg)
  if len(links) != 1:
    msg = re_link.sub('', msg)
  msg = re_link_js.sub('', msg)
  return msg

def post_code(msg):
  '''将代码贴到网站，返回 URL 地址 或者 None（失败）'''
  form_data = urllib.parse.urlencode({'vimcn': msg}).encode('utf-8')
  try:
    result = urllib.request.urlopen('http://p.vim-cn.com/', form_data)
    return result.read().decode('utf-8').strip() + '/text' # 默认当作纯文本高亮
  except:
    logger.error(traceback.format_exc())
    return

def long_text_check(self, msg):
  if len(msg) > 500 or msg.count('\n') > 5:
    msgbody = post_code(msg)
    if msgbody:
      self.reply('内容过长，已贴至 %s 。' % msgbody)
      firstline = ''
      lineiter = iter(msg.split('\n'))
      try:
        while not firstline:
          firstline = next(lineiter)
      except StopIteration:
        pass
      if len(firstline) > 40:
        firstline = firstline[:40]
      msgbody += '\n' + firstline + '...'
      return msgbody
    else:
      logger.warn('转贴代码失败，代码长度 %d' % len(msg))
      self.reply('大段文本请贴 paste 网站。\n'
                 '如 http://paste.ubuntu.org.cn/ http://slexy.org/\n'
                 'PS: 自动转帖失败！')
      return True

message_plugin_early = [
]
message_plugin = [
  cache_clear, autoreply, filter_autoreply,
  remove_links,
  long_text_check,
]

import re

re_youren = re.compile(r'有人在?吗.{,3}')
re_link = re.compile(r' <https?://(?!i.imgur.com/)[^>]+>')
re_link_js = re.compile(r' <javascript:[^>]+>')

filtered_message = (
  "I'm currently away and will reply as soon as I return to eBuddy on my iPod touch",
  'This is an autoreply: I am currently not available. Please leave your message, and I will get back to you as soon as possible.',
  '你好，我现在有事情不在，一会再和您联系',
  'A music messaging session has been requested. Please click the MM icon to accept.',
)

def debug(self, msg):
  '''debug things; unregister in production!'''
  if msg == 'cli':
    import builtins
    from cli import repl
    old_ = builtins._
    repl(locals(), 'cmd.txt')
    builtins._ = old_
    return True
  elif msg == 'cache_clear':
    self.user_get_nick.cache_clear()
    self.reply('ok.')
    return True

def autoreply(self, msg):
  msg = msg.strip()
  if msg in ('test', '测试'):
    self.reply(msg + ' ok.')
  elif len(msg) < 8 and re_youren.match(msg):
    self.reply('查看在线用户请使用 %sonline 命令。' % self.current_user.prefix)
  else:
    return False
  return True

def filter_autoreply(self, msg):
  if msg in filtered_message:
    self.reply('请不要设置自动回复或者其它自动发送的消息。')
    return True
  else:
    return False

def remove_links(self, msg):
  '''remove massive links cause by pasting'''
  links = re_link.findall(msg)
  if len(links) != 1:
    msg = re_link.sub('', msg)
  msg = re_link_js.sub('', msg)
  return msg

message_plugin = [
  debug, autoreply, filter_autoreply, remove_links
]

#!/usr/bin/env python3
# vim:fileencoding=utf-8

import re
import time
import sys
from collections import defaultdict

re_color = re.compile(r'\[[0-9;]*[mK]|')
re_ping = re.compile(r'\[[^]]+\] ping$')
re_test = re.compile(r'\[[^]]+\]\s+(test|测试)\s*$')
re_cmd = re.compile(r'\[[^]]+\] -(\w+)')
re_other_msg = re.compile(r'\[[^]]+\] ')

year = time.gmtime().tm_year

def parse(l):
  l = re_color.sub('', l[:-1])
  if not l.startswith('[I '):
    return
  level, date, t, file, msg = l.split(None, 4)

  if msg == 'done with new message':
    type = 'done'
  elif re_ping.match(msg):
    type = 'ping'
  elif re_test.match(msg):
    type = 'test'
  elif re_cmd.match(msg):
    type = 'cmd_' + re_cmd.match(msg).group(1)
  elif re_other_msg.match(msg):
    type = 'chat'
  else:
    return

  t, ms = t.split('.')
  dtstr = '%s-%s %s' % (year, date, t)
  t = time.strptime(dtstr, '%Y-%m-%d %H:%M:%S')
  timestamp = int(time.mktime(t)) * 1000 + int(ms)

  return type, timestamp

def log_entry(fp):
  for l in fp:
    r = parse(l)
    if r:
      yield r

def stat(file):
  data = defaultdict(int)
  count = defaultdict(int)
  it = log_entry(open(file))
  while True:
    try:
      type1, t1 = next(it)
      type2, t2 = next(it)
      if type2 != 'done':
        #ignore it
        continue
    except StopIteration:
      break

    data[type1] += t2 - t1
    count[type1] += 1

  for k in data.keys():
    print('%s: %dms, %d entries' % (k, data[k] // count[k], count[k]))

if __name__ == '__main__':
  if len(sys.argv) != 2:
    sys.exit('no logfile provided.')
  stat(sys.argv[1])

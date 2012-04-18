#!/bin/bash -e
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

install_xz () {
  save_pwd=$PWD
  cd soft
  wget -c http://tukaani.org/xz/xz-5.0.3.tar.bz2
  tar xjf xz-5.0.3.tar.bz2
  cd xz-5.0.3
  ./configure
  make && make install
  cd "$save_pwd"
}

install_bz2 () {
  save_pwd=$PWD
  cd soft
  wget -c http://bzip.org/1.0.6/bzip2-1.0.6.tar.gz
  tar xzf bzip2-1.0.6.tar.gz
  cd bzip2-1.0.6
  make -f Makefile-libbz2_so
  make install
  ldconfig /usr/local/lib
  cd "$save_pwd"
}

install_python27 () {
  ld -lbz2 || install_bz2
  save_pwd=$PWD
  cd soft
  wget -c http://www.python.org/ftp/python/2.7/Python-2.7.tar.bz2
  tar xjf Python-2.7.tar.bz2
  cd Python-2.7
  save_lang=$LANG
  export LANG=en_US.UTF-8
  ./configure --enable-shared --with-threads --with-computed-gotos --enable-ipv6 --with-wide-unicode --with-system-expat --with-system-ffi
  make
  make install
  export LANG=$save_lang
  ldconfig /usr/local/lib
  cd "$save_pwd"
}

install_python32 () {
  which xz >/dev/null || install_xz
  save_pwd=$PWD
  cd soft
  wget -c http://www.python.org/ftp/python/3.2.2/Python-3.2.2.tar.xz
  xz -d < Python-3.2.2.tar.xz | tar x
  cd Python-3.2.2
  save_lang=$LANG
  export LANG=en_US.UTF-8
  ./configure --enable-shared --with-threads --with-computed-gotos --enable-ipv6 --with-wide-unicode --with-system-expat --with-system-ffi
  make
  make altinstall
  export LANG=$save_lang
  ldconfig /usr/local/lib
  cd /usr/local/bin; ln -s python3.2 python3
  cd "$save_pwd"
}

ln_py3 () {
  which python3 >/dev/null || {
    cd /usr/local/bin; ln -s python3.2 python3;
  }
}

install_distribute () {
  save_pwd=$PWD
  cd soft
  wget -c 'http://pypi.python.org/packages/source/d/distribute/distribute-0.6.24.tar.gz#md5=17722b22141aba8235787f79800cc452'
  tar xzf distribute-0.6.24.tar.gz
  cd distribute-0.6.24
  python3 setup.py install
  cd "$save_pwd"
}

install_git () {
  save_pwd=$PWD
  cd soft
  wget -c http://git-core.googlecode.com/files/git-1.7.9.1.tar.gz
  tar xzf git-1.7.9.1.tar.gz
  cd git-1.7.9.1
  ./configure
  make
  make install
  cd "$save_pwd"
}

install_dns () {
  save_pwd=$PWD
  cd soft
  git clone -b python3 git://www.dnspython.org/dnspython.git
  cd dnspython
  python3 setup.py install
  cd "$save_pwd"
}

install_pyxmpp2 () {
  save_pwd=$PWD
  cd soft
  git clone git://github.com/lilydjwg/pyxmpp2.git
  cd pyxmpp2
  python3 setup.py install
  cd "$save_pwd"
}

install_pymongo () {
  save_pwd=$PWD
  cd soft
  wget -c http://pypi.python.org/packages/source/p/pymongo3/pymongo3-1.9b1.tar.gz
  tar xzf pymongo3-1.9b1.tar.gz
  cd pymongo3-1.9b1
  python3 setup.py install
  cd "$save_pwd"
}

install_greenlet () {
  save_pwd=$PWD
  cd soft
  hg clone https://bitbucket.org/ambroff/greenlet
  cd greenlet
  python3 setup.py install
  cd "$save_pwd"
}

install_hg () {
  {
    which python >/dev/null && python -c 'import sys; sys.exit(sys.version_info < (2, 4))';
  } || install_python27
  save_pwd=$PWD
  cd soft
  wget -c http://mercurial.selenic.com/release/mercurial-2.1.tar.gz
  tar xzf mercurial-2.1.tar.gz
  cd mercurial-2.1
  make install-bin
  cd "$save_pwd"
}

install_mongo () {
  save_pwd=$PWD
  cd soft
  name=mongodb-linux-$(uname -m)-2.0.2
  wget -c http://fastdl.mongodb.org/linux/$name.tgz
  tar xzf $name.tgz
  cd $name
  cp bin/* /usr/local/bin
  cd "$save_pwd"
}

install_mongokit () {
  which xz >/dev/null || install_xz
  save_pwd=$PWD
  cd soft
  wget -c http://lilydjwg.is-programmer.com/user_files/lilydjwg/File/mongokit-lily.tar.xz
  mkdir -p mongokit-lily
  cd mongokit-lily
  xz -d < ../mongokit-lily.tar.xz | tar x
  cd ..
  mkdir -p /usr/local/lib/python3.2/site-packages
  cp -r mongokit-lily /usr/local/lib/python3.2/site-packages/mongokit
  cd "$save_pwd"
}

install_self () {
  which xz >/dev/null || install_xz
  save_pwd=$PWD
  cd soft
  wget -c http://lilydjwg.is-programmer.com/user_files/lilydjwg/File/xmpptalk_a040700.tar.xz
  xz -d < xmpptalk_a040700.tar.xz | tar x -C "$save_pwd"
  # git clone git://github.com/lilydjwg/xmpptalk.git
  cd "$save_pwd"
}

mkdir -p soft
which python3.2 >/dev/null && ln_py3 || { which python3 >/dev/null && python3 -c 'import sys; sys.exit(sys.version_info.minor < 2)'; } || install_python32
python3 -c 'import setuptools' 2>/dev/null || install_distribute
which git >/dev/null || install_git
python3 -c 'import dns' 2>/dev/null || install_dns
python3 -c 'import pyxmpp2' 2>/dev/null || install_pyxmpp2
python3 -c 'import pymongo' 2>/dev/null || install_pymongo
which hg >/dev/null || install_hg
python3 -c 'import greenlet' 2>/dev/null || install_greenlet
which mongo >/dev/null || install_mongo
python3 -c 'import mongokit' 2>/dev/null || install_mongokit
[ -x ./main.py ] || install_self

echo "Everything done!"

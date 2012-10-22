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

install_python3 () {
  which xz >/dev/null || install_xz
  save_pwd=$PWD
  cd soft
  wget -c http://www.python.org/ftp/python/3.3.0/Python-3.3.0.tar.xz
  xz -d < Python-3.3.0.tar.xz | tar x
  cd Python-3.3.0
  save_lang=$LANG
  export LANG=en_US.UTF-8
  ./configure --enable-shared --with-threads --with-computed-gotos --enable-ipv6 --with-system-expat --with-system-ffi
  make
  make altinstall
  export LANG=$save_lang
  ldconfig /usr/local/lib
  cd /usr/local/bin; ln -s python3.3 python3
  cd "$save_pwd"
}

ln_py3 () {
  which python3 >/dev/null || {
    cd /usr/local/bin; ln -s $1 python3; cd -
  }
}

install_distribute () {
  save_pwd=$PWD
  cd soft
  wget -c 'http://pypi.python.org/packages/source/d/distribute/distribute-0.6.30.tar.gz#md5=17722b22141aba8235787f79800cc452'
  tar xzf distribute-0.6.30.tar.gz
  cd distribute-0.6.30
  python3 setup.py install
  cd "$save_pwd"
}

install_git () {
  save_pwd=$PWD
  cd soft
  wget -c https://github.com/git/git/tarball/v1.8.0 -O git-v1.8.0.tar.gz
  tar xzf git-v1.8.0.tar.gz
  cd git-v1.8.0
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
  wget -c http://pypi.python.org/packages/source/p/pymongo/pymongo-2.3.tar.gz
  tar xzf pymongo-2.3.tar.gz
  cd pymongo-2.3
  python3 setup.py install
  cd "$save_pwd"
}

# install_hg () {
#   {
#     which python >/dev/null && python -c 'import sys; sys.exit(sys.version_info < (2, 4))';
#   } || install_python27
#   save_pwd=$PWD
#   cd soft
#   wget -c http://mercurial.selenic.com/release/mercurial-2.2.3.tar.gz
#   tar xzf mercurial-2.2.3.tar.gz
#   cd mercurial-2.2.3
#   make install-bin
#   cd "$save_pwd"
# }

install_mongo () {
  save_pwd=$PWD
  cd soft
  name=mongodb-linux-$(uname -m)-2.2.0
  wget -c http://fastdl.mongodb.org/linux/$name.tgz
  tar xzf $name.tgz
  cd $name
  cp bin/* /usr/local/bin
  cd "$save_pwd"
}

install_mongokit () {
  save_pwd=$PWD
  cd soft
  git clone git://github.com/namlook/mongokit.git
  cd mongokit
  python3 setup.py install
  dir=$(python3 -c 'import imp; print(imp.find_module("mongokit")[1])')
  cd "$dir"
  2to3 -w .
  cd "$save_pwd"
}

install_self () {
  git clone git://github.com/lilydjwg/xmpptalk.git
}

mkdir -p soft
if which python3.2 >/dev/null; then
  ln_py3 $(which python3.2)
elif which python3.3 >/dev/null; then
  ln_py3 $(which python3.3)
else
  install_python3
fi
python3 -c 'import setuptools' 2>/dev/null || install_distribute
which git >/dev/null || install_git
python3 -c 'import dns' 2>/dev/null || install_dns
python3 -c 'import pyxmpp2' 2>/dev/null || install_pyxmpp2
python3 -c 'import pymongo' 2>/dev/null || install_pymongo
which mongo >/dev/null || install_mongo
python3 -c 'import mongokit' 2>/dev/null || install_mongokit
[ -x xmpptalk/main.py ] || install_self

echo "Everything done!"

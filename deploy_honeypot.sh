#!/bin/bash

# Install required build dependencies before configuring and building dionaea.
# sudo apt-get install \
#     autoconf \
#     automake \
#     build-essential \
#     check \
#     cython3 \
#     libcurl4-openssl-dev \
#     libemu-dev \
#     libev-dev \
#     libglib2.0-dev \
#     libloudmouth1-dev \
#     libnetfilter-queue-dev \
#     libnl-dev \
#     libpcap-dev \
#     libssl-dev \
#     libtool \
#     libudns-dev \
#     python3 \
#     python3-dev \
#     python3-bson \
#     python3-yaml

# After all dependencies have been installed successfully run autreconf to build or rebuild the build scripts.
autoreconf -vi

# Run configure to configure the build scripts.
./configure \
    --disable-werror \
    --prefix=/opt/dionaea \
    --with-python=/usr/bin/python3 \
    --with-cython-dir=/usr/bin \
    --with-ev-include=/usr/include \
    --with-ev-lib=/usr/lib \
    --with-emu-lib=/usr/lib/libemu \
    --with-emu-include=/usr/include \
    --with-nl-include=/usr/include/libnl3 \
    --with-nl-lib=/usr/lib

# Now you should be able to run make to build and run make install to install the honeypot.
make
sudo make install

# Changing the ownership of some directory where files are to be written as we launch the honeypot with a swith of user and group
cd /opt/first_version_dionaea/var/dionaea/
sudo chown -R dionaea:dionaea ./

# At this point the the new honeypot can be found in the directory /opt/dionaea. 
# We can launch it on the server with the following command to lit it run in background:
nohup sudo /opt/dionaea/bin/dionaea -c /opt/dionaea/etc/dionaea/dionaea.cfg -l info -u dionaea -g dionaea -p /opt/dionaea/var/run/dionaea.pid >& /dev/null &
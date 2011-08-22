#!/usr/bin/env python
### Script provided by DataStax.

import ConfigParser

configfile = '/home/ubuntu/datastax_ami/ami.cfg'

config = ConfigParser.RawConfigParser()
config.read(configfile)
try:
    config.add_section('AMI')
    config.add_section('Cassandra')
    config.add_section('OpsCenter')
except:
    pass


def setConfig(section, variable, value):
    config.set(section, variable, value)
    with open(configfile, 'wb') as configtext:
        config.write(configtext)

def getConfig(section, variable):
    try:
        config.read(configfile)
        return config.get(section, variable.lower())
    except:
        return False

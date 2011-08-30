#!/usr/bin/env python
### Script provided by DataStax.

import os, subprocess, shlex, time
import logger
import conf

# Begin configuration this is only run once in Public Packages
if os.path.isfile('ds2_configure.py'):
    # Configure brisk variables
    logger.exe('python ds2_configure.py', False)

    # Set ulimit hard limits
    logger.pipe('echo "* soft nofile 32768"', 'sudo tee -a /etc/security/limits.conf')
    logger.pipe('echo "* hard nofile 32768"', 'sudo tee -a /etc/security/limits.conf')
    logger.pipe('echo "root soft nofile 32768"', 'sudo tee -a /etc/security/limits.conf')
    logger.pipe('echo "root hard nofile 32768"', 'sudo tee -a /etc/security/limits.conf')

# Create /raid0
logger.exe('sudo mount -a')

# Change permission back to being ubuntu's and cassandra's
logger.exe('sudo chown -hR ubuntu:ubuntu /home/ubuntu')
logger.exe('sudo chown -hR cassandra:cassandra /raid0/cassandra', False)
logger.exe('sudo chown -hR cassandra:cassandra /mnt/cassandra', False)

logger.info('Starting a background process to start OpsCenter after a given delay...')
subprocess.Popen(shlex.split('sudo -u ubuntu python ds3_after_init.py &'))

logger.info( "Printing AMI Type" )
logger.info( conf.getConfig("AMI", "Type") )

# Actually start the application
if conf.getConfig("AMI", "Type") == "Cassandra" or conf.getConfig("AMI", "Type") == "False":
    logger.info('Starting Cassandra...')
    logger.exe('sudo service cassandra restart')

elif conf.getConfig("AMI", "Type") == "Brisk":
    time.sleep(15)
    logger.info('Starting Brisk...')
    logger.exe('sudo service brisk restart')

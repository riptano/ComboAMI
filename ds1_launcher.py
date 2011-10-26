#!/usr/bin/env python
### Script provided by DataStax.

import os, subprocess, shlex, time, urllib2
import logger
import conf

# Begin configuration this is only run once in Public Packages
if os.path.isfile('ds2_configure.py'):
    # Configure DataStax variables
    read = logger.exe('python ds2_configure.py', False)
    
    stderr = read[1]
    stderr = stderr.replace('yes: standard output: Broken pipe', '').strip()
    stderr = stderr.replace('yes: write error', '').strip()

    if len(stderr) > 0:
        # TODO: later
        # logger.error("DEBUG")
        # logger.error(stderr)
        # logger.error("/DEBUG")
        pass

    # Set ulimit hard limits
    logger.pipe('echo "* soft nofile 32768"', 'sudo tee -a /etc/security/limits.conf')
    logger.pipe('echo "* hard nofile 32768"', 'sudo tee -a /etc/security/limits.conf')
    logger.pipe('echo "root soft nofile 32768"', 'sudo tee -a /etc/security/limits.conf')
    logger.pipe('echo "root hard nofile 32768"', 'sudo tee -a /etc/security/limits.conf')

# Create /raid0
logger.exe('sudo mount -a')

# Disable swap
logger.exe('sudo swapoff --all')

# Change permission back to being ubuntu's and cassandra's
logger.exe('sudo chown -hR ubuntu:ubuntu /home/ubuntu')
logger.exe('sudo chown -hR cassandra:cassandra /raid0/cassandra', False)
logger.exe('sudo chown -hR cassandra:cassandra /mnt/cassandra', False)

logger.info("AMI Type: " + str(conf.getConfig("AMI", "Type")))


# Wait for the seed node to come online
req = urllib2.Request('http://instance-data/latest/meta-data/local-ipv4')
internalip = urllib2.urlopen(req).read()

if internalip != conf.getConfig("AMI", "LeadingSeed"):
    logger.info("Waiting for seed node to come online...")
    nodetoolStatement = "nodetool -h " + conf.getConfig("AMI", "LeadingSeed") + " ring"
    logger.info(nodetoolStatement)
    stoppedErrorMsg = False
    while True:
        nodetoolOut = subprocess.Popen(shlex.split(nodetoolStatement), stderr=subprocess.PIPE, stdout=subprocess.PIPE).stdout.read()
        if (nodetoolOut.lower().find("error") == -1 and nodetoolOut.lower().find("up") and len(nodetoolOut) > 0):
            logger.info("Seed node now online!")
            time.sleep(20)
            break
        time.sleep(10)
        logger.info("Retrying seed node...")


logger.info('Starting a background process to start OpsCenter after a given delay...')
subprocess.Popen(shlex.split('sudo -u ubuntu python ds3_after_init.py &'))


# Actually start the application
if conf.getConfig("AMI", "Type") == "Community" or conf.getConfig("AMI", "Type") == "False":
    logger.info('Starting DataStax Community...')
    logger.exe('sudo service cassandra restart')

elif conf.getConfig("AMI", "Type") == "Enterprise":
    logger.info('Starting DataStax Enterprise...')
    logger.exe('sudo service dse restart')

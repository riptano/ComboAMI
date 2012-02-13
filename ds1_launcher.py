#!/usr/bin/env python
### Script provided by DataStax.

import os
import subprocess
import shlex
import time
import urllib2

import logger
import conf

def initial_configurations():
    # Begin configuration this is only run once in Public Packages
    if os.path.isfile('ds2_configure.py'):
        # Configure DataStax variables
        try:
            import ds2_configure
            ds2_configure.run()
        except:
            conf.set_config("AMI", "Error", "Exception seen in %s. Please check ~/datastax_ami/ami.log for more info." % 'ds1_launcher.py')

            logger.exception('ds1_launcher.py')


        # Set ulimit hard limits
        logger.pipe('echo "* soft nofile 32768"', 'sudo tee -a /etc/security/limits.conf')
        logger.pipe('echo "* hard nofile 32768"', 'sudo tee -a /etc/security/limits.conf')
        logger.pipe('echo "root soft nofile 32768"', 'sudo tee -a /etc/security/limits.conf')
        logger.pipe('echo "root hard nofile 32768"', 'sudo tee -a /etc/security/limits.conf')

        # Change permission back to being ubuntu's and cassandra's
        logger.exe('sudo chown -hR ubuntu:ubuntu /home/ubuntu')
        logger.exe('sudo chown -hR cassandra:cassandra /raid0/cassandra', False)
        logger.exe('sudo chown -hR cassandra:cassandra /mnt/cassandra', False)
    else:
        logger.info('Skipping initial configurations.')

def restart_tasks():
    logger.info("AMI Type: " + str(conf.get_config("AMI", "Type")))

    # Create /raid0
    logger.exe('sudo mount -a')

    # Disable swap
    logger.exe('sudo swapoff --all')

def wait_for_seed():
    # Wait for the seed node to come online
    req = urllib2.Request('http://instance-data/latest/meta-data/local-ipv4')
    internalip = urllib2.urlopen(req).read()

    if internalip != conf.get_config("AMI", "LeadingSeed"):
        logger.info("Waiting for seed node to come online...")
        nodetoolStatement = "nodetool -h " + conf.get_config("AMI", "LeadingSeed") + " ring"
        logger.info(nodetoolStatement)

        while True:
            nodetool_out = subprocess.Popen(shlex.split(nodetoolStatement), stderr=subprocess.PIPE, stdout=subprocess.PIPE).stdout.read()
            if (nodetool_out.lower().find("error") == -1 and nodetool_out.lower().find("up") and len(nodetool_out) > 0):
                logger.info("Seed node now online!")
                time.sleep(5)
                break
            time.sleep(5)
            logger.info("Retrying seed node...")

def launch_opscenter():
    logger.info('Starting a background process to start OpsCenter after a given delay...')
    subprocess.Popen(shlex.split('sudo -u ubuntu python ds3_after_init.py &'))

def start_services():
    # Actually start the application
    if conf.get_config("AMI", "Type") == "Community" or conf.get_config("AMI", "Type") == "False":
        logger.info('Starting DataStax Community...')
        logger.exe('sudo service cassandra restart')

    elif conf.get_config("AMI", "Type") == "Enterprise":
        logger.info('Starting DataStax Enterprise...')
        logger.exe('sudo service dse restart')


def run():
    initial_configurations()
    restart_tasks()
    wait_for_seed()
    launch_opscenter()
    start_services()

#!/usr/bin/env python
### Script provided by DataStax.
import base64

import exceptions
import glob
import json
import os
import random
import re
import shlex
import subprocess
import sys
import tempfile
import time
import traceback
import urllib2
import urllib

import gzip
import StringIO
from email.parser import Parser

from argparse import ArgumentParser

import logger
import conf

# Full path must be used since this script will execute at
# startup as no root user

instance_data = {}
config_data = {}
config_data['conf_path'] = os.path.expanduser("/etc/cassandra/")
config_data['opsc_conf_path'] = os.path.expanduser("/etc/opscenter/")
options = False

def exit_path(errorMsg, append_msg=False):
    if not append_msg:
        # Remove passwords from printing: -p
        p = re.search('(-p\s+)(\S*)', instance_data['userdata'])
        if p:
            instance_data['userdata'] = instance_data['userdata'].replace(p.group(2), '****')

        # Remove passwords from printing: --password
        p = re.search('(--password\s+)(\S*)', instance_data['userdata'])
        if p:
            instance_data['userdata'] = instance_data['userdata'].replace(p.group(2), '****')

        append_msg = " Aborting installation.\n\nPlease verify your settings:\n{0}".format(instance_data['userdata'])

    errorMsg += append_msg

    logger.error(errorMsg)
    conf.set_config("AMI", "Error", errorMsg)

    raise AttributeError(errorMsg)


def clear_motd():
    # To clear the default MOTD
    logger.exe('sudo rm -rf /etc/motd')
    logger.exe('sudo touch /etc/motd')

def curl_instance_data(url):
    while True:
        try:
            req = urllib2.Request(url)
            return req
        except urllib2.HTTPError:
            logger.info("Failed to grab %s..." % url)
            time.sleep(5)

def read_instance_data(req):
    data = urllib2.urlopen(req).read()
    try:
        stream = StringIO.StringIO(data)
        gzipper = gzip.GzipFile(fileobj=stream)
        return gzipper.read()
    except IOError:
        stream = StringIO.StringIO(data)
        return stream.read()

def is_multipart_mime(data):
    match = re.search('Content-Type: multipart', data)
    if match: return True

def get_user_data(req):
    data = read_instance_data(req)
    if is_multipart_mime(data):
        message = Parser().parsestr(data)
        for part in message.walk():
            if (part.get_content_type() == 'text/plaintext'):
                match = re.search('totalnodes', part.get_payload())
                if (match): return part.get_payload()
    else:
        return data

def get_ec2_data():
    conf.set_config("AMI", "CurrentStatus", "Installation started")

    # Try to get EC2 User Data
    try:
        req = curl_instance_data('http://169.254.169.254/latest/user-data/')
        instance_data['userdata'] = get_user_data(req)

        logger.info("Started with user data set to:")
        logger.info(instance_data['userdata'])

        # Trim leading Rightscale UserData
        instance_data['userdata'] = instance_data['userdata'][instance_data['userdata'].find('--'):]

        if len(instance_data['userdata']) < 2:
            raise Exception

        logger.info("Using user data:")
        logger.info(instance_data['userdata'])
    except Exception, e:
        instance_data['userdata'] = '--totalnodes 1 --version Community --clustername "Test Cluster - No AMI Parameters"'
        logger.info("No userdata found. Starting 1 node clusters, by default.")

    # Find internal instance type
    req = curl_instance_data('http://169.254.169.254/latest/meta-data/instance-type')
    instancetype = urllib2.urlopen(req).read()
    logger.info("Using instance type: %s" % instancetype)
    logger.info("meta-data:instance-type: %s" % instancetype)

    if instancetype in ['t1.micro', 'm1.small', 'm1.medium']:
        exit_path("t1.micro, m1.small, and m1.medium instances are not supported. At minimum, use an m1.large instance.")

    # Find internal IP address for seed list
    req = curl_instance_data('http://169.254.169.254/latest/meta-data/local-ipv4')
    instance_data['internalip'] = urllib2.urlopen(req).read()
    logger.info("meta-data:local-ipv4: %s" % instance_data['internalip'])

    # Find public hostname
    req = curl_instance_data('http://169.254.169.254/latest/meta-data/public-hostname')
    try:
        instance_data['publichostname'] = urllib2.urlopen(req).read()
        if not instance_data['publichostname']:
            raise
        logger.info("meta-data:public-hostname: %s" % instance_data['publichostname'])
    except:
        # For VPC's and certain setups, this metadata may not be available
        # In these cases, use the internal IP address
        instance_data['publichostname'] = instance_data['internalip']
        logger.info("meta-data:public-hostname: <same as local-ipv4>")

    # # Find public IP
    # req = curl_instance_data('http://169.254.169.254/latest/meta-data/public-ipv4')
    # try:
    #     instance_data['publicip'] = urllib2.urlopen(req).read()
    #     logger.info("meta-data:public-ipv4: %s" % instance_data['publicip'])
    # except:
    #     # For VPC's and certain setups, this metadata may not be available
    #     # In these cases, use the internal IP address
    #     instance_data['publicip'] = instance_data['internalip']
    #     logger.info("meta-data:public-ipv4: <same as local-ipv4>")

    # Find launch index for token splitting
    req = curl_instance_data('http://169.254.169.254/latest/meta-data/ami-launch-index')
    instance_data['launchindex'] = int(urllib2.urlopen(req).read())
    logger.info("meta-data:ami-launch-index: %s" % instance_data['launchindex'])

    # Find reservation-id for cluster-id and jmxpass
    req = curl_instance_data('http://169.254.169.254/latest/meta-data/reservation-id')
    instance_data['reservationid'] = urllib2.urlopen(req).read()
    logger.info("meta-data:reservation-id: %s" % instance_data['reservationid'])

    instance_data['clustername'] = instance_data['reservationid']

def vpc_workaround():
    # workaround for https://github.com/riptano/ComboAMI/issues/51

    if logger.exe('sudo ls')[1]:
        hostname = logger.exe('hostname')[0].strip()
        logger.pipe('echo -e "\n# Workaround for ComboAMI Issue #51\n%s %s"' % (instance_data['internalip'],
                                                                                hostname),
                    'sudo tee -a /etc/hosts')

def parse_ec2_userdata():
    # Setup parser
    parser = ArgumentParser()

    # Option that requires either: Enterprise or Community
    parser.add_argument("--version", action="store", type=str, dest="version")
    # Option that specifies how the ring will be divided
    parser.add_argument("--totalnodes", action="store", type=int, dest="totalnodes")
    # Option that specifies the cluster's name
    parser.add_argument("--clustername", action="store", type=str, dest="clustername")
    # Option that allows for a release version of Enterprise or Community e.g. 1.0.2
    parser.add_argument("--release", action="store", type=str, dest="release")
    # Option that forces the rpc binding to the internal IP address of the instance
    parser.add_argument("--rpcbinding", action="store_true", dest="rpcbinding", default=False)

    # Option for multi-region
    parser.add_argument("--multiregion", action="store_true", dest="multiregion", default=False)
    parser.add_argument("--seeds", action="store", dest="seeds")
    parser.add_argument("--opscenterip", action="store", dest="opscenterip")

    # Option that specifies how the number of Analytics nodes
    parser.add_argument("--analyticsnodes", action="store", type=int, dest="analyticsnodes")
    # Option that specifies how the number of Search nodes
    parser.add_argument("--searchnodes", action="store", type=int, dest="searchnodes")
    # Option that forces Hadoop analytics nodes over Spark analytics nodes
    parser.add_argument("--hadoop", action="store_true", dest="hadoop")

    # Option that specifies the CassandraFS replication factor
    parser.add_argument("--cfsreplicationfactor", action="store", type=int, dest="cfsreplication")

    # Option that specifies the username
    parser.add_argument("--username", action="store", type=str, dest="username")
    # Option that specifies the password
    parser.add_argument("--password", action="store", type=str, dest="password")

    # Option that specifies the installation of OpsCenter on the first node
    parser.add_argument("--opscenter", action="store", type=str, dest="opscenter")
    # Option that specifies an alternative reflector.php
    parser.add_argument("--reflector", action="store", type=str, dest="reflector")

    # Unsupported dev options
    # Option that allows for just configuring opscenter
    parser.add_argument("--opscenteronly", action="store_true", dest="opscenteronly")
    # Option that allows for just configuring RAID0 on the attached drives
    parser.add_argument("--raidonly", action="store_true", dest="raidonly")
    # Option that allows for an OpsCenter to enable the SSL setting
    parser.add_argument("--opscenterssl", action="store_true", dest="opscenterssl")
    # Option that enforces a bootstrapping node
    parser.add_argument("--bootstrap", action="store_true", dest="bootstrap", default=False)
    # Option that enforces vnodes
    parser.add_argument("--vnodes", action="store_true", dest="vnodes", default=False)
    # Option that allows for an emailed report of the startup diagnostics
    parser.add_argument("--email", action="store", type=str, dest="email")
    # Option that allows heapsize to be changed
    parser.add_argument("--heapsize", action="store", type=str, dest="heapsize")
    # Option that allows an interface port for OpsCenter to be set
    parser.add_argument("--opscenterinterface", action="store", type=str, dest="opscenterinterface")
    # Option that allows a custom reservation id to be set
    parser.add_argument("--customreservation", action="store", type=str, dest="customreservation")
    # Option that allows custom scripts to be executed
    parser.add_argument("--base64postscript", action="store", type=str, dest="base64postscript")

    # Grab provided reflector through provided userdata
    global options
    try:
        (options, unknown) = parser.parse_known_args(shlex.split(instance_data['userdata']))
    except:
        exit_path("One of the options was not set correctly.")

    if not options.analyticsnodes:
        options.analyticsnodes = 0
    if not options.searchnodes:
        options.searchnodes = 0

    if os.path.isfile('/etc/datastax_ami.conf'):
        if options.version and options.version.lower() == "community":
            logger.error("The Dynamic DataStax AMI will automatically install DataStax Enterprise.")
        conf.set_config("AMI", "Type", "Enterprise")
    else:
        if options.version:
            if options.version.lower() == "community":
                conf.set_config("AMI", "Type", "Community")
            elif options.version.lower() == "enterprise":
                conf.set_config("AMI", "Type", "Enterprise")
            else:
                exit_path("Invalid --version (-v) argument.")

def use_ec2_userdata():
    if not options:
        exit_path("No parsed options found.")

    if not options.totalnodes:
        exit_path("Missing required --totalnodes (-n) switch.")

    if (options.analyticsnodes + options.searchnodes) > options.totalnodes:
        exit_path("Total nodes assigned (--analyticsnodes + --searchnodes) > total available nodes (--totalnodes)")

    if conf.get_config("AMI", "Type") == "Community" and (options.cfsreplication or options.analyticsnodes or options.searchnodes):
        exit_path('CFS Replication, Analytics Nodes, and Search Node settings can only be set in DataStax Enterprise installs.')

    if options.email:
        logger.info('Setting up diagnostic email using: {0}'.format(options.email))
        conf.set_config("AMI", "Email", options.email)

    if options.clustername:
        logger.info('Using cluster name: {0}'.format(options.clustername))
        instance_data['clustername'] = options.clustername

    if options.customreservation:
        instance_data['reservationid'] = options.customreservation

    if options.seeds:
        instance_data['seeds'] = options.seeds

    if options.opscenterip:
        instance_data['opscenterip'] = options.opscenterip

    options.realtimenodes = (options.totalnodes - options.analyticsnodes - options.searchnodes)
    options.seed_indexes = [0, options.realtimenodes, options.realtimenodes + options.analyticsnodes]

    logger.info('Using cluster size: {0}'.format(options.totalnodes))
    conf.set_config("Cassandra", "TotalNodes", options.totalnodes)
    logger.info('Using seed indexes: {0}'.format(options.seed_indexes))

    if options.reflector:
        logger.info('Using reflector: {0}'.format(options.reflector))

def confirm_authentication():
    if os.path.isfile('/etc/datastax_ami.conf'):
        with open('/etc/datastax_ami.conf') as f:

            # Using this license is strictly prohibited on any AMIs other than
            # those that come pre-baked with this key.

            options.username = f.readline().strip()
            options.password = f.readline().strip()
        return

    if conf.get_config("AMI", "Type") == "Enterprise":
        if options.username and options.password:
            repo_url = "http://debian.datastax.com/enterprise"

            # Configure HTTP authentication
            password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
            password_mgr.add_password(None, repo_url, options.username, options.password)
            handler = urllib2.HTTPBasicAuthHandler(password_mgr)
            opener = urllib2.build_opener(handler)

            # Try reading from the authenticated connection
            try:
                opener.open(repo_url)
            except Exception as inst:
                # Print error message if failed
                if "401" in str(inst):
                    exit_path('Authentication for DataStax Enterprise failed. Please confirm your username and password.\n')
        elif not options.username or not options.password:
            exit_path("Both --username (-u) and --password (-p) required for DataStax Enterprise.")

def setup_repos():
    # Add repos
    if conf.get_config("AMI", "Type") == "Enterprise":
        logger.pipe('echo "deb http://{0}:{1}@debian.datastax.com/enterprise stable main"'.format(options.username, options.password), 'sudo tee /etc/apt/sources.list.d/datastax.sources.list')
    else:
        logger.pipe('echo "deb http://debian.datastax.com/community stable main"', 'sudo tee /etc/apt/sources.list.d/datastax.sources.list')

    # Add repokeys
    logger.exe('sudo apt-key add /home/ubuntu/datastax_ami/repo_keys/DataStax.key')

    # Perform the install
    logger.exe('sudo apt-get update')
    time_in_loop = time.time()
    logger.info('Update loop...')
    while time.time() - time_in_loop < 10 * 60:
        output = logger.exe('sudo apt-get update')
        if not output[1] and not 'err' in output[0].lower() and not 'failed' in output[0].lower():
            break
        time.sleep(2 + random.randint(0, 5))

    time.sleep(5)

def clean_installation():
    logger.info('Performing deployment install...')

    # Hold onto baked limits conf before installation
    logger.exe('sudo mv /etc/security/limits.d/cassandra.conf /etc/security/limits.d/cassandra.conf.bak')

    if conf.get_config("AMI", "Type") == "Community":
        if options.release and options.release.startswith('1.0'):
            cassandra_release = options.release
            if cassandra_release == '1.0.11-1':
                cassandra_release = '1.0.11'
            logger.exe('sudo apt-get install -y python-cql datastax-agent cassandra={0} dsc={1}'.format(cassandra_release, options.release))
            conf.set_config('AMI', 'package', 'dsc')
            conf.set_config('Cassandra', 'partitioner', 'random_partitioner')
        elif options.release and options.release.startswith('1.1'):
            dsc_release = cassandra_release = options.release
            if not dsc_release in ['1.1.1', '1.1.2', '1.1.3', '1.1.5']:
                dsc_release = dsc_release + '-1'
            logger.exe('sudo apt-get install -y python-cql datastax-agent cassandra={0} dsc1.1={1}'.format(cassandra_release, dsc_release))
            conf.set_config('AMI', 'package', 'dsc1.1')
            conf.set_config('Cassandra', 'partitioner', 'random_partitioner')
        elif options.release and options.release.startswith('1.2'):
            dsc_release = cassandra_release = options.release
            dsc_release = dsc_release + '-1'
            logger.exe('sudo apt-get install -y python-cql datastax-agent cassandra={0} dsc12={1}'.format(cassandra_release, dsc_release))
            conf.set_config('AMI', 'package', 'dsc12')
            conf.set_config('Cassandra', 'partitioner', 'murmur')
            conf.set_config('Cassandra', 'vnodes', 'True')
        elif options.release and options.release.startswith('2.0'):
            dsc_release = cassandra_release = options.release
            if options.release == '2.0.8':
                dsc_release = dsc_release + '-2'
            else:
                dsc_release = dsc_release + '-1'
            logger.exe('sudo apt-get install -y python-cql datastax-agent cassandra={0} dsc20={1}'.format(cassandra_release, dsc_release))
            conf.set_config('AMI', 'package', 'dsc20')
            conf.set_config('Cassandra', 'partitioner', 'murmur')
            conf.set_config('Cassandra', 'vnodes', 'True')
        elif options.release and options.release.startswith('2.1'):
            dsc_release = cassandra_release = options.release
            dsc_release = dsc_release + '-1'
            if cassandra_release == '2.1.0':
                cassandra_release = cassandra_release + '-2'
            logger.exe('sudo apt-get install -y python-cql datastax-agent cassandra={0} dsc21={1}'.format(cassandra_release, dsc_release))
            conf.set_config('AMI', 'package', 'dsc21')
            conf.set_config('Cassandra', 'partitioner', 'murmur')
            conf.set_config('Cassandra', 'vnodes', 'True')
        elif options.release and options.release.startswith('2.2'):
            dsc_release = cassandra_release = options.release
            dsc_release = dsc_release + '-1'
            logger.exe('sudo apt-get install -y python-cql datastax-agent cassandra={0} dsc22={1}'.format(cassandra_release, dsc_release))
            conf.set_config('AMI', 'package', 'dsc22')
            conf.set_config('Cassandra', 'partitioner', 'murmur')
            conf.set_config('Cassandra', 'vnodes', 'True')
        else:
            logger.exe('sudo apt-get install -y python-cql datastax-agent dsc22')
            conf.set_config('AMI', 'package', 'dsc22')
            conf.set_config('Cassandra', 'partitioner', 'murmur')
            conf.set_config('Cassandra', 'vnodes', 'True')
        logger.exe('sudo service cassandra stop')

    elif conf.get_config("AMI", "Type") == "Enterprise":
        config_data['conf_path'] = os.path.expanduser("/etc/dse/cassandra/")

        if options.release:
            install_list = 'sudo apt-get install -y dse-full={0} dse={0}'
            install_list += ' dse-demos={0} dse-hive={0} dse-libcassandra={0}'
            install_list += ' dse-libhadoop={0} dse-libhive={0} dse-libpig={0}'
            install_list += ' dse-pig={0}'
            if options.release.startswith('1'):
                logger.exe(install_list.format(options.release))
                conf.set_config('AMI', 'package', 'dse-full')
                conf.set_config('Cassandra', 'partitioner', 'random_partitioner')
            elif options.release.startswith('2'):
                install_list += ' dse-liblog4j={0} dse-libsolr={0} dse-libsqoop={0} dse-libtomcat={0}'
                if options.release.startswith('2.1') or options.release.startswith('2.2'):
                    install_list += ' dse-libmahout={0}'
                logger.exe(install_list.format(options.release))
                conf.set_config('AMI', 'package', 'dse-full')
                conf.set_config('Cassandra', 'partitioner', 'random_partitioner')
            elif options.release.startswith('3'):
                install_list += ' dse-liblog4j={0} dse-libsolr={0} dse-libsqoop={0} dse-libtomcat={0} dse-libmahout={0} dse-libhadoop-native={0}'
                logger.exe(install_list.format(options.release))
                conf.set_config('AMI', 'package', 'dse-full')
                if options.release.startswith('3.0'):
                    conf.set_config('Cassandra', 'partitioner', 'random_partitioner')
                else:
                    conf.set_config('Cassandra', 'partitioner', 'murmur')
                    conf.set_config('Cassandra', 'vnodes', 'False')
            elif options.release.startswith('4'):
                install_list += ' dse-liblog4j={0} dse-libsolr={0} dse-libsqoop={0} dse-libtomcat={0} dse-libmahout={0} dse-libhadoop-native={0}'
                if options.release[:3] in ['4.5', '4.6', '4.7']:
                    install_list += ' dse-libspark={0}'
                logger.exe(install_list.format(options.release))
                conf.set_config('AMI', 'package', 'dse-full')
                conf.set_config('Cassandra', 'partitioner', 'murmur')
                conf.set_config('Cassandra', 'vnodes', 'False')
            else:
                exit_path("--release should be in the format similar to `1.0.2-1` or `2.0`.")
        else:
            logger.exe('sudo apt-get install -y dse-full')
            conf.set_config('AMI', 'package', 'dse-full')
            conf.set_config('Cassandra', 'partitioner', 'murmur')
            conf.set_config('Cassandra', 'vnodes', 'False')
        logger.exe('sudo service dse stop')

    # Remove the presaved information from startup
    logger.exe('sudo rm -rf /var/lib/cassandra')
    logger.exe('sudo rm -rf /var/log/cassandra')
    logger.exe('sudo mkdir -p /var/lib/cassandra')
    logger.exe('sudo mkdir -p /var/log/cassandra')
    logger.exe('sudo chown -R cassandra:cassandra /var/lib/cassandra')
    logger.exe('sudo chown -R cassandra:cassandra /var/log/cassandra')

    # Replace baked image conf after installation
    logger.exe('sudo mv /etc/security/limits.d/cassandra.conf.bak /etc/security/limits.d/cassandra.conf')

def opscenter_installation():
    if instance_data['launchindex'] == 0 and options.opscenter != "no":
        logger.info('Installing OpsCenter...')
        logger.exe('sudo apt-get install -y opscenter libssl0.9.8')
        logger.exe('sudo service opscenterd stop')
        if options.opscenterssl:
            logger.exe('sudo /usr/share/opscenter/bin/setup.py')
    elif options.opscenter == "no":
        conf.set_config("OpsCenter", "NoOpsCenter", True)

def get_seed_list():
    # Read seed list from reflector
    index_set = set(options.seed_indexes)
    if options.totalnodes in index_set:
        index_set.remove(options.totalnodes)
    expected_responses = len(index_set)

    time_in_loop = time.time()
    continue_loop = True
    logger.info('Reflector loop...')
    while continue_loop:
        if time.time() - time_in_loop > 10 * 60:
            exit_path('EC2 is experiencing some issues and has not allocated all of the resources in under 10 minutes.', '\n\nAborting the clustering of this reservation. Please try again.')

        if options.reflector:
            reflector = options.reflector
        else:
            reflector = 'http://reflector2.datastax.com/reflector2.php'

        req = urllib2.Request('{0}?indexid={1}&reservationid={2}&internalip={3}&externaldns={4}&second_seed_index={5}&third_seed_index={6}'.format(
                                    reflector,
                                    instance_data['launchindex'],
                                    instance_data['reservationid'],
                                    instance_data['internalip'],
                                    instance_data['publichostname'],
                                    options.seed_indexes[1],
                                    options.seed_indexes[2]
                             ))
        req.add_header('User-agent', 'DataStaxSetup')
        try:
            response = urllib2.urlopen(req).read()
            response = json.loads(response)

            status =  "{0} Reflector: Received {1} of {2} responses from: {3}".format(
                            time.strftime("%m/%d/%y-%H:%M:%S", time.localtime()),
                            response['number_of_returned_ips'],
                            expected_responses,
                            response['seeds']
                      )
            conf.set_config("AMI", "CurrentStatus", status)
            logger.info(status)

            if response['number_of_returned_ips'] == expected_responses:
                conf.set_config("OpsCenter", "DNS", response['opscenter_dns'])

                config_data['seed_list'] = set(response['seeds'])
                config_data['opscenterseed'] = response['seeds'][0]

                continue_loop = False
            else:
                time.sleep(2 + random.randint(0, options.totalnodes / 4 + 1))
        except:
            if expected_responses == 1:
                conf.set_config("AMI", "CurrentStatus", "Bypassing reflector for 1 node cluster...")

                conf.set_config("OpsCenter", "DNS", instance_data['publichostname'])

                config_data['seed_list'] = set([instance_data['internalip']])
                config_data['opscenterseed'] = instance_data['internalip']

                continue_loop = False

            traceback.print_exc(file=sys.stdout)
            time.sleep(2 + random.randint(0, 5))

def checkpoint_info():
    if options.raidonly:
        conf.set_config("AMI", "RaidOnly", "True")
    elif options.opscenteronly:
        conf.set_config("AMI", "OpsCenterOnly", "True")
        conf.set_config("OpsCenter", "DNS", instance_data['publichostname'])
    else:
        logger.info("Seed list: {0}".format(config_data['seed_list']))
        if options.seeds:
            logger.info("OpsCenter: {0}".format(options.seeds))
        else:
            logger.info("OpsCenter: {0}".format(config_data['opscenterseed']))
        logger.info("Options: {0}".format(options))
        conf.set_config("AMI", "LeadingSeed", config_data['opscenterseed'])
    conf.set_config("AMI", "CurrentStatus", "Installation complete")

def calculate_tokens():
    if conf.get_config('Cassandra', 'partitioner') == 'random_partitioner':
        import tokentoolv2

        datacenters = [options.realtimenodes, options.analyticsnodes, options.searchnodes]
        config_data['tokens'] = tokentoolv2.run(datacenters)

def construct_yaml():
    with open(os.path.join(config_data['conf_path'], 'cassandra.yaml'), 'r') as f:
        yaml = f.read()

    # Create the seed list
    seeds_yaml = ','.join(config_data['seed_list'])

    if options.seeds:
        if options.bootstrap:
            # Do not include current node while bootstrapping
            seeds_yaml = options.seeds
        else:
            # Add current node to seed list for multi-region setups
            seeds_yaml = seeds_yaml + ',' + options.seeds

    # Set seeds for DSE/C
    p = re.compile('seeds:.*')
    yaml = p.sub('seeds: "{0}"'.format(seeds_yaml), yaml)

    # Set listen_address
    p = re.compile('listen_address:.*')
    yaml = p.sub('listen_address: {0}'.format(instance_data['internalip']), yaml)

    # Set rpc_address
    p = re.compile('rpc_address:.*')
    if options.rpcbinding:
        yaml = p.sub('rpc_address: {0}'.format(instance_data['internalip']), yaml)
    else:
        yaml = p.sub('rpc_address: 0.0.0.0', yaml)

        # needed for 2.1+
        p = re.compile('# broadcast_rpc_address:.*')
        yaml = p.sub('broadcast_rpc_address: {0}'.format(instance_data['internalip']), yaml)

    if options.multiregion:
        # multiregion: --rpcbinding is implicitly true
        yaml = p.sub('rpc_address: {0}'.format(instance_data['internalip']), yaml)
        yaml = yaml.replace('endpoint_snitch: org.apache.cassandra.locator.SimpleSnitch', 'endpoint_snitch: org.apache.cassandra.locator.Ec2MultiRegionSnitch')
        yaml = yaml.replace('endpoint_snitch: SimpleSnitch', 'endpoint_snitch: Ec2MultiRegionSnitch')
        p = re.compile('# broadcast_address: 1.2.3.4')
        req = curl_instance_data('http://169.254.169.254/latest/meta-data/public-ipv4')
        instance_data['externalip'] = urllib2.urlopen(req).read()
        logger.info("meta-data:external-ipv4: %s" % instance_data['externalip'])
        yaml = p.sub('broadcast_address: {0}'.format(instance_data['externalip']), yaml)

    # Uses the EC2Snitch for Community Editions
    if conf.get_config("AMI", "Type") == "Community":
        yaml = yaml.replace('endpoint_snitch: org.apache.cassandra.locator.SimpleSnitch', 'endpoint_snitch: org.apache.cassandra.locator.Ec2Snitch')
        yaml = yaml.replace('endpoint_snitch: SimpleSnitch', 'endpoint_snitch: Ec2Snitch')

    # Set cluster_name to reservationid
    instance_data['clustername'] = instance_data['clustername'].strip("'").strip('"')
    yaml = yaml.replace("cluster_name: 'Test Cluster'", "cluster_name: '{0}'".format(instance_data['clustername']))

    # Set auto_bootstrap
    if options.bootstrap:
        if 'auto_bootstrap' in yaml:
            p = re.compile('auto_bootstrap:.*')
            yaml = p.sub('auto_bootstrap: true', yaml)
        else:
            yaml += "\nauto_bootstrap: true\n"
    else:
        if 'auto_bootstrap' in yaml:
            p = re.compile('auto_bootstrap:.*')
            yaml = p.sub('auto_bootstrap: false', yaml)
        else:
            yaml += "\nauto_bootstrap: false\n"

    if conf.get_config('Cassandra', 'partitioner') == 'random_partitioner':
        # Construct token for an equally split ring
        logger.info('Cluster tokens: {0}'.format(config_data['tokens']))

        if instance_data['launchindex'] < options.seed_indexes[1]:
            token = config_data['tokens'][0][instance_data['launchindex']]

        if options.seed_indexes[1] <= instance_data['launchindex'] and instance_data['launchindex'] < options.seed_indexes[2]:
            token = config_data['tokens'][1][instance_data['launchindex'] - options.realtimenodes]

        if options.seed_indexes[2] <= instance_data['launchindex']:
            token = config_data['tokens'][2][instance_data['launchindex'] - options.realtimenodes - options.analyticsnodes]

        p = re.compile( 'initial_token:.*')
        yaml = p.sub('initial_token: {0}'.format(token), yaml)

    elif conf.get_config('Cassandra', 'partitioner') == 'murmur':
        if conf.get_config('Cassandra', 'vnodes') == 'True' or options.vnodes:
            p = re.compile( '# num_tokens:.*')
            yaml = p.sub('num_tokens: 256', yaml)
        else:
            if instance_data['launchindex'] < options.seed_indexes[1]:
                tokens = [((2**64 / options.realtimenodes) * i) - 2**63 for i in range(options.realtimenodes)]
                token = str(tokens[instance_data['launchindex']])

            if options.seed_indexes[1] <= instance_data['launchindex'] and instance_data['launchindex'] < options.seed_indexes[2]:
                tokens = [((2**64 / options.analyticsnodes) * i) - 2**63 for i in range(options.analyticsnodes)]
                token = str(tokens[instance_data['launchindex'] - options.realtimenodes] + 10000)

            if options.seed_indexes[2] <= instance_data['launchindex']:
                tokens = [((2**64 / options.searchnodes) * i) - 2**63 for i in range(options.searchnodes)]
                token = str(tokens[instance_data['launchindex'] - options.realtimenodes - options.analyticsnodes] + 20000)

            p = re.compile( 'initial_token:.*')
            yaml = p.sub('initial_token: {0}'.format(token), yaml)

    with open(os.path.join(config_data['conf_path'], 'cassandra.yaml'), 'w') as f:
        f.write(yaml)

    logger.info('cassandra.yaml configured.')

def construct_opscenter_conf():
    try:
        with open(os.path.join(config_data['opsc_conf_path'], 'opscenterd.conf'), 'r') as f:
            opsc_conf = f.read()

        # Configure OpsCenter
        opsc_conf = opsc_conf.replace('port = 8080', 'port = 7199')
        opsc_conf = opsc_conf.replace('interface = 127.0.0.1', 'interface = 0.0.0.0')

        conf.set_config("OpsCenter", "port", 8888)
        if options.opscenterinterface:
            conf.set_config("OpsCenter", "port", options.opscenterinterface)
            opsc_conf = opsc_conf.replace('port = 8888', 'port = %s' % options.opscenterinterface)

        if options.opscenterssl:
            opsc_conf += '\n[agents]\n' \
                         'use_ssl = true'

        with open(os.path.join(config_data['opsc_conf_path'], 'opscenterd.conf'), 'w') as f:
            f.write(opsc_conf)

        logger.info('opscenterd.conf configured.')
    except:
        logger.info('opscenterd.conf not configured since conf was unable to be located.')

def construct_opscenter_cluster_conf():
    cluster_conf = re.sub(r'[\W]+', '', re.sub(r'\s', '_', instance_data['clustername']))
    cluster_conf = cluster_conf if cluster_conf else 'Test_Cluster'
    cluster_conf = '%s.conf' % cluster_conf

    try:
        opsc_cluster_path = os.path.join(config_data['opsc_conf_path'], 'clusters')
        if not os.path.exists(opsc_cluster_path):
            os.mkdir(opsc_cluster_path)

        opsc_cluster_conf = """[jmx]
username =
password =
port = 7199

[cassandra]
username =
seed_hosts = {0}
api_port = 9160
password =
"""

        # Configure OpsCenter Cluster
        if options.opscenterip:
            opsc_cluster_conf = opsc_cluster_conf.format(options.opscenterip)
        else:
            opsc_cluster_conf = opsc_cluster_conf.format(config_data['opscenterseed'])

        with open(os.path.join(opsc_cluster_path, cluster_conf), 'w') as f:
            f.write(opsc_cluster_conf)

        logger.info('opscenter/%s configured.' % cluster_conf)
    except:
        logger.info('opscenter/%s not configured since opscenter was unable to be located.' % cluster_conf)

def construct_env():
    with open(os.path.join(config_data['conf_path'], 'cassandra-env.sh'), 'r') as f:
        cassandra_env = f.read()

    # Clear commented line
    cassandra_env = cassandra_env.replace('# JVM_OPTS="$JVM_OPTS -Djava.rmi.server.hostname=<public name>"', 'JVM_OPTS="$JVM_OPTS -Djava.rmi.server.hostname=<public name>"')

    # Set JMX hostname
    settings = 'JVM_OPTS="$JVM_OPTS -Djava.rmi.server.hostname={0}"\n'.format(instance_data['internalip'])

    # Perform the replacement
    p = re.compile('JVM_OPTS="\$JVM_OPTS -Djava.rmi.server.hostname=(.*\s*)*?#')
    cassandra_env = p.sub('{0}\n\n#'.format(settings), cassandra_env)

    if options.heapsize:
        if len(options.heapsize.split(',')) == 2:
            max_heap = options.heapsize.split(',')[0].strip()
            new_size = options.heapsize.split(',')[1].strip()
            cassandra_env = cassandra_env.replace('#MAX_HEAP_SIZE="4G"', 'MAX_HEAP_SIZE="%s"' % max_heap)
            cassandra_env = cassandra_env.replace('#HEAP_NEWSIZE="800M"', 'HEAP_NEWSIZE="%s"' % new_size)
        else:
            logger.warn('The correct settings for --heapsize are: "MAX_HEAP_SIZE,HEAP_NEWSIZE".\n')
            logger.warn('Ignoring heapsize settings and continuing.')

    cassandra_env = cassandra_env.replace('JVM_OPTS="$JVM_OPTS -Xss128k"', '# Updated by the AMI for the newest JVM\nJVM_OPTS="$JVM_OPTS -Xss256k"')
    cassandra_env = cassandra_env.replace('JVM_OPTS="$JVM_OPTS -Xss180k"', '# Updated by the AMI for the newest JVM\nJVM_OPTS="$JVM_OPTS -Xss256k"')

    with open(os.path.join(config_data['conf_path'], 'cassandra-env.sh'), 'w') as f:
        f.write(cassandra_env)

    logger.info('cassandra-env.sh configured.')

def construct_dse():
    if conf.get_config("AMI", "Type") == "Enterprise":
        with open('/etc/default/dse', 'r') as f:
            dse_default = f.read()

        if options.cfsreplication:
            logger.info('Using cfsreplication factor: {0}'.format(options.cfsreplication))
            dse_default = dse_default.replace("#CFS_REPLICATION_FACTOR=1", "CFS_REPLICATION_FACTOR={0}".format(options.cfsreplication))

        enable_analytics = True
        enable_search = True

        if instance_data['launchindex'] < options.seed_indexes[1]:
            enable_analytics = False
            enable_search = False

        if options.seed_indexes[1] <= instance_data['launchindex'] and instance_data['launchindex'] < options.seed_indexes[2]:
            enable_analytics = True
            enable_search = False

        if options.seed_indexes[2] <= instance_data['launchindex']:
            enable_analytics = False
            enable_search = True

        if enable_analytics:
            if not options.hadoop and 'SPARK_ENABLED' in dse_default:
                dse_default = dse_default.replace("SPARK_ENABLED=0", "SPARK_ENABLED=1")
            else:
                dse_default = dse_default.replace("HADOOP_ENABLED=0", "HADOOP_ENABLED=1")

        if enable_search:
            dse_default = dse_default.replace("SOLR_ENABLED=0", "SOLR_ENABLED=1")

        with open('/etc/default/dse', 'w') as f:
            f.write(dse_default)

        logger.info('/etc/default/dse configured.')

def construct_agent():
    logger.exe('sudo mkdir -p /var/lib/datastax-agent/conf')
    logger.exe('sudo chown ubuntu:ubuntu /var/lib/datastax-agent/conf')

    with open('/var/lib/datastax-agent/conf/address.yaml', 'w') as f:
        if options.opscenterip:
            f.write('stomp_interface: %s\n' % options.opscenterip)
        else:
            f.write('stomp_interface: %s\n' % config_data['opscenterseed'])

        if options.opscenterssl:
            f.write('use_ssl: 1')

    logger.exe('cat /var/lib/datastax-agent/conf/address.yaml')

    # post 5.1: OpsCenter relies on the cassandra user. This will be attempted first to chown the user from `root`
    logger.exe('sudo chown cassandra:cassandra /var/lib/datastax-agent/conf', expectError=True)
    # pre 5.1: OpsCenter created the opscenter-agent. In post 5.1 clusters, this command will be logged, but will not change ownership.
    logger.exe('sudo chown opscenter-agent:opscenter-agent /var/lib/datastax-agent/conf', expectError=True)

    logger.info('address.yaml configured.')


def create_cassandra_directories(mnt_point, device):
    logger.pipe("echo '{0}\t{1}\txfs\tdefaults,nobootwait\t0\t0'".format(device, mnt_point), 'sudo tee -a /etc/fstab')
    logger.exe('sudo mount -a')

    if conf.get_config("AMI", "RaidOnly"):
        output = logger.exe('id cassandra', expectError=True)
        if output[1] or 'no such user' in output[0].lower():
            while True:
                logger.pipe('yes','sudo adduser --no-create-home --disabled-password cassandra')
                output = logger.exe('id cassandra', expectError=True)
                if not output[1] and not 'no such user' in output[0].lower():
                    break
                time.sleep(1)

        output = logger.exe('id opscenter-agent', expectError=True)
        if output[1] or 'no such user' in output[0].lower():
            logger.pipe('yes','sudo adduser --no-create-home --disabled-password opscenter-agent')
            while True:
                output = logger.exe('id opscenter-agent', expectError=True)
                if not output[1] and not 'no such user' in output[0].lower():
                    break
                time.sleep(1)

    logger.exe('sudo mkdir -p {0}'.format(os.path.join(mnt_point, 'cassandra', 'logs')))
    logger.exe('sudo chown -R cassandra:cassandra {0}'.format(os.path.join(mnt_point, 'cassandra')))

    # Create symlink for Cassandra data
    logger.exe('sudo rm -rf /var/lib/cassandra')
    logger.exe('sudo ln -s {0} /var/lib/cassandra'.format(os.path.join(mnt_point, 'cassandra')))
    logger.exe('sudo chown -R cassandra:cassandra /var/lib/cassandra')

    # Create symlink for Cassandra logs
    logger.exe('sudo rm -rf /var/log/cassandra')
    logger.exe('sudo ln -s {0} /var/log/cassandra'.format(os.path.join(mnt_point, 'cassandra', 'logs')))
    logger.exe('sudo chown -R cassandra:cassandra /var/log/cassandra')

    # Create symlink for OpsCenter logs
    if instance_data['launchindex'] == 0 and options.opscenter != "no":
        logger.exe('sudo mkdir -p {0}'.format(os.path.join(mnt_point, 'opscenter', 'logs')))
        logger.exe('sudo rm -rf /var/log/opscenter')
        logger.exe('sudo ln -s {0} /var/log/opscenter'.format(os.path.join(mnt_point, 'opscenter', 'logs')))
        logger.exe('sudo chown -R root:root /var/log/opscenter')
        logger.exe('sudo chown -R root:root {0}'.format(os.path.join(mnt_point, 'opscenter')))

    # Create symlink for DataStax Agent logs
    logger.exe('sudo mkdir -p {0}'.format(os.path.join(mnt_point, 'datastax-agent', 'logs')))
    logger.exe('sudo rm -rf /var/log/datastax-agent')
    logger.exe('sudo ln -s {0} /var/log/datastax-agent'.format(os.path.join(mnt_point, 'datastax-agent', 'logs')))

    # post 5.1: OpsCenter relies on the cassandra user. This will be attempted first to chown the user from `root`
    logger.exe('sudo chown -R cassandra:cassandra /var/log/datastax-agent', expectError=True)
    # pre 5.1: OpsCenter created the opscenter-agent. In post 5.1 clusters, this command will be logged, but will not change ownership.
    logger.exe('sudo chown -R opscenter-agent:opscenter-agent /var/log/datastax-agent', expectError=True)

    logger.exe('sudo touch /var/log/datastax-agent/agent.log')
    logger.exe('sudo touch /var/log/datastax-agent/startup.log')

    logger.exe('sudo chown -R cassandra:cassandra {0}'.format(os.path.join(mnt_point, 'cassandra')))

    # post 5.1: OpsCenter relies on the cassandra user. This will be attempted first to chown the user from `root`
    logger.exe('sudo chown -R cassandra:cassandra {0}'.format(os.path.join(mnt_point, 'datastax-agent')), expectError=True)
    # pre 5.1: OpsCenter created the opscenter-agent. In post 5.1 clusters, this command will be logged, but will not change ownership.
    logger.exe('sudo chown -R opscenter-agent:opscenter-agent {0}'.format(os.path.join(mnt_point, 'datastax-agent')), expectError=True)


def mount_raid(devices):
    # Make sure the devices are umounted, then run fdisk on each device
    logger.info('Clear "invalid flag 0x0000 of partition table 4" by issuing a write, then running fdisk on each device...')
    formatCommands = "echo 'n\np\n1\n\n\nt\nfd\nw'"
    for device in devices:
        logger.info('Confirming devices are not mounted:')
        # Try unmounting both /dev/xvdb and /dev/xvdb1 in case it is partitioned
        # by default
        logger.exe('sudo umount {0}'.format(device), expectError=True)
        logger.exe('sudo umount {0}1'.format(device), expectError=True)
        logger.pipe("echo 'w'", 'sudo fdisk -c -u {0}'.format(device))
        logger.pipe(formatCommands, 'sudo fdisk -c -u {0}'.format(device))

    # Create a list of partitions to RAID
    logger.exe('sudo fdisk -l')
    partitions = glob.glob('/dev/xvd*[0-9]')
    if '/dev/xvda1' in partitions:
        partitions.remove('/dev/xvda1')
    partitions.sort()
    logger.info('Partitions about to be added to RAID0 set: {0}'.format(partitions))

    # Make sure the partitions are umounted and create a list string
    partion_list = ''
    for partition in partitions:
        logger.info('Confirming partitions are not mounted:')
        logger.exe('sudo umount ' + partition, expectError=True)
    partion_list = ' '.join(partitions).strip()

    logger.info('Creating the RAID0 set:')
    time.sleep(3) # was at 10

    conf.set_config("AMI", "CurrentStatus", "Raid creation")

    # Continuously create the Raid device, in case there are errors
    raid_created = False
    while not raid_created:
        logger.exe('sudo mdadm --create /dev/md0 --chunk=256 --level=0 --raid-devices={0} {1}'.format(len(partitions), partion_list), expectError=True)
        raid_created = True

        logger.pipe('echo DEVICE {0}'.format(partion_list), 'sudo tee /etc/mdadm/mdadm.conf')
        time.sleep(5)

        # New parsing and elimination of the name= field due to 12.04's new RAID'ing methods
        response = logger.exe('sudo mdadm --examine --scan')[0]
        response = ' '.join(response.split(' ')[0:-1])
        with open('/etc/mdadm/mdadm.conf', 'a') as f:
            f.write(response)
        logger.exe('sudo update-initramfs -u')

        time.sleep(10)
        conf.set_config('AMI', 'raid_readahead', 128)
        logger.exe('sudo blockdev --setra %s /dev/md0' % (conf.get_config('AMI', 'raid_readahead')))

        logger.info('Formatting the RAID0 set:')
        time.sleep(10)
        raidError = logger.exe('sudo mkfs.xfs -f /dev/md0', expectError=True)[1]

        if raidError:
            logger.exe('sudo mdadm --stop /dev/md_d0', expectError=True)
            logger.exe('sudo mdadm --zero-superblock /dev/sdb1', expectError=True)
            raid_created = False

    # Configure fstab and mount the new RAID0 device
    mnt_point = '/raid0'
    logger.exe('sudo mkdir {0}'.format(mnt_point))
    create_cassandra_directories(mnt_point=mnt_point, device='/dev/md0')

    logger.info('Showing RAID0 details:')
    logger.exe('cat /proc/mdstat')
    logger.exe('sudo mdadm --detail /dev/md0')

    # http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/InstanceStorage.html
    logger.pipe('echo "30720"', 'sudo tee /proc/sys/dev/raid/speed_limit_min')

    return mnt_point

def format_xfs(devices):
    # Make sure the device is umounted, then run fdisk on the device
    logger.info('Clear "invalid flag 0x0000 of partition table 4" by issuing a write, then running fdisk on the device...')
    formatCommands = "echo 'd\nn\np\n1\n\n\nt\n83\nw'"
    logger.exe('sudo umount {0}'.format(devices[0]), expectError=True)
    logger.pipe("echo 'w'", 'sudo fdisk -c -u {0}'.format(devices[0]))
    logger.pipe(formatCommands, 'sudo fdisk -c -u {0}'.format(devices[0]))

    # Create a list of partitions to RAID
    logger.exe('sudo fdisk -l')
    partitions = glob.glob('/dev/xvd*[0-9]')
    if '/dev/xvda1' in partitions:
        partitions.remove('/dev/xvda1')
    partitions.sort()

    logger.info('Formatting the new partition:')
    logger.exe('sudo mkfs.xfs -f {0}'.format(partitions[0]))

    # Configure fstab and mount the new formatted device
    mnt_point = '/mnt'
    create_cassandra_directories(mnt_point=mnt_point, device=partitions[0])

    return mnt_point

def prepare_for_raid():
    # Only create raid0 once. Mount all times in init.d script.
    # A failsafe against resurrecting this file.
    if conf.get_config("AMI", "RAIDAttempted"):
        return

    conf.set_config("AMI", "CurrentStatus", "Raiding started")

    # Remove EC2 default /mnt from fstab
    fstab = ''
    file_to_open = '/etc/fstab'
    logger.exe('sudo chmod 777 {0}'.format(file_to_open))
    with open(file_to_open, 'r') as f:
        for line in f:
            if not "/mnt" in line:
                fstab += line
    with open(file_to_open, 'w') as f:
        f.write(fstab)
    logger.exe('sudo chmod 644 {0}'.format(file_to_open))

    # Create a list of devices
    # skip /dev/xvda, which is the root-device
    devices = glob.glob('/dev/xvd[b-z]')
    devices.sort()
    logger.info('Unformatted devices: {0}'.format(devices))

    # Check if there are enough drives to start a RAID set
    if len(devices) > 1:
        time.sleep(3) # was at 20
        mnt_point = mount_raid(devices)

    # Not enough drives to RAID together.
    else:
        mnt_point = format_xfs(devices)

    if not options.raidonly:
        # Change cassandra.yaml to point to the new data directories
        with open(os.path.join(config_data['conf_path'], 'cassandra.yaml'), 'r') as f:
            yaml = f.read()

        yaml = yaml.replace('/var/lib/cassandra/data', os.path.join(mnt_point, 'cassandra', 'data'))
        yaml = yaml.replace('/var/lib/cassandra/saved_caches', os.path.join(mnt_point, 'cassandra', 'saved_caches'))
        yaml = yaml.replace('/var/lib/cassandra/commitlog', os.path.join(mnt_point, 'cassandra', 'commitlog'))
        yaml = yaml.replace('/var/log/cassandra', os.path.join(mnt_point, 'cassandra', 'logs'))

        # Increase phi_convict_threshold to account for EC2 noise
        yaml = yaml.replace('# phi_convict_threshold: 8', 'phi_convict_threshold: 12')

        with open(os.path.join(config_data['conf_path'], 'cassandra.yaml'), 'w') as f:
            f.write(yaml)

    # Never create raid array again
    conf.set_config("AMI", "RAIDAttempted", True)

    logger.info("Mounted Raid.\n")
    conf.set_config("AMI", "MountDirectory", mnt_point)
    conf.set_config("AMI", "CurrentStatus", "Raiding complete")

def construct_core_site():
    if conf.get_config("AMI", "Type") == "Enterprise":
        with open('/etc/dse/hadoop/core-site.xml', 'r') as f:
            core_site = f.read()

        hadoop_tmp_dir = os.path.join(conf.get_config("AMI", "MountDirectory"), 'hadoop')
        tmp_dir = '\n <!-- AMI configuration -->\n <property>\n   <name>hadoop.tmp.dir</name>\n   <value>%s/${user.name}</value>\n </property>\n</configuration>' % hadoop_tmp_dir
        core_site = core_site.replace('</configuration>', tmp_dir)

        logger.exe('sudo mkdir -p %s' % hadoop_tmp_dir)
        logger.exe('sudo chown -R cassandra:cassandra %s' % hadoop_tmp_dir)

        hadoop_ubuntu_dir = os.path.join(hadoop_tmp_dir, 'ubuntu')
        logger.exe('sudo mkdir -p %s' % hadoop_ubuntu_dir)
        logger.exe('sudo chown -R ubuntu:ubuntu %s' % hadoop_ubuntu_dir)

        with open('/etc/dse/hadoop/core-site.xml', 'w') as f:
            f.write(core_site)

def construct_mapred_site():
    if conf.get_config("AMI", "Type") == "Enterprise":
        with open('/etc/dse/hadoop/mapred-site.xml', 'r') as f:
            mapred_site = f.read()

        mapred_local_dir = os.path.join(conf.get_config("AMI", "MountDirectory"), 'hadoop', 'mapredlocal')
        mapred_site = mapred_site.replace('/tmp/mapredlocal', mapred_local_dir)

        logger.exe('sudo mkdir -p %s' % mapred_local_dir)
        logger.exe('sudo chown -R cassandra:cassandra %s' % mapred_local_dir)

        with open('/etc/dse/hadoop/mapred-site.xml', 'w') as f:
            f.write(mapred_site)

def sync_clocks():
    # Confirm that NTP is installed
    logger.exe('sudo apt-get -y install ntp')

    with open('/etc/ntp.conf', 'r') as f:
            ntp_conf = f.read()

    # Create a list of ntp server pools
    server_list = ""
    for i in range(0, 4):
        server_list += "server {0}.pool.ntp.org\n".format(i)

    # Overwrite the single ubuntu ntp server with the server pools
    ntp_conf = ntp_conf.replace('server ntp.ubuntu.com', server_list)

    with open('/etc/ntp.conf', 'w') as f:
        f.write(ntp_conf)

    # Restart the service
    logger.exe('sudo service ntp stop')
    logger.exe('sudo ntpdate pool.ntp.org')
    logger.exe('sudo service ntp start')


def additional_pre_configurations():
    # Get required keys for Ubuntu
    logger.exe('sudo apt-key add /home/ubuntu/datastax_ami/repo_keys/Launchpad_VLC.C2518248EEA14886.key')
    logger.exe('sudo apt-key add /home/ubuntu/datastax_ami/repo_keys/Ubuntu_Archive.40976EAF437D05B5.key')

def additional_post_configurations():
    if options.base64postscript:
        command = base64.b64decode(options.base64postscript)
        process = subprocess.Popen(shlex.split(command), stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
        read = process.communicate()
        logger.info('base64postscript response: %s\n%s' % read)
    logger.exe('sudo apt-get --reinstall install ubuntu-keyring')

def run():
    # Remove script files
    logger.exe('sudo rm ds2_configure.py*')
    logger.info('Deleting ds2_configure.py now. This AMI will never change any configs after this first run.')

    additional_pre_configurations()
    clear_motd()

    try:
        get_ec2_data()
    except urllib2.HTTPError:
        exit_path("Clusters backed by Spot Instances are not supported.")

    parse_ec2_userdata()
    vpc_workaround()

    if options.raidonly:
        # This file is marked as a config file by the various cassandra
        # packages, and breaks unattended installs by throwing apt into
        # interactive conflict resolution mode unless dangerous flags
        # are supplied that force config overrides.
        #
        # In order to allow OpsCenter to install packages on machines
        # provisioned with this AMI, the custom limits configs should
        # be removed when the --raidonly flag is supplied.
        logger.exe('sudo mv /etc/security/limits.d/cassandra.conf /etc/security/limits.d/cassandra.conf.ami_default')

    if not options.raidonly and not options.opscenteronly:
        use_ec2_userdata()

    if not options.raidonly:
        confirm_authentication()
        setup_repos()

    if not options.raidonly and not options.opscenteronly:
        clean_installation()

    if not options.raidonly:
        opscenter_installation()

    if not options.raidonly and not options.opscenteronly:
        get_seed_list()

    checkpoint_info()

    if not options.raidonly and not options.opscenteronly:
        calculate_tokens()
        construct_yaml()

    if not options.raidonly:
        construct_opscenter_conf()

    if not options.raidonly and not options.opscenteronly:
        construct_opscenter_cluster_conf()
        construct_env()
        construct_dse()
        construct_agent()

    if not options.opscenteronly:
        prepare_for_raid()

    if not options.raidonly and not options.opscenteronly:
        construct_core_site()
        construct_mapred_site()

        sync_clocks()

        additional_post_configurations()

    logger.info("ds2_configure.py completed!\n")
    conf.set_config("AMI", "CurrentStatus", "Complete!")

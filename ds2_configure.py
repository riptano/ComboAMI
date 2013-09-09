#!/usr/bin/env python
### Script provided by DataStax.

import exceptions
import glob
import json
import os
import random
import re
import shlex
import subprocess
import sys
import time
import traceback
import urllib2
import urllib

import gzip
import StringIO
from email.parser import Parser

from optparse import OptionParser

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

    raise exceptions.AttributeError


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
        req = curl_instance_data('http://instance-data/latest/user-data/')
        instance_data['userdata'] = get_user_data(req)

        logger.info("Started with user data set to:")
        logger.info(instance_data['userdata'])
    except Exception, e:
        instance_data['userdata'] = ''
        exit_path("No User Data was set.")

    # Find internal instance type
    req = curl_instance_data('http://instance-data/latest/meta-data/instance-type')
    instancetype = urllib2.urlopen(req).read()
    logger.info("Using instance type: %s" % instancetype)

    if instancetype == 'm1.small' or instancetype == 'm1.medium':
        exit_path("m1.small and m1.medium instances are not supported. At minimum, use an m1.large instance.")

    # Find internal IP address for seed list
    req = curl_instance_data('http://instance-data/latest/meta-data/local-ipv4')
    instance_data['internalip'] = urllib2.urlopen(req).read()

    # Find public hostname for JMX
    req = curl_instance_data('http://instance-data/latest/meta-data/public-hostname')
    instance_data['publichostname'] = urllib2.urlopen(req).read()

    # Find launch index for token splitting
    req = curl_instance_data('http://instance-data/latest/meta-data/ami-launch-index')
    instance_data['launchindex'] = int(urllib2.urlopen(req).read())

    # Find reservation-id for cluster-id and jmxpass
    req = curl_instance_data('http://instance-data/latest/meta-data/reservation-id')
    instance_data['reservationid'] = urllib2.urlopen(req).read()
    instance_data['clustername'] = instance_data['reservationid']
    # instance_data['jmx_pass'] = instance_data['reservationid']

def parse_ec2_userdata():
    # Setup parser
    parser = OptionParser()

    # Development options
    # Option that specifies the cluster's name
    parser.add_option("--dev", action="store", type="string", dest="dev")

    # Letters available: ...
    # Option that requires either: Enterprise or Community
    parser.add_option("--version", action="store", type="string", dest="version")
    # Option that specifies how the ring will be divided
    parser.add_option("--totalnodes", action="store", type="int", dest="totalnodes")
    # Option that specifies the cluster's name
    parser.add_option("--clustername", action="store", type="string", dest="clustername")
    # Option that allows for a release version of Enterprise or Community
    parser.add_option("--release", action="store", type="string", dest="release")

    # Option that specifies how the number of Analytics nodes
    parser.add_option("--analyticsnodes", action="store", type="int", dest="analyticsnodes")
    # Option that specifies how the number of Analytics nodes
    parser.add_option("--searchnodes", action="store", type="int", dest="searchnodes")

    # Option that specifies the CassandraFS replication factor
    parser.add_option("--cfsreplicationfactor", action="store", type="int", dest="cfsreplication")

    # Option that specifies the username
    parser.add_option("--username", action="store", type="string", dest="username")
    # Option that specifies the password
    parser.add_option("--password", action="store", type="string", dest="password")

    # Option that specifies the installation of OpsCenter on the first node
    parser.add_option("--opscenter", action="store", type="string", dest="opscenter")
    # Option that specifies an alternative reflector.php
    parser.add_option("--reflector", action="store", type="string", dest="reflector")

    # Unsupported dev options
    # Option that allows for an emailed report of the startup diagnostics
    parser.add_option("--raidonly", action="store_true", dest="raidonly")
    # Option that allows for an emailed report of the startup diagnostics
    parser.add_option("--email", action="store", type="string", dest="email")
    # Option that allows heapsize to be changed
    parser.add_option("--heapsize", action="store", type="string", dest="heapsize")
    # Option that allows an interface port for OpsCenter to be set
    parser.add_option("--opscenterinterface", action="store", type="string", dest="opscenterinterface")
    # Option that allows a custom reservation id to be set
    parser.add_option("--customreservation", action="store", type="string", dest="customreservation")

    # Community options
    # https://github.com/riptano/ComboAMI/pull/9
    # Option that allows for keeping the javaversion up to date by installing at runtime. Includes option for 1.6 or 1.7.
    parser.add_option("--javaversion", action="store", type="string", dest="javaversion")

    # Grab provided reflector through provided userdata
    global options
    try:
        (options, args) = parser.parse_args(shlex.split(instance_data['userdata']))
    except:
        exit_path("One of the options was not set correctly.")

    if not options.analyticsnodes:
        options.analyticsnodes = 0
    if not options.searchnodes:
        options.searchnodes = 0

    if not options.raidonly:
        options.realtimenodes = (options.totalnodes - options.analyticsnodes - options.searchnodes)
        options.seed_indexes = [0, options.realtimenodes, options.realtimenodes + options.analyticsnodes]

def use_ec2_userdata():
    if not options:
        exit_path("EC2 User Data must be set for the DataStax AMI to run.")

    if not options.totalnodes:
        exit_path("Missing required --totalnodes (-n) switch.")

    if (options.analyticsnodes + options.searchnodes) > options.totalnodes:
        exit_path("Total nodes assigned (--analyticsnodes + --searchnodes) > total available nodes (--totalnodes)")

    if options.javaversion:
        if options.javaversion.lower() == '1.7':
            conf.set_config("AMI", "JavaType", "1.7")
        else:
            conf.set_config("AMI", "JavaType", "1.6")

    if options.version:
        if options.version.lower() == "community":
            conf.set_config("AMI", "Type", "Community")
        elif options.version.lower() == "enterprise":
            conf.set_config("AMI", "Type", "Enterprise")
        else:
            exit_path("Invalid --version (-v) argument.")
    else:
        exit_path("Missing required --version (-v) switch.")

    if conf.get_config("AMI", "Type") == "Community" and (options.cfsreplication or options.analyticsnodes or options.searchnodes):
        exit_path('CFS Replication, Vanilla Nodes, and adding an Analytic Node settings can only be set in DataStax Enterprise installs.')

    if options.email:
        logger.info('Setting up diagnostic email using: {0}'.format(options.email))
        conf.set_config("AMI", "Email", options.email)

    if options.clustername:
        logger.info('Using cluster name: {0}'.format(options.clustername))
        instance_data['clustername'] = options.clustername

    if options.customreservation:
        instance_data['reservationid'] = options.customreservation

    logger.info('Using cluster size: {0}'.format(options.totalnodes))
    conf.set_config("Cassandra", "TotalNodes", options.totalnodes)
    logger.info('Using seed indexes: {0}'.format(options.seed_indexes))

    if options.reflector:
        logger.info('Using reflector: {0}'.format(options.reflector))

def confirm_authentication():
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
                config_data['conf_path'] = os.path.expanduser("/etc/dse/cassandra/")
            except Exception as inst:
                # Print error message if failed
                if "401" in str(inst):
                    exit_path('Authentication for DataStax Enterprise failed. Please confirm your username and password.\n')
        elif (options.username or options.password):
            exit_path("Both --username (-u) and --password (-p) required for DataStax Enterprise.")

def setup_repos():
    # Clear repo when filled, primarily for debugging purposes
    logger.exe('sudo rm /etc/apt/sources.list.d/datastax.sources.list', log=False, expectError=True)

    # Add repos
    if conf.get_config("AMI", "Type") == "Enterprise":
        logger.pipe('echo "deb http://{0}:{1}@debian.datastax.com/enterprise stable main"'.format(options.username, options.password), 'sudo tee -a /etc/apt/sources.list.d/datastax.sources.list')
    else:
        logger.pipe('echo "deb http://debian.datastax.com/community stable main"', 'sudo tee -a /etc/apt/sources.list.d/datastax.sources.list')

    # Add repokeys
    logger.pipe('curl -s http://installer.datastax.com/downloads/ubuntuarchive.repo_key', 'sudo apt-key add -')
    logger.pipe('curl -s http://opscenter.datastax.com/debian/repo_key', 'sudo apt-key add -')
    logger.pipe('curl -s http://debian.datastax.com/debian/repo_key', 'sudo apt-key add -')

    if options.dev:
        logger.pipe('echo "deb {0} maverick main"'.format(options.dev.split(',')[0]), 'sudo tee -a /etc/apt/sources.list.d/datastax.sources.list')
        logger.pipe('curl -s {0}'.format(options.dev.split(',')[1]), 'sudo apt-key add -')

    # Perform the install
    logger.exe('sudo apt-get update')
    while True:
        output = logger.exe('sudo apt-get update')
        if not output[1] and not 'err' in output[0].lower() and not 'failed' in output[0].lower():
            break

    time.sleep(5)

def clean_installation():
    logger.info('Performing deployment install...')
    if conf.get_config("AMI", "Type") == "Community":
        if options.release and options.release.startswith('1.0'):
            cassandra_release = options.release
            if cassandra_release == '1.0.11-1':
                cassandra_release = '1.0.11'
            logger.exe('sudo apt-get install -y python-cql cassandra={0} dsc={1}'.format(cassandra_release, options.release))
            conf.set_config('AMI', 'package', 'dsc')
            conf.set_config('Cassandra', 'partitioner', 'random_partitioner')
        elif options.release and options.release.startswith('1.1'):
            dsc_release = cassandra_release = options.release
            if dsc_release in ['1.1.6', '1.1.7', '1.1.9']:
                dsc_release = dsc_release + '-1'
            logger.exe('sudo apt-get install -y python-cql cassandra={0} dsc1.1={1}'.format(cassandra_release, dsc_release))
            conf.set_config('AMI', 'package', 'dsc1.1')
            conf.set_config('Cassandra', 'partitioner', 'random_partitioner')
        elif options.release and options.release.startswith('1.2'):
            dsc_release = cassandra_release = options.release
            dsc_release = dsc_release + '-1'
            logger.exe('sudo apt-get install -y python-cql cassandra={0} dsc12={1}'.format(cassandra_release, dsc_release))
            conf.set_config('AMI', 'package', 'dsc12')
            conf.set_config('Cassandra', 'partitioner', 'murmur')
            conf.set_config('Cassandra', 'vnodes', 'True')
        elif options.release and options.release.startswith('2.0'):
            dsc_release = cassandra_release = options.release
            dsc_release = dsc_release + '-1'
            logger.exe('sudo apt-get install -y python-cql cassandra={0} dsc20={1}'.format(cassandra_release, dsc_release))
            conf.set_config('AMI', 'package', 'dsc20')
            conf.set_config('Cassandra', 'partitioner', 'murmur')
            conf.set_config('Cassandra', 'vnodes', 'True')
        else:
            logger.exe('sudo apt-get install -y python-cql dsc20')
            conf.set_config('AMI', 'package', 'dsc20')
            conf.set_config('Cassandra', 'partitioner', 'murmur')
            conf.set_config('Cassandra', 'vnodes', 'True')
            # logger.exe('sudo apt-get install -y dsc-demos')
        logger.exe('sudo service cassandra stop')
    elif conf.get_config("AMI", "Type") == "Enterprise":
        if options.release:
            install_list = 'sudo apt-get install -y dse-full={0} dse={0} dse-demos={0} dse-hive={0} dse-libcassandra={0} dse-libhadoop={0} dse-libhive={0} dse-libpig={0} dse-pig={0}'
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

def opscenter_installation():
    if instance_data['launchindex'] == 0 and options.opscenter != "no":
        logger.info('Installing OpsCenter...')
        if conf.get_config("AMI", "Type") == "Community":
            logger.exe('sudo apt-get -y install opscenter-free libssl0.9.8')
        elif conf.get_config("AMI", "Type") == "Enterprise":
            logger.exe('sudo apt-get -y install opscenter libssl0.9.8')
        logger.exe('sudo service opscenterd stop')
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
    while continue_loop:
        logger.info('Reflector loop...')
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

            status =  "[INFO] {0} Received {1} of {2} responses from:        {0}".format(
                            time.strftime("%m/%d/%y-%H:%M:%S", time.localtime()),
                            response['number_of_returned_ips'],
                            expected_responses,
                            response['seeds']
                      )
            conf.set_config("AMI", "CurrentStatus", status)

            if response['number_of_returned_ips'] == expected_responses:
                conf.set_config("OpsCenter", "DNS", response['opscenter_dns'])

                config_data['seed_list'] = set(response['seeds'])
                config_data['opscenterseed'] = response['seeds'][0]

                continue_loop = False
            else:
                time.sleep(2 + random.randint(0, options.totalnodes / 4 + 1))
        except:
            traceback.print_exc(file=sys.stdout)
            time.sleep(2 + random.randint(0, 5))

def checkpoint_info():
    if options.raidonly:
        conf.set_config("AMI", "RaidOnly", "True")
    else:
        logger.info("Seed list: {0}".format(config_data['seed_list']))
        logger.info("OpsCenter: {0}".format(config_data['opscenterseed']))
        logger.info("Options: {0}".format(options))
        conf.set_config("AMI", "LeadingSeed", config_data['opscenterseed'])
    conf.set_config("AMI", "CurrentStatus", "Installation complete")

def calculate_tokens():
    # MAXRANGE = (2**127)

    # tokens = {}
    # for dc in range(len(datacenters)):
    #     tokens[dc] = {}
    #     for i in range(datacenters[dc]):
    #         tokens[dc][i] = (i * MAXRANGE / datacenters[dc]) + dc * 1000

    # config_data['tokens'] = tokens

    if conf.get_config('Cassandra', 'partitioner') == 'random_partitioner':
        import tokentoolv2

        datacenters = [options.realtimenodes, options.analyticsnodes, options.searchnodes]
        config_data['tokens'] = tokentoolv2.run(datacenters)
    # else:
    #     # Used to calculate tokens for murmur partitioners. But vnodes are used instead.
    #     number_of_tokens = options.realtimenodes
    #     tokens = [(((2**64 / number_of_tokens) * i) - 2**63) for i in range(number_of_tokens)]
    #     config_data['tokens'] = {0: tokens}

def construct_yaml():
    with open(os.path.join(config_data['conf_path'], 'cassandra.yaml'), 'r') as f:
        yaml = f.read()

    # Create the seed list
    seeds_yaml = ','.join(config_data['seed_list'])

    # Set seeds for DSE/C
    p = re.compile('seeds:.*')
    yaml = p.sub('seeds: "{0}"'.format(seeds_yaml), yaml)

    # Set listen_address
    p = re.compile('listen_address:.*')
    yaml = p.sub('listen_address: {0}'.format(instance_data['internalip']), yaml)

    # Set rpc_address
    p = re.compile('rpc_address:.*')
    yaml = p.sub('rpc_address: 0.0.0.0', yaml)

    # Uses the EC2Snitch for Community Editions
    if conf.get_config("AMI", "Type") == "Community":
        yaml = yaml.replace('endpoint_snitch: org.apache.cassandra.locator.SimpleSnitch', 'endpoint_snitch: org.apache.cassandra.locator.Ec2Snitch')
        yaml = yaml.replace('endpoint_snitch: SimpleSnitch', 'endpoint_snitch: Ec2Snitch')

    # Set cluster_name to reservationid
    instance_data['clustername'] = instance_data['clustername'].strip("'").strip('"')
    yaml = yaml.replace("cluster_name: 'Test Cluster'", "cluster_name: '{0}'".format(instance_data['clustername']))

    # Set auto_bootstrap: false
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
        if conf.get_config('Cassandra', 'vnodes') == 'True':
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

        # Deprecated
        opsc_conf = opsc_conf.replace('seed_hosts = localhost', 'seed_hosts = {0}'.format(config_data['opscenterseed']))

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

    # Set JMX hostname and password file
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

    cassandra_env = cassandra_env.replace('JVM_OPTS="$JVM_OPTS -Xss128k"', '# Updated by the AMI for the newest JVM\nJVM_OPTS="$JVM_OPTS -Xss180k"')

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

        enable_hadoop = True
        enable_search = True

        if instance_data['launchindex'] < options.seed_indexes[1]:
            enable_hadoop = False
            enable_search = False

        if options.seed_indexes[1] <= instance_data['launchindex'] and instance_data['launchindex'] < options.seed_indexes[2]:
            enable_hadoop = True
            enable_search = False

        if options.seed_indexes[2] <= instance_data['launchindex']:
            enable_hadoop = False
            enable_search = True

        if enable_hadoop:
            dse_default = dse_default.replace("HADOOP_ENABLED=0", "HADOOP_ENABLED=1")

        if enable_search:
            dse_default = dse_default.replace("SOLR_ENABLED=0", "SOLR_ENABLED=1")

        with open('/etc/default/dse', 'w') as f:
            f.write(dse_default)

def mount_raid(devices):
    # Make sure the devices are umounted, then run fdisk on each device
    logger.info('Clear "invalid flag 0x0000 of partition table 4" by issuing a write, then running fdisk on each device...')
    formatCommands = "echo 'n\np\n1\n\n\nt\nfd\nw'"
    for device in devices:
        logger.info('Confirming devices are not mounted:')
        logger.exe('sudo umount {0}'.format(device), False)
        logger.pipe("echo 'w'", 'sudo fdisk -c -u {0}'.format(device))
        logger.pipe(formatCommands, 'sudo fdisk -c -u {0}'.format(device))

    # Create a list of partitions to RAID
    logger.exe('sudo fdisk -l')
    partitions = glob.glob('/dev/xvd*[0-9]')
    partitions.remove('/dev/xvda1')
    partitions.sort()
    logger.info('Partitions about to be added to RAID0 set: {0}'.format(partitions))

    # Make sure the partitions are umounted and create a list string
    partion_list = ''
    for partition in partitions:
        logger.info('Confirming partitions are not mounted:')
        logger.exe('sudo umount ' + partition, False)
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
        conf.set_config('AMI', 'raid_readahead', 512)
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
    logger.pipe("echo '/dev/md0\t{0}\txfs\tdefaults,nobootwait,noatime\t0\t0'".format(mnt_point), 'sudo tee -a /etc/fstab')
    logger.exe('sudo mkdir {0}'.format(mnt_point))
    logger.exe('sudo mount -a')
    logger.exe('sudo mkdir -p {0}'.format(os.path.join(mnt_point, 'cassandra')))
    if conf.get_config("AMI", "RaidOnly"):
        logger.pipe('yes', 'sudo adduser --no-create-home --disabled-password cassandra')
        while True:
            output = logger.exe('id cassandra')
            if not output[1] and not 'no such user' in output[0].lower():
                break
            time.sleep(1)
    logger.exe('sudo chown -R cassandra:cassandra {0}'.format(os.path.join(mnt_point, 'cassandra')))

    # Create symlink for Cassandra
    logger.exe('sudo rm -rf /var/lib/cassandra')
    logger.exe('sudo ln -s {0} /var/lib/cassandra'.format(os.path.join(mnt_point, 'cassandra')))
    logger.exe('sudo chown -R cassandra:cassandra /var/lib/cassandra')

    logger.info('Showing RAID0 details:')
    logger.exe('cat /proc/mdstat')
    logger.exe('echo "15000" > /proc/sys/dev/raid/speed_limit_min')
    logger.exe('sudo mdadm --detail /dev/md0')
    return mnt_point

def format_xfs(devices):
    # Make sure the device is umounted, then run fdisk on the device
    logger.info('Clear "invalid flag 0x0000 of partition table 4" by issuing a write, then running fdisk on the device...')
    formatCommands = "echo 'd\nn\np\n1\n\n\nt\n83\nw'"
    logger.exe('sudo umount {0}'.format(devices[0]))
    logger.pipe("echo 'w'", 'sudo fdisk -c -u {0}'.format(devices[0]))
    logger.pipe(formatCommands, 'sudo fdisk -c -u {0}'.format(devices[0]))

    # Create a list of partitions to RAID
    logger.exe('sudo fdisk -l')
    partitions = glob.glob('/dev/xvd*[0-9]')
    partitions.remove('/dev/xvda1')
    partitions.sort()

    logger.info('Formatting the new partition:')
    logger.exe('sudo mkfs.xfs -f {0}'.format(partitions[0]))

    # Configure fstab and mount the new formatted device
    mnt_point = '/mnt'
    logger.pipe("echo '{0}\t{1}\txfs\tdefaults,nobootwait,noatime\t0\t0'".format(partitions[0], mnt_point), 'sudo tee -a /etc/fstab')
    logger.exe('sudo mkdir {0}'.format(mnt_point), False)
    logger.exe('sudo mount -a')
    logger.exe('sudo mkdir -p {0}'.format(os.path.join(mnt_point, 'cassandra')))
    logger.exe('sudo chown -R cassandra:cassandra {0}'.format(os.path.join(mnt_point, 'cassandra')))
    return mnt_point

def prepare_for_raid():
    # Only create raid0 once. Mount all times in init.d script. A failsafe against deleting this file.
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
    devices = glob.glob('/dev/xvd*')
    devices.remove('/dev/xvda1')
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
        server_list += "server {0}.north-america.pool.ntp.org\n".format(i)

    # Overwrite the single ubuntu ntp server with the server pools
    ntp_conf = ntp_conf.replace('server ntp.ubuntu.com', server_list)

    with open('/etc/ntp.conf', 'w') as f:
        f.write(ntp_conf)

    # Restart the service
    logger.exe('sudo service ntp restart')

def additional_pre_configurations():
    logger.exe('gpg --keyserver pgp.mit.edu --recv-keys 40976EAF437D05B5', expectError=True)
    logger.pipe('gpg --export --armor 40976EAF437D05B5', 'sudo apt-key add -')
    pass

def additional_post_configurations():
    logger.exe('sudo apt-get install s3cmd')

    # Setup HADOOP_HOME for ubuntu
    file_to_open = '/home/ubuntu/.profile'
    logger.exe('sudo chmod 777 ' + file_to_open)
    with open(file_to_open, 'a') as f:
        f.write("""
    export HADOOP_HOME=/usr/share/dse/hadoop
    """)
    logger.exe('sudo chmod 644 ' + file_to_open)

    # Setup HADOOP_HOME for root
    os.chdir('/root')
    file_to_open = '.profile'
    logger.exe('sudo chmod 777 ' + file_to_open)
    with open(file_to_open, 'w') as f:
        f.write("""
    export HADOOP_HOME=/usr/share/dse/hadoop
    """)
    logger.exe('sudo chmod 644 ' + file_to_open)
    os.chdir('/home/ubuntu')
    pass

def install_java():
    logger.info('Performing deployment install...')
    if conf.get_config("AMI", "JavaType") == "1.7":
        url = "http://www.java.com/en/download/manual.jsp"
        majorversion = "7"
    else:
        url = "http://java.com/en/download/manual_v6.jsp"
        majorversion = "6"

    f = urllib2.urlopen(url)
    t = f.read()

    #regex to find java minor version
    vr = re.compile("(?<=Update )\d+(?=.*)")
    m = vr.search(t)
    minorversion = m.group()

    arch = "64"
    if arch == "64":
        # regex to find download link
        dlr= re.compile('(?<=Linux x64\" href=\")\S+(?=\".*)')
    else:
        dlr= re.compile('(?<=Linux\" href=\")\S+(?=\".*)')

    m = dlr.search(t)
    downloadlink = m.group()

    path = "/opt/java/" + arch + "/"
    cwd = os.curdir
    logger.exe("sudo mkdir -p " + path);
    os.chdir(path)

    if conf.get_config("AMI", "JavaType") == "1.7":
        outputfilename = "jre1.7.tar.gz"
    else:
        outputfilename = "jre1.6.bin"

    urllib.urlretrieve(downloadlink, path + outputfilename)

    if conf.get_config("AMI", "JavaType") == "1.7":
        logger.exe("sudo tar -zxvf " + path + outputfilename)
    else:
        logger.exe("sudo chmod +x " + path + outputfilename)
        logger.exe("sudo " + path + outputfilename)

    logger.exe('sudo update-alternatives --install "/usr/bin/java" "java" "' + path + 'jre1.' + majorversion + '.0_' + minorversion + '/bin/java" 1')
    logger.exe('sudo update-alternatives --set "java" "' + path + 'jre1.' + majorversion + '.0_' + minorversion + '/bin/java"')

    os.chdir(cwd)


def run():
    # Remove script files
    logger.exe('sudo rm ds2_configure.py')
    logger.info('Deleting ds2_configure.py now. This AMI will never change any configs after this first run.')

    additional_pre_configurations()
    clear_motd()

    try:
        get_ec2_data()
    except urllib2.HTTPError:
        exit_path("Clusters within a VPC or backed by Spot Instances are not supported.")

    parse_ec2_userdata()

    if not options.raidonly:
        use_ec2_userdata()

        confirm_authentication()
        if options.javaversion:
            install_java()
        setup_repos()
        clean_installation()
        opscenter_installation()

        get_seed_list()

    checkpoint_info()

    if not options.raidonly:
        calculate_tokens()
        construct_yaml()
        construct_opscenter_conf()
        construct_opscenter_cluster_conf()
        construct_env()
        construct_dse()

    prepare_for_raid()

    if not options.raidonly:
        construct_core_site()
        construct_mapred_site()

        sync_clocks()

        additional_post_configurations()

    logger.info("ds2_configure.py completed!\n")
    conf.set_config("AMI", "CurrentStatus", "Complete!")

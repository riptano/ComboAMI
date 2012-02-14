#!/usr/bin/env python
### Script provided by DataStax.

import exceptions
import glob
import os
import random
import re
import shlex
import subprocess
import sys
import time
import traceback
import urllib2

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

tokens = {}

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

def get_ec2_data():
    conf.set_config("AMI", "CurrentStatus", "Installation started")

    # Find internal IP address for seed list
    req = urllib2.Request('http://instance-data/latest/meta-data/local-ipv4')
    instance_data['internalip'] = urllib2.urlopen(req).read()
    
    # Find public hostname for JMX
    req = urllib2.Request('http://instance-data/latest/meta-data/public-hostname')
    instance_data['publichostname'] = urllib2.urlopen(req).read()
    
    # Find launch index for token splitting
    req = urllib2.Request('http://instance-data/latest/meta-data/ami-launch-index')
    instance_data['launchindex'] = int(urllib2.urlopen(req).read())
    
    # Find reservation-id for cluster-id and jmxpass
    req = urllib2.Request('http://instance-data/latest/meta-data/reservation-id')
    instance_data['reservationid'] = urllib2.urlopen(req).read()
    instance_data['clustername'] = instance_data['reservationid']
    # instance_data['jmx_pass'] = instance_data['reservationid']

    # Try to get EC2 User Data
    try:
        req = urllib2.Request('http://instance-data/latest/user-data/')
        instance_data['userdata'] = urllib2.urlopen(req).read()

        logger.info("Started with user data set to:")
        logger.info(instance_data['userdata'])
    except Exception, e:
        instance_data['userdata'] = ''
        exit_path("No User Data was set.")

def parse_ec2_userdata():
    # Setup parser
    parser = OptionParser()

    # Development options
    # Option that specifies the cluster's name
    parser.add_option("-d", "--dev", action="store", type="string", dest="dev")
    
    # Letters available: ...
    # Option that requires a version
    parser.add_option("-v", "--version", action="store", type="string", dest="version")
    # Option that specifies how the ring will be divided
    parser.add_option("-n", "--totalnodes", action="store", type="string", dest="clustersize")
    # Option that specifies the cluster's name
    parser.add_option("-c", "--clustername", action="store", type="string", dest="clustername")
    # Option that specifies how the number of Cassandra nodes
    parser.add_option("-r", "--realtimenodes", action="store", type="string", dest="vanillanodes")
    # Option that specifies the CassandraFS replication factor
    parser.add_option("-f", "--cfsreplicationfactor", action="store", type="string", dest="cfsreplication")
    # Option that specifies the username
    parser.add_option("-u", "--username", action="store", type="string", dest="username")
    # Option that specifies the password
    parser.add_option("-p", "--password", action="store", type="string", dest="password")
    # Option that allows for an emailed report of the startup diagnostics
    parser.add_option("-e", "--email", action="store", type="string", dest="email")
    # Option that specifies the installation of OpsCenter on the first node
    parser.add_option("-o", "--opscenter", action="store", type="string", dest="opscenter")
    # Option that allows partitioners to be changed
    parser.add_option("-P", "--partitioner", action="store", type="string", dest="partitioner")

    # Option that allows partitioners to be changed
    parser.add_option("--heapsize", action="store", type="string", dest="heapsize")

    # Option that allows for a token to be declared by the user
    parser.add_option("-t", "--token", action="store", type="string", dest="token")
    # Option that allows for seeds to be declared by the user
    parser.add_option("-s", "--seeds", action="store", type="string", dest="seeds")
    # Option that allows for declaring this seed a vanilla node (in DSE)
    parser.add_option("-a", "--analyticsnode", action="store", type="string", dest="analyticsnode")

    # # Option that specifies an alternative reflector.php
    # parser.add_option("-r", "--reflector", action="store", type="string", dest="reflector")
    
    # Grab provided reflector through provided userdata
    global options
    try:
        (options, args) = parser.parse_args(shlex.split(instance_data['userdata']))
    except:
        exit_path("One of the options was not set correctly.")

    options.vanillanodes = int(options.vanillanodes)
    options.clustersize = int(options.clustersize)

def use_ec2_userdata():
    if not options:
        exit_path("EC2 User Data must be set for the DataStax AMI to run.")

    if not options.clustersize:
        exit_path("Missing required --totalnodes (-n) switch.")

    if options.version:
        if options.version.lower() == "community":
            conf.set_config("AMI", "Type", "Community")
        elif options.version.lower() == "enterprise":
            conf.set_config("AMI", "Type", "Enterprise")
        else:
            exit_path("Invalid --version (-v) argument.")
    else:
        exit_path("Missing required --version (-v) switch.")

    if options.token or options.seeds:
        if not (options.token and options.seeds):
            exit_path("Both --token (-t) and --seeds (-s) must be set in order to attach nodes.")

    if options.email:
        logger.info('Setting up diagnostic email using: {0}'.format(options.email))
        conf.set_config("AMI", "Email", options.email)

    if options.clustername:
        logger.info('Using cluster name: {0}'.format(options.clustername))
        instance_data['clustername'] = options.clustername

    logger.info('Using cluster size: {0}'.format(options.clustersize))
    conf.set_config("Cassandra", "ClusterSize", options.clustersize)
    # if options.reflector:
    #     logger.info('Using reflector: {0}'.format(options.reflector))
    
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
    logger.exe('sudo apt-get update')
    time.sleep(5)

def clean_installation():
    logger.info('Performing deployment install...')
    if conf.get_config("AMI", "Type") == "Community":
        logger.exe('sudo apt-get install -y dsc')
        logger.exe('sudo service cassandra stop')
    elif conf.get_config("AMI", "Type") == "Enterprise":
        logger.exe('sudo apt-get install -y dse-full')
        logger.exe('sudo service dse stop')

    # Remove the presaved information from startup
    logger.exe('sudo rm -rf /var/lib/cassandra')
    logger.exe('sudo rm -rf /var/log/cassandra')
    logger.exe('sudo mkdir -p /var/lib/cassandra')
    logger.exe('sudo mkdir -p /var/log/cassandra')
    logger.exe('sudo chown -R cassandra:cassandra /var/lib/cassandra')
    logger.exe('sudo chown -R cassandra:cassandra /var/log/cassandra')

def opscenter_installation():
    if instance_data['launchindex'] and options.opscenter != "no":
        logger.info('Installing OpsCenter...')
        if conf.get_config("AMI", "Type") == "Community":
            logger.exe('sudo apt-get -y install opscenter-free')
        elif conf.get_config("AMI", "Type") == "Enterprise":
            logger.exe('sudo apt-get -y install opscenter')
        logger.exe('sudo service opscenterd stop')
    elif options.opscenter == "no":
        conf.set_config("OpsCenter", "NoOpsCenter", True)

def get_seed_list():
    if options.seeds:
        # Read seed list from user-data
        config_data['seed_list'] = options.seeds.strip("'").strip('"').replace(' ', '')
        config_data['seed_list'] = config_data['seed_list'].split(",")
        logger.info(config_data['seed_list'])
    else:
        # Read seed list from reflector
        config_data['seed_list'] = []
        time_in_loop = time.time()
        continue_loop = True
        while continue_loop:
            if time.time() - time_in_loop > 10 * 60:
                exit_path('EC2 is experiencing some issues and has not allocated all of the resources in under 10 minutes.', '\n\nAborting the clustering of this reservation. Please try again.')

            logger.info('Reflector loop...')
            default_reflector = 'http://reflector2.datastax.com/reflector.php'
            if options.vanillanodes and options.vanillanodes != options.clustersize:
                second_dc_start = options.vanillanodes
                expected_responses = 2
            else:
                second_dc_start = 0
                expected_responses = 1
            req = urllib2.Request('{0}?indexid={1}&reservationid={2}&internalip={3}&externaldns={4}&secondDCstart={5}'.format(default_reflector, instance_data['launchindex'], instance_data['reservationid'], instance_data['internalip'], instance_data['publichostname'], second_dc_start))
            req.add_header('User-agent', 'DataStaxSetup')
            try:
                r = urllib2.urlopen(req).read()
                r = r.split("\n")

                status =  "[INFO] {0} Received {1} of {2} responses from: ".format(time.strftime("%m/%d/%y-%H:%M:%S", time.localtime()), r[0], expected_responses)
                status += "       {0}".format(r[2:])
                conf.set_config("AMI", "CurrentStatus", status)
                
                if int(r[0]) == expected_responses:
                    r.pop(0)
                    opscenterDNS = r[0]
                    conf.set_config("OpsCenter", "DNS", opscenterDNS)
                    r.pop(0)

                    # Assign the first IP to be a seed
                    config_data['seed_list'].append(r[0])
                    config_data['opscenterseed'] = config_data['seed_list'][0]
                    
                    if options.vanillanodes and options.vanillanodes != options.clustersize:
                        # Add one more IP to be a seed if using two datacenters
                        config_data['seed_list'].append(r[1])
                    continue_loop = False
                else:
                    time.sleep(2 + random.randint(0, options.clustersize / 4 + 1))
            except:
                traceback.print_exc(file=sys.stdout)
                time.sleep(2 + random.randint(0, 5))

def checkpoint_info():
    logger.info("Seed list: {0}".format(config_data['seed_list']))
    logger.info("OpsCenter: {0}".format(config_data['opscenterseed']))
    logger.info("Options: {0}".format(options))
    conf.set_config("AMI", "LeadingSeed", config_data['seed_list'][0])
    conf.set_config("AMI", "CurrentStatus", "Installation complete")

def calculate_tokens():
    import tokentool

    initalized = False
    if options.vanillanodes:
        tokentool.initialRingSplit([options.vanillanodes, options.clustersize - options.vanillanodes])
        initalized = True
    else:
        tokentool.initialRingSplit([options.clustersize])
        initalized = True
    
    if initalized:
        tokentool.focus()
        tokentool.calculateTokens()
        config_data['tokens'] = tokentool.originalTokens

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

    # Uses the EC2Snitch
    if not conf.get_config("AMI", "Type") == "Enterprise":
        yaml = yaml.replace('endpoint_snitch: org.apache.cassandra.locator.SimpleSnitch', 'endpoint_snitch: org.apache.cassandra.locator.Ec2Snitch')

    # Set partitioner, if provided
    if options.partitioner:
        p = re.compile('partitioner:.*')
        if options.partitioner == 'rop':
            yaml = p.sub('partitioner: org.apache.cassandra.dht.RandomPartitioner', yaml)
        if options.partitioner == 'bop':
            yaml = p.sub('partitioner: org.apache.cassandra.dht.ByteOrderedPartitioner', yaml)
        if options.partitioner == 'opp':
            yaml = p.sub('partitioner: org.apache.cassandra.dht.OrderPreservingPartitioner', yaml)
            
    # Set cluster_name to reservationid
    instance_data['clustername'] = instance_data['clustername'].strip("'").strip('"')
    yaml = yaml.replace("cluster_name: 'Test Cluster'", "cluster_name: '{0}'".format(instance_data['clustername']))

    # To allow the addition of a single node
    if options.token:
        # Set auto_bootstrap: true
        yaml += "\nauto_bootstrap: true\n"

        logger.info('Using predefined token: {0}'.format(options.token))
        p = re.compile( 'initial_token:.*')
        yaml = p.sub( 'initial_token: {0}'.format(options.token), yaml)
    # Handles the ring instantiation token settings
    else:
        # Set auto_bootstrap: false
        yaml += "\nauto_bootstrap: false\n"

        # Construct token for an equally split ring
        logger.info('Cluster tokens: {0}'.format(config_data['tokens']))
        if options.vanillanodes:
            if instance_data['launchindex'] < options.vanillanodes:
                token = config_data['tokens'][0][instance_data['launchindex']]
            else:
                token = config_data['tokens'][1][instance_data['launchindex'] - options.vanillanodes]
        else:
            token = config_data['tokens'][0][instance_data['launchindex']]
            
        p = re.compile( 'initial_token:.*')
        yaml = p.sub( 'initial_token: {0}'.format(token), yaml)
    
    with open(os.path.join(config_data['conf_path'], 'cassandra.yaml'), 'w') as f:
        f.write(yaml)
    
    logger.info('cassandra.yaml configured.')

def construct_opscenter_conf():
    try:
        with open(os.path.join(config_data['opsc_conf_path'], 'opscenterd.conf'), 'r') as f:
            opsConf = f.read()
        
        # Configure OpsCenter
        opsConf = opsConf.replace('port = 8080', 'port = 7199')
        opsConf = opsConf.replace('interface = 127.0.0.1', 'interface = 0.0.0.0')
        opsConf = opsConf.replace('seed_hosts = localhost', 'seed_hosts = {0}'.format(config_data['opscenterseed']))
        
        with open(os.path.join(config_data['opsc_conf_path'], 'opscenterd.conf'), 'w') as f:
            f.write(opsConf)
            
        logger.info('opscenterd.conf configured.')
    except:
        logger.info('opscenterd.conf not configured since conf was unable to be located.')

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
        if options.vanillanodes:
            logger.info('Using vanilla nodes: {0}'.format(options.vanillanodes))
            if instance_data['launchindex'] < options.vanillanodes:
                enable_hadoop = False

        if enable_hadoop or options.analyticsnode:
            dse_default = dse_default.replace("HADOOP_ENABLED=0", "HADOOP_ENABLED=1")

        with open('/etc/default/dse', 'w') as f:
            f.write(dse_default)

    if conf.get_config("AMI", "Type") == "Community" and (options.cfsreplication or options.vanillanodes or options.analyticsnode):
        exit_path('CFS Replication, Vanilla Nodes, and adding an Analytic Node settings can only be set in DataStax Enterprise installs.')
    
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
    partitions = glob.glob("/dev/sd*[0-9]")
    partitions.remove('/dev/sda1')
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
        logger.exe('sudo mdadm --create /dev/md0 --chunk=256 --level=0 --raid-devices={0} {1}'.format(len(devices), partion_list), expectError=True)
        raid_created = True

        logger.pipe('echo DEVICE {0}'.format(partion_list), 'sudo tee /etc/mdadm/mdadm.conf')
        time.sleep(5)
        logger.pipe('mdadm --detail --scan', 'sudo tee -a /etc/mdadm/mdadm.conf')
        time.sleep(10)
        logger.exe('blockdev --setra 65536 /dev/md0')

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
    logger.exe('sudo chown -R cassandra:cassandra {0}'.format(os.path.join(mnt_point, 'cassandra')))

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
    partitions = glob.glob("/dev/sd*[0-9]")
    partitions.remove('/dev/sda1')
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
    devices = glob.glob("/dev/sd*")
    devices.remove('/dev/sda1')
    devices.sort()
    logger.info('Unformatted devices: {0}'.format(devices))
    
    # Check if there are enough drives to start a RAID set
    if len(devices) > 1:
        time.sleep(3) # was at 20
        mnt_point = mount_raid(devices)

    # Not enough drives to RAID together.
    else:
        mnt_point = format_xfs(devices)
    
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

def additional_configurations():
    pass



def run():
    # Remove script files
    logger.exe('sudo rm ds2_configure.py')
    logger.info('Deleting ds2_configure.py now. This AMI will never change any configs after this first run.')

    clear_motd()
    get_ec2_data()
    parse_ec2_userdata()
    use_ec2_userdata()

    confirm_authentication()
    setup_repos()
    clean_installation()
    opscenter_installation()

    get_seed_list()
    checkpoint_info()

    calculate_tokens()
    construct_yaml()
    construct_opscenter_conf()
    construct_env()
    construct_dse()

    prepare_for_raid()

    sync_clocks()
    additional_configurations()

    logger.info("ds2_configure.py completed!\n")
    conf.set_config("AMI", "CurrentStatus", "Complete!")

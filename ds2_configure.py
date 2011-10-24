#!/usr/bin/env python
### Script provided by DataStax.

import urllib2, os, re, subprocess, sys, glob, random, time, traceback
from optparse import OptionParser
import logger
import conf

# Full path must be used since this script will execute at
# startup as no root user
confPath = os.path.expanduser("/etc/cassandra/")
opsConfPath = os.path.expanduser("/etc/opscenter/")

opscenterseed = 0

internalip = 0
publichostname = 0
launchindex = 0
reservationid = False
clustername = False
jmxPass = False
userdata = False
seedList = []
options = False

tokens = {}


def clearMOTD():
    # To clear the default MOTD
    logger.exe('sudo rm -rf /etc/motd')
    logger.exe('sudo touch /etc/motd')

def getAddresses():
    # Find internal IP address for seed list
    global internalip
    req = urllib2.Request('http://instance-data/latest/meta-data/local-ipv4')
    internalip = urllib2.urlopen(req).read()
    
    # Find public hostname for JMX
    req = urllib2.Request('http://instance-data/latest/meta-data/public-hostname')
    global publichostname
    publichostname = urllib2.urlopen(req).read()
    
    # Find launch index for token splitting
    req = urllib2.Request('http://instance-data/latest/meta-data/ami-launch-index')
    global launchindex
    launchindex = int(urllib2.urlopen(req).read())
    
    # Find reservation-id for cluster-id and jmxpass
    req = urllib2.Request('http://instance-data/latest/meta-data/reservation-id')
    global reservationid, jmxPass, clustername
    reservationid = urllib2.urlopen(req).read()
    jmxPass = reservationid
    clustername = reservationid

    # Try to get EC2 User Data
    userDataExists = False
    try:
        req = urllib2.Request('http://instance-data/latest/user-data/')
        global userdata
        userdata = urllib2.urlopen(req).read()
        userDataExists = True
        
    except Exception, e:
        logger.info("No User Data was set. Naming cluster the same as the reservation ID.")
        logger.exe('sudo add-apt-repository "deb http://www.apache.org/dist/cassandra/debian 08x main"')
        logger.exe('sudo apt-get update')
        logger.exe('sudo apt-get install -y cassandra')
        logger.exe('sudo rm -rf /var/lib/cassandra/*')
        logger.exe('sudo service cassandra stop')

    if userDataExists:
        # Setup parser
        parser = OptionParser()

        # Development options
        # Option that specifies the cluster's name
        parser.add_option("-d", "--dev", action="store", type="string", dest="dev")
        
        # Letters available: ...
        # Option that specifies the cluster's name
        parser.add_option("-c", "--clustername", action="store", type="string", dest="clustername")
        # Option that specifies how the ring will be divided
        parser.add_option("-n", "--totalnodes", action="store", type="string", dest="clustersize")
        # Option that specifies how the number of Cassandra nodes
        parser.add_option("-r", "--realtimenodes", action="store", type="string", dest="vanillanodes")
        # Option that specifies the CassandraFS replication factor
        parser.add_option("-f", "--cfsreplicationfactor", action="store", type="string", dest="cfsreplication")
        # Option that specifies the username
        parser.add_option("-u", "--username", action="store", type="string", dest="username")
        # Option that specifies the password
        parser.add_option("-w", "--password", action="store", type="string", dest="password")
        # Option that allows for an emailed report of the startup diagnostics
        parser.add_option("-e", "--email", action="store", type="string", dest="email")
        # Option that specifies the installation of OpsCenter on the first node
        # parser.add_option("-o", "--opscenter", action="store", type="string", dest="opscenter")
        # Option that allows partitioners to be changed
        parser.add_option("-p", "--partitioner", action="store", type="string", dest="partitioner")

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
            (options, args) = parser.parse_args(userdata.strip().split(" "))
        except:
            logger.error('One of the options was not set correctly. Please verify your settings')
            print userdata

        conf.setConfig("AMI", "Type", "Community")
        if options.username and options.password:
            repo_url = "http://deb.opsc.datastax.com/"

            # Configure HTTP authentication
            password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
            password_mgr.add_password(None, repo_url, options.username, options.password)
            handler = urllib2.HTTPBasicAuthHandler(password_mgr)
            opener = urllib2.build_opener(handler)

            # Try reading from the authenticated connection
            try:
                opener.open(repo_url)
                conf.setConfig("AMI", "Type", "Enterprise")
                global confPath
                confPath = os.path.expanduser("/etc/dse/cassandra/")
            except Exception as inst:
                # Print error message if failed
                if "401" in str(inst):
                    logger.warn('Authentication failed. Continuing with DataStax Community.')
        elif options.username or options.password:
            logger.warn('Both username and password are required to use DataStax Enterprise. Continuing with DataStax Community.')
            
        # Add repos
        if conf.getConfig("AMI", "Type") == "Enterprise":
            logger.pipe('echo "deb http://' + options.username + ':' + options.password + '@debian.datastax.com/enterprise unstable main"', 'sudo tee -a /etc/apt/sources.list.d/datastax.sources.list')
        else:
            logger.pipe('echo "deb http://debian.datastax.com/community unstable main"', 'sudo tee -a /etc/apt/sources.list.d/datastax.sources.list')

        logger.pipe('echo "deb http://debian.riptano.com/maverick maverick main"', 'sudo tee -a /etc/apt/sources.list.d/datastax.sources.list')
        logger.pipe('echo "deb http://debian.datastax.com/maverick maverick main"', 'sudo tee -a /etc/apt/sources.list.d/datastax.sources.list')
        logger.pipe('curl -s http://installer.datastax.com/downloads/ubuntuarchive.repo_key', 'sudo apt-key add -')
        logger.pipe('curl -s http://opscenter.datastax.com/debian/repo_key', 'sudo apt-key add -')
        logger.pipe('curl -s http://debian.datastax.com/debian/repo_key', 'sudo apt-key add -')

        if options.dev:
            logger.pipe('echo "deb ' + options.dev.split(',')[0] + ' maverick main"', 'sudo tee -a /etc/apt/sources.list.d/datastax.sources.list')
            logger.pipe('curl -s ' + options.dev.split(',')[1], 'sudo apt-key add -')

        # Perform the install
        logger.exe('sudo apt-get update')
        time.sleep(5)
        logger.info('Performing deployment install...')
        if conf.getConfig("AMI", "Type") == "Community":
            logger.exe('sudo apt-get install -y apache-cassandra1')
            logger.exe('sudo rm -rf /var/lib/cassandra/*')
            logger.exe('sudo service cassandra stop')
            logger.exe('sudo apt-get install -y dsc-demos')
        elif conf.getConfig("AMI", "Type") == "Enterprise":
            logger.exe('sudo apt-get install -y dse-full')
            logger.exe('sudo rm -rf /var/lib/cassandra/*')
            logger.exe('sudo service dse stop')

        # Remove the presaved information from startup
        logger.exe('sudo rm -rf /var/lib/cassandra')
        logger.exe('sudo rm -rf /var/log/cassandra')
        logger.exe('sudo mkdir -p /var/lib/cassandra')
        logger.exe('sudo mkdir -p /var/log/cassandra')
        logger.exe('sudo chown -R cassandra:cassandra /var/lib/cassandra')
        logger.exe('sudo chown -R cassandra:cassandra /var/log/cassandra')

        if options and options.email:
            logger.info('Setting up diagnostic email using: ' + options.email)
            conf.setConfig("AMI", "Email", options.email)
        if options and options.clustername:
            logger.info('Using cluster name: ' + options.clustername)
            clustername = options.clustername
        if int(launchindex) == 0:
            if not conf.getConfig("OpsCenter", "DNS"):
                logger.info('Installing OpsCenter...')
                if conf.getConfig("AMI", "Type") == "Community":
                    logger.exe('sudo apt-get -y install opscenter-free')
                elif conf.getConfig("AMI", "Type") == "Enterprise":
                    logger.exe('sudo apt-get -y install opscenter')
                logger.exe('sudo service opscenterd stop')
        if options and options.cfsreplication:
            if conf.getConfig("AMI", "Type") == "Enterprise":
                logger.info('Using cfsreplication factor: ' + options.cfsreplication)
                with open('/etc/default/dse', 'r') as f:
                    dseDefault = f.read()

                dseDefault = dseDefault.replace("#CFS_REPLICATION_FACTOR=1", "CFS_REPLICATION_FACTOR=" + options.cfsreplication)
                
                with open('/etc/default/dse', 'w') as f:
                    f.write(dseDefault)
            else:
                logger.error('CFS replication can only be set in DataStax Enterprise installs. Please refer to SWITCHES.txt if you wish to run DataStax Enterprise.')
                logger.error('Continuing as Cassandra 0.8.')
        if options and options.vanillanodes:
            if conf.getConfig("AMI", "Type") == "Enterprise":
                logger.info('Using vanilla nodes: ' + options.vanillanodes)
                options.vanillanodes = int(options.vanillanodes)
                if int(launchindex) >= options.vanillanodes:
                    with open('/etc/default/dse', 'r') as f:
                        dseDefault = f.read()

                    dseDefault = dseDefault.replace("HADOOP_ENABLED=0", "HADOOP_ENABLED=1")
                    
                    with open('/etc/default/dse', 'w') as f:
                        f.write(dseDefault)
                if not options.clustersize:
                    logger.error('Vanilla option was set without Cluster Size.')
                    logger.error('Continuing as a collection of 1-node clusters.')
                    sys.exit(1)
            else:
                logger.error('Vanilla nodes can only be set in DataStax Enterprise installs. Please refer to SWITCHES.txt if you wish to run DataStax Enterprise.')
                logger.error('Continuing as Cassandra 0.8.')
        else:
            if conf.getConfig("AMI", "Type") == "Enterprise":
                with open('/etc/default/dse', 'r') as f:
                    dseDefault = f.read()

                dseDefault = dseDefault.replace("HADOOP_ENABLED=0", "HADOOP_ENABLED=1")
                
                with open('/etc/default/dse', 'w') as f:
                    f.write(dseDefault)

        if options and options.analyticsnode:
            if conf.getConfig("AMI", "Type") == "Enterprise":
                with open('/etc/default/dse', 'r') as f:
                    dseDefault = f.read()

                dseDefault = dseDefault.replace("HADOOP_ENABLED=0", "HADOOP_ENABLED=1")
                
                with open('/etc/default/dse', 'w') as f:
                    f.write(dseDefault)

        if options and options.clustersize:
            logger.info('Using cluster size: ' + options.clustersize)
            conf.setConfig("Cassandra", "ClusterSize", options.clustersize)
        # if options.reflector:
        #     logger.info('Using reflector: ' + options.reflector)
        
    # Remove script files
    logger.exe('sudo rm ds2_configure.py')
    logger.info('Deleting ds2_configure.py now. This AMI will never change any configs after this first run.')
    
    global opscenterseed

    # DSE DC splitting
    global seedList
    if options and options.seeds:
        seedList = options.seeds.strip("'").strip('"').replace(' ', '')
        seedList = seedList.split(",")
        logger.info(seedList)

        stayinloop = False
    else:
        stayinloop = True
    timeIntoLoop = time.time()
    while stayinloop:
        if time.time() - timeIntoLoop > 10 * 60:
            logger.error('EC2 must have not started the cluster correctly. Aborting the clustering of this reservation. Please try again.')
            return

        logger.info('Reflector loop...')
        defaultReflector = 'http://reflector2.datastax.com/reflector.php'
        if options and options.vanillanodes and int(options.vanillanodes) != int(options.clustersize):
            req = urllib2.Request(defaultReflector + '?indexid=' + str(launchindex) + '&reservationid=' + reservationid + '&internalip=' + internalip + '&externaldns=' + publichostname + '&secondDCstart=' + str(options.vanillanodes))
            expectedResponses = 2
        else:
            req = urllib2.Request(defaultReflector + '?indexid=' + str(launchindex) + '&reservationid=' + reservationid + '&internalip=' + internalip + '&externaldns=' + publichostname + '&secondDCstart=0')
            expectedResponses = 1
        req.add_header('User-agent', 'DataStaxSetup')
        try:
            r = urllib2.urlopen(req).read()
            r = r.split("\n")

            status =  "[INFO] " + time.strftime("%m/%d/%y-%H:%M:%S", time.localtime()) + " Received " + r[0] + " of " + str(expectedResponses) + " responses from: "
            status += "       " + str(r[2:])
            conf.setConfig("AMI", "CurrentStatus", status)
            
            if options and options.vanillanodes and not options.clustersize:
                logger.error('-r only works with -n also set. Starting up nodes with NO configurations.')
                stayinloop = False
                break
            if int(r[0]) == expectedResponses:
                r.pop(0)
                opscenterDNS = r[0]
                r.pop(0)

                # Assign the first IP to be a seed
                seedList.append(r[0])
                opscenterseed = seedList[0]
                
                if options and options.vanillanodes and int(options.vanillanodes) != int(options.clustersize):
                    # Add one more IP to be a seed
                    seedList.append(r[1])
                stayinloop = False
            else:
                if options and options.clustersize:
                    time.sleep(2 + random.randint(0, int(options.clustersize) / 4 + 1))
                else:
                    time.sleep(2 + random.randint(0, 5))
        except:
            traceback.print_exc(file=sys.stdout)
            time.sleep(2 + random.randint(0, 5))
    
    conf.setConfig("AMI", "CurrentStatus", "Complete!")

    conf.setConfig("AMI", "LeadingSeed", seedList[-1])

    if options and options.vanillanodes and not options.clustersize:
        sys.exit(0)

    conf.setConfig("OpsCenter", "DNS", opscenterDNS)
    
    if userdata:
        logger.info("Started with user data set to:")
        print userdata
    else:
        logger.info("No user data was set.")
    logger.info("Seed list: " + str(seedList))
    logger.info("OpsCenter: " + str(opscenterseed))
    logger.info("Options: " + str(options))

def calculateTokens():
    import tokentool
    global tokens

    initalized = False
    if options and options.vanillanodes:
        tokentool.initialRingSplit([int(options.vanillanodes), int(options.clustersize) - int(options.vanillanodes)])
        initalized = True
    elif options and options.clustersize:
        tokentool.initialRingSplit([int(options.clustersize)])
        initalized = True
    
    if initalized:
        tokentool.focus()
        tokentool.calculateTokens()
        tokens = tokentool.originalTokens

def constructYaml():
    with open(confPath + 'cassandra.yaml', 'r') as f:
        yaml = f.read()

    # Create the seed list
    global seedList
    
    # Create the seed list
    seedsYaml = ''
    for ip in seedList:
        seedsYaml += ip + ','
    seedsYaml = seedsYaml[:-1]

    # Set seeds for 0.8
    p = re.compile('seeds:.*')
    yaml = p.sub('seeds: "' + seedsYaml + '"', yaml)

    # Set listen_address
    p = re.compile('listen_address:.*')
    yaml = p.sub('listen_address: ' + internalip, yaml)
    
    # Set rpc_address
    p = re.compile('rpc_address:.*')
    yaml = p.sub('rpc_address: ' + internalip, yaml)

    # Uses the EC2Snitch
    if not conf.getConfig("AMI", "Type") == "Enterprise":
        yaml = yaml.replace('endpoint_snitch: org.apache.cassandra.locator.SimpleSnitch', 'endpoint_snitch: org.apache.cassandra.locator.Ec2Snitch')

    # Set partitioner, if provided
    if options and options.partitioner:
        p = re.compile('partitioner:.*')
        if options.partitioner == 'rop':
            yaml = p.sub('partitioner: org.apache.cassandra.dht.RandomPartitioner', yaml)
        if options.partitioner == 'bop':
            yaml = p.sub('partitioner: org.apache.cassandra.dht.ByteOrderedPartitioner', yaml)
        if options.partitioner == 'opp':
            yaml = p.sub('partitioner: org.apache.cassandra.dht.OrderPreservingPartitioner', yaml)
            
    # Set cluster_name to reservationid
    global clustername
    clustername = clustername.strip("'").strip('"')
    yaml = yaml.replace("cluster_name: 'Test Cluster'", "cluster_name: '" + clustername + "'")
    
    if options and options.token:
        logger.info('Using predefined token: ' + options.token)
        p = re.compile( 'initial_token:.*')
        yaml = p.sub( 'initial_token: ' + options.token, yaml)
    else:
        # Construct token for an equally split ring
        logger.info('Cluster tokens: ' + str(tokens))
        if options and options.clustersize:
            if options.vanillanodes:
                if launchindex < options.vanillanodes:
                    print 1
                    token = tokens[0][launchindex]
                else:
                    print 2
                    token = tokens[1][launchindex - options.vanillanodes]
            else:
                print 3
                token = tokens[0][launchindex]
                
            p = re.compile( 'initial_token:.*')
            yaml = p.sub( 'initial_token: ' + str(token), yaml)
    
    with open(confPath + 'cassandra.yaml', 'w') as f:
        f.write(yaml)
    
    logger.info('cassandra.yaml configured.')

def constructOpscenterConf():
    try:
        with open(opsConfPath + 'opscenterd.conf', 'r') as f:
            opsConf = f.read()
        
        # Configure OpsCenter
        opsConf = opsConf.replace('port = 8080', 'port = 7199')
        opsConf = opsConf.replace('interface = 127.0.0.1', 'interface = 0.0.0.0')
        opsConf = opsConf.replace('seed_hosts = localhost', 'seed_hosts = ' + opscenterseed)
        
        with open(opsConfPath + 'opscenterd.conf', 'w') as f:
            f.write(opsConf)
            
        logger.info('opscenterd.conf configured.')
    except:
        logger.info('opscenterd.conf not configured since conf was unable to be located.')

def constructEnv():
    envsh = None
    with open(confPath + 'cassandra-env.sh', 'r') as f:
        envsh = f.read()
    
    # Clear commented line
    envsh = envsh.replace('# JVM_OPTS="$JVM_OPTS -Djava.rmi.server.hostname=<public name>"', 'JVM_OPTS="$JVM_OPTS -Djava.rmi.server.hostname=<public name>"')
    
    # Set JMX hostname and password file
    settings = 'JVM_OPTS="$JVM_OPTS -Djava.rmi.server.hostname=' + internalip + '"\n'
    
    # Perform the replacement
    p = re.compile('JVM_OPTS="\$JVM_OPTS -Djava.rmi.server.hostname=(.*\s*)*?#')
    envsh = p.sub(settings + '\n\n#', envsh)
    
    with open(confPath + 'cassandra-env.sh', 'w') as f:
        f.write(envsh)
    
    logger.info('cassandra-env.sh configured.')
    
def mountRAID():
    # Only create raid0 once. Mount all times in init.d script.
    if not conf.getConfig("AMI", "RAIDCreated"):

        # Remove EC2 default /mnt from fstab
        fstab = ''
        fileToOpen = '/etc/fstab'
        logger.exe('sudo chmod 777 ' + fileToOpen)
        with open(fileToOpen, 'r') as f:
            for line in f:
                if not "/mnt" in line:
                    fstab += line
        with open(fileToOpen, 'w') as f:
            f.write(fstab)
        logger.exe('sudo chmod 644 ' + fileToOpen)
        
        # Create a list of devices
        devices = glob.glob("/dev/sd*")
        devices.remove('/dev/sda1')
        devices.sort()
        logger.info('Unformatted devices: ' + str(devices))
        
        # Check if there are enough drives to start a RAID set
        if len(devices) > 1:
            # Make sure the devices are umounted, then run fdisk on each device
            logger.info('Clear "invalid flag 0x0000 of partition table 4" by issuing a write, then running fdisk on each device...')
            formatCommands = """echo 'n
    p
    1


    t
    fd
    w'"""
            for device in devices:
                logger.info('Confirming devices are not mounted:')
                logger.exe('sudo umount ' + device, False)
                logger.pipe("echo 'w'", 'sudo fdisk -c -u ' + device)
                logger.pipe(formatCommands, 'sudo fdisk -c -u ' + device)
        
            # Create a list of partitions to RAID
            logger.exe('sudo fdisk -l')
            partitions = glob.glob("/dev/sd*[0-9]")
            partitions.remove('/dev/sda1')
            partitions.sort()
            logger.info('Partitions about to be added to RAID0 set: ' + str(partitions))
        
            # Make sure the partitions are umounted and create a list string
            partionList = ''
            for partition in partitions:
                logger.info('Confirming partitions are not mounted:')
                logger.exe('sudo umount ' + partition, False)
                partionList += partition + ' '
            partionList = partionList.strip()
        
            logger.info('Creating the RAID0 set:')
            time.sleep(5)
            logger.pipe('yes', 'sudo mdadm --create /dev/md0 --chunk=256 --level=0 --raid-devices=' + str(len(devices)) + ' ' + partionList, False)
            logger.pipe('echo DEVICE ' + partionList, 'sudo tee /etc/mdadm/mdadm.conf')
            logger.pipe('mdadm --detail --scan', 'sudo tee -a /etc/mdadm/mdadm.conf')
            time.sleep(5)
            logger.exe('blockdev --setra 65536 /dev/md0')

            logger.info('Formatting the RAID0 set:')
            time.sleep(5)
            logger.exe('sudo mkfs.xfs -f /dev/md0')
            
            # Configure fstab and mount the new RAID0 device
            raidMnt = '/raid0'
            logger.pipe("echo '/dev/md0\t" + raidMnt + "\txfs\tdefaults,nobootwait,noatime\t0\t0'", 'sudo tee -a /etc/fstab')
            logger.exe('sudo mkdir ' + raidMnt)
            logger.exe('sudo mount -a')
            logger.exe('sudo mkdir -p ' + raidMnt + '/cassandra/')
            logger.exe('sudo chown -R ubuntu:ubuntu ' + raidMnt + '/cassandra')
        
            logger.info('Showing RAID0 details:')
            logger.exe('cat /proc/mdstat')
            logger.exe('echo "15000" > /proc/sys/dev/raid/speed_limit_min')
            logger.exe('sudo mdadm --detail /dev/md0')

        else:
            # Make sure the device is umounted, then run fdisk on the device
            logger.info('Clear "invalid flag 0x0000 of partition table 4" by issuing a write, then running fdisk on the device...')
            formatCommands = """echo 'd
    n
    p
    1


    t
    83
    w'"""
            logger.exe('sudo umount ' + devices[0])
            logger.pipe("echo 'w'", 'sudo fdisk -c -u ' + devices[0])
            logger.pipe(formatCommands, 'sudo fdisk -c -u ' + devices[0])
            
            # Create a list of partitions to RAID
            logger.exe('sudo fdisk -l')
            partitions = glob.glob("/dev/sd*[0-9]")
            partitions.remove('/dev/sda1')
            partitions.sort()
            
            logger.info('Formatting the new partition:')
            logger.exe('sudo mkfs.xfs -f ' + partitions[0])
            
            # Configure fstab and mount the new formatted device
            mntPoint = '/mnt'
            logger.pipe("echo '" + partitions[0] + "\t" + mntPoint + "\txfs\tdefaults,nobootwait,noatime\t0\t0'", 'sudo tee -a /etc/fstab')
            logger.exe('sudo mkdir ' + mntPoint, False)
            logger.exe('sudo mount -a')
            logger.exe('sudo mkdir -p ' + mntPoint + '/cassandra')
            logger.exe('sudo chown -R cassandra:cassandra ' + mntPoint + '/cassandra')
        
        # Change cassandra.yaml to point to the new data directories
        with open(confPath + 'cassandra.yaml', 'r') as f:
            yaml = f.read()
        if len(partitions) > 1:
            yaml = yaml.replace('/var/lib/cassandra/data', raidMnt + '/cassandra/data')
            yaml = yaml.replace('/var/lib/cassandra/saved_caches', raidMnt + '/cassandra/saved_caches')
            yaml = yaml.replace('/var/lib/cassandra/commitlog', raidMnt + '/cassandra/commitlog')
        else:
            yaml = yaml.replace('/var/lib/cassandra/data', mntPoint + '/cassandra/data')
            yaml = yaml.replace('/var/lib/cassandra/saved_caches', mntPoint + '/cassandra/saved_caches')
            yaml = yaml.replace('/var/lib/cassandra/commitlog', mntPoint + '/cassandra/commitlog')
        with open(confPath + 'cassandra.yaml', 'w') as f:
            f.write(yaml)
        
        # Remove the old cassandra folders
        subprocess.Popen("sudo rm -rf /var/log/cassandra/*", shell=True)
        subprocess.Popen("sudo rm -rf /var/lib/cassandra/*", shell=True)
        logger.exe('sudo chown -R cassandra:cassandra /var/lib/cassandra')
        logger.exe('sudo chown -R cassandra:cassandra /var/log/cassandra')

        # Never create raid array again
        conf.setConfig("AMI", "RAIDCreated", True)

        logger.info("Mounted Raid.\n")

def syncClocks():
    # Confirm that NTP is installed
    logger.exe('sudo apt-get -y install ntp')
    
    with open('/etc/ntp.conf', 'r') as f:
            ntpConf = f.read()

    # Create a list of ntp server pools
    serverList = ""
    for i in range(0, 4):
        serverList += "server " + str(i) + ".north-america.pool.ntp.org\n"

    # Overwrite the single ubuntu ntp server with the server pools
    ntpConf = ntpConf.replace('server ntp.ubuntu.com', serverList)

    with open('/etc/ntp.conf', 'w') as f:
        f.write(ntpConf)

    # Restart the service
    logger.exe('sudo service ntp restart')

def additionalConfigurations():
    pass




clearMOTD()
getAddresses()

calculateTokens()
constructYaml()
constructOpscenterConf()
constructEnv()

mountRAID()

syncClocks()
additionalConfigurations()

logger.info("ds2_configure.py completed!\n")

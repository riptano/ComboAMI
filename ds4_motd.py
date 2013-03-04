#!/usr/bin/env python
### Script provided by DataStax.

import os
import re
import shlex
import subprocess
import sys
import time
import urllib2

import conf

import gzip
import StringIO
from email.parser import Parser

config_data = {}
config_data['nodetool_statement'] = 'nodetool -h localhost ring'

def ami_error_handling():
    if conf.get_config("AMI", "Error"):
        print
        print conf.get_config("AMI", "Error")
        print
        print "Please visit http://datastax.com/ami for this AMI's feature set."
        print
        sys.exit(1)

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

def print_userdata():
    try:
        req = urllib2.Request('http://instance-data/latest/user-data/')
        config_data['userdata'] = get_user_data(req)

        # Remove passwords from printing: -p
        p = re.search('(-p\s+)(\S*)', config_data['userdata'])
        if p:
            config_data['userdata'] = config_data['userdata'].replace(p.group(2), '****')

        # Remove passwords from printing: --password
        p = re.search('(--password\s+)(\S*)', config_data['userdata'])
        if p:
            config_data['userdata'] = config_data['userdata'].replace(p.group(2), '****')

        print
        print "Cluster started with these options:"
        print config_data['userdata']
        print
    except:
        print "No cluster configurations set."

def waiting_for_status():
    config_data['waiting_for_status'] = False
    dots = 0
    while True:
        status = conf.get_config("AMI", "CurrentStatus")
        if not status == 'Complete!' and not status == False:
            ticker = ''
            for i in range(dots):
                ticker += '.'

            sys.stdout.write("\r                                                                                                                         ")
            sys.stdout.write("\r%s%s " % (status, ticker))
            sys.stdout.flush()
        elif status == 'Complete!':
            break
        else:
            if not config_data['waiting_for_status']:
                print "Waiting for cluster to boot..."
                config_data['waiting_for_status'] = True
        ami_error_handling()
        time.sleep(5)
        dots = (dots + 1) % 4
    print

def waiting_for_nodetool():
    print "Waiting for nodetool..."
    print "The cluster is now in it's finalization phase. This should only take a moment..."
    print
    print "Note: You can also use CTRL+C to view the logs if desired:"
    print "    AMI log: ~/datastax_ami/ami.log"
    print "    Cassandra log: /var/log/cassandra/system.log"
    print
    print

    retcode = 0
    while True:
        retcode = subprocess.call(shlex.split(config_data['nodetool_statement']), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if (int(retcode) != 3):
            break

def check_for_one_up_node():
    stopped_error_msg = False
    while True:
        ami_error_handling()
        nodetool_out = subprocess.Popen(shlex.split(config_data['nodetool_statement']), stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.read()
        if (nodetool_out.lower().find("error") == -1 and nodetool_out.lower().find("up") and len(nodetool_out) > 0):
            if not stopped_error_msg:
                if config_data['waiting_for_status']:
                    time.sleep(15)
                stopped_error_msg = True
            else:
                break
    return nodetool_out

def waiting_for_full_cluster_to_launch(nodetool_out):
    start_time = time.time()
    while True:
        if nodetool_out.count("Up") == int(conf.get_config("Cassandra", "TotalNodes")):
            break
        if nodetool_out.count("UN") == int(conf.get_config("Cassandra", "TotalNodes")):
            break
        if time.time() - start_time > 60:
            break

        if conf.get_config('Cassandra', 'partitioner') == 'murmur':
            config_data['nodetool_statement'] = 'nodetool status'
        nodetool_out = subprocess.Popen(shlex.split(config_data['nodetool_statement']), stderr=subprocess.PIPE, stdout=subprocess.PIPE).stdout.read()

    print nodetool_out

def print_opscenter_information():
    try:
        opscenter_ip = conf.get_config("OpsCenter", "DNS")
        opscenter_port = conf.get_config("OpsCenter", "port")
        packageQuery = subprocess.Popen(shlex.split("dpkg-query -l 'opscenter'"), stderr=subprocess.PIPE, stdout=subprocess.PIPE).stdout.read()
        if packageQuery:
            print "Opscenter: http://{0}:{1}/".format(opscenter_ip, opscenter_port)
            print "    Please wait 60 seconds if this is the cluster's first start..."
            print
            print
    except:
        pass

def print_tools():
    print "Tools:"
    print "    Run: datastax_tools"
    print "Demos:"
    print "    Run: datastax_demos"
    print "Support:"
    print "    Run: datastax_support"

def print_trialing_info():
    try:
        with open('/home/ubuntu/datastax_ami/presetup/VERSION', 'r') as f:
            version = f.readline().strip()
    except:
        version = "<< $HOME/datastax_ami/presetup/VERSION missing >>"

    substring = "Version: "
    versionInfo = subprocess.Popen(shlex.split("dpkg -s %s" % conf.get_config("AMI", "package")), stdout=subprocess.PIPE).stdout.read()
    versionInfo = versionInfo[versionInfo.find(substring) + len(substring) : versionInfo.find("\n", versionInfo.find(substring))].strip()
    if conf.get_config("AMI", "Type") == "Community":
        versionInfo = "DataStax Community version " + versionInfo
    if conf.get_config("AMI", "Type") == "Enterprise":
        versionInfo = "DataStax Enterprise version " + versionInfo

    print """

------------------------------------
DataStax AMI for DataStax Enterprise
and DataStax Community
AMI version {0}
{1}

------------------------------------

""".format(version, versionInfo)


def print_errors():
    notices = ''
    knownErrors = []
    knownErrors.append("yes: write error\n")
    knownErrors.append("java.io.ioexception: timedoutexception()\n")
    knownErrors.append("caused by: timedoutexception()\n")
    knownErrors.append("Error getting MD array info from /dev/md0\n".lower())
    for line in open('/home/ubuntu/datastax_ami/ami.log'):
        if ('error' in line.lower() or '[warn]' in line.lower() or 'exception' in line.lower()) and not (line.lower() in knownErrors or line.startswith('xss =  ')):
            notices += line

    if len(notices) > 0:
        print "These notices occurred during the startup of this instance:"
        print notices

def run():
    ami_error_handling()
    print_userdata()

    waiting_for_status()
    waiting_for_nodetool()
    nodetool_out = check_for_one_up_node()
    waiting_for_full_cluster_to_launch(nodetool_out)

    print_opscenter_information()
    print_tools()
    print_trialing_info()
    print_errors()

run()

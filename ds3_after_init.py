#!/usr/bin/env python
### Script provided by DataStax.

import os
import smtplib
import shlex
import subprocess
import time
import urllib2

from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText

from email.MIMEBase import MIMEBase
from email import Encoders

import logger
import conf

config_data = {}

def exe(command, external_log=False):
    # Helper function to execute commands and print traces of the command and output for debugging/logging purposes
    process = subprocess.Popen(shlex.split(command), stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    read = process.communicate()
    
    # Print output on next line if it exists
    if len(read[0]) > 0:
        print '[EXEC] ' + command + ":\n" + read[0]
    elif len(read[1]) > 0:
        print '[ERROR] ' + command + ":\n" + read[1]
    else:
        print '[EXEC] ' + command
    
    if external_log:
        log = '[EXEC] ' + command + "\n"
        if len(read[0]) > 0:
            log += read[0] + "\n"
        if len(read[1]) > 0:
            log += '[ERROR] ' + read[1] + "\n"
        return log
    return process

def get_ec2_data():
    # Collect EC2 variables
    req = urllib2.Request('http://169.254.169.254/latest/meta-data/reservation-id')
    config_data['reservationid'] = urllib2.urlopen(req).read()

    req = urllib2.Request('http://169.254.169.254/latest/meta-data/local-ipv4')
    config_data['internalip'] = urllib2.urlopen(req).read()

    req = urllib2.Request('http://169.254.169.254/latest/meta-data/public-hostname')
    config_data['publichostname'] = urllib2.urlopen(req).read()

    req = urllib2.Request('http://169.254.169.254/latest/meta-data/ami-launch-index')
    config_data['launchindex'] = int(urllib2.urlopen(req).read())

def get_email_auth():
    # Setup global variables
    config_data['smtp'] = None
    config_data['port'] = None
    config_data['username'] = None
    config_data['password'] = None

    # Ensure that the ring output is in the log
    logger.exe('nodetool -h localhost ring')

    # Parse Email information
    if conf.get_config("AMI", "Email"):
        try:
            raw_email = conf.get_config("AMI", "Email")
            read = raw_email.split(':')

            logger.info("Parsed Email Options: {0}".format(read))

            config_data['smtp'] = read[0]
            config_data['port'] = read[1]
            config_data['username'] = read[2]
            config_data['password'] = read[3]
        except:
            print "[ERROR] No emails will be sent. Error during parsing."

def check_and_launch_opscenter():
    if config_data['launchindex'] == 0 and conf.get_config("OpsCenter", "DNS") and not conf.get_config("AMI", "CompletedFirstBoot") and not conf.get_config("OpsCenter", "NoOpsCenter"):
        logger.exe('sudo service opscenterd restart')
        conf.set_config("AMI", "CompletedFirstBoot", True)

def email_report(subject, message):
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg.attach(MIMEText(message))

    msg = msg.as_string().replace('yes: write error','yes: write nrror')

    # The actual mail send
    server = smtplib.SMTP(config_data['smtp'] + ':' + config_data['port'])
    server.starttls()
    server.login(config_data['username'], config_data['password'])
    server.sendmail(config_data['username'], config_data['username'], msg)
    server.quit()

def smoke_test():
    if conf.get_config("AMI", "SmokeURL") and conf.get_config("AMI", "SmokeFile") and config_data['launchindex'] == 0:
        smokeURL = conf.get_config("AMI", "SmokeURL")
        smokeFile = conf.get_config("AMI", "SmokeFile")

        import urllib
        urllib.urlretrieve (smokeURL, 'smoke.tar.gz')
        log = exe('tar xvf smoke.tar.gz', True)

        os.chdir('/home/ubuntu/smoke')
        log += "-----------------------------------------------------" + "\n"
        log += "-------------------- SMOKE TESTS --------------------" + "\n"
        log += "-----------------------------------------------------" + "\n"
        log += "Retrieved: " + smokeURL + "\n"
        log += "Executing: " + smokeFile + "\n"
        log += "\n"

        with open(smokeFile, 'r') as f:
            log += f.read() + "\n"

        log += "-----------------------------------------------------" + "\n"
        
        log += exe('sudo chmod +x ' + smokeFile, True)
        log += exe('./' + smokeFile, True)
        
        log += "-----------------------------------------------------" + "\n"
        log += "--------------------- END TESTS ---------------------" + "\n"
        log += "-----------------------------------------------------" + "\n"
        os.chdir('/home/ubuntu/')

        # Email smoke test results
        email_report('SMOKE-TESTS ::: ' + smokeFile + ' ::: ' + config_data['publichostname'], log)

def check_and_send_emails():
    # Send email if username and password were read
    if config_data['username'] and config_data['password']:
        with open('ami.log', 'r') as f:
            ami_log = f.read()

        email_report(config_data['reservationid'] + ' ::: ' + config_data['internalip'] + ' ::: ' + config_data['publichostname'], ami_log)

        # Run smoke tests
        smoke_test()

def run():
    print '[INFO] Waiting 60 seconds to restart opscenter, setup demos, and possibly send emails...'
    time.sleep(60)

    get_ec2_data()
    get_email_auth()
    check_and_launch_opscenter()
    check_and_send_emails()

run()

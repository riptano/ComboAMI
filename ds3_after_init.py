#!/usr/bin/env python
### Script provided by DataStax.

import shlex, subprocess, os, time, urllib2, smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText

from email.MIMEBase import MIMEBase
from email import Encoders

import logger
import conf

def exe(command, externalLog=False):
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
    
    if externalLog:
        log = '[EXEC] ' + command + "\n"
        if len(read[0]) > 0:
            log += read[0] + "\n"
        if len(read[1]) > 0:
            log += '[ERROR] ' + read[1] + "\n"
        return log
    return process

def checkAndLaunchOpsCenter():
    global launchindex
    if int(launchindex) == 0 and conf.getConfig("OpsCenter", "DNS") and not conf.getConfig("AMI", "CompletedFirstBoot"):
        logger.exe('sudo service opscenterd restart')
        conf.setConfig("AMI", "CompletedFirstBoot", True)

def setupDemos():
    global launchindex
    if int(launchindex) == 0:
        req = urllib2.Request('http://instance-data/latest/meta-data/local-ipv4')
        internalip = urllib2.urlopen(req).read()

        logger.exe('sudo /usr/share/dse-demos/portfolio_manager/bin/pricer -o INSERT_PRICES -d %s' % internalip)
        logger.exe('sudo /usr/share/dse-demos/portfolio_manager/bin/pricer -o UPDATE_PORTFOLIOS -d %s' % internalip)
        logger.exe('sudo /usr/share/dse-demos/portfolio_manager/bin/pricer -o INSERT_HISTORICAL_PRICES -n 100 -d %s' % internalip)

def emailReport(subject, message):
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg.attach(MIMEText(message))

    msg = msg.as_string().replace('yes: write error','yes: write nrror')

    # The actual mail send
    server = smtplib.SMTP(smtp + ':' + port)
    server.starttls()
    server.login(username,password)
    server.sendmail(username, username, msg)
    server.quit()

def smokeTest():
    if conf.getConfig("AMI", "SmokeURL") and conf.getConfig("AMI", "SmokeFile") and int(launchindex) == 0:
        smokeURL = conf.getConfig("AMI", "SmokeURL")
        smokeFile = conf.getConfig("AMI", "SmokeFile")

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
        emailReport('SMOKE-TESTS ::: ' + smokeFile + ' ::: ' + publichostname, log)




print '[INFO] Waiting 60 seconds to restart opscenter, setup demos, and possibly send emails...'
time.sleep(60)
req = urllib2.Request('http://instance-data/latest/meta-data/reservation-id')
reservationid = urllib2.urlopen(req).read()

req = urllib2.Request('http://instance-data/latest/meta-data/local-ipv4')
internalip = urllib2.urlopen(req).read()

req = urllib2.Request('http://instance-data/latest/meta-data/public-hostname')
publichostname = urllib2.urlopen(req).read()

req = urllib2.Request('http://instance-data/latest/meta-data/ami-launch-index')
launchindex = int(urllib2.urlopen(req).read())

smtp = None
port = None
username = None
password = None

logger.exe('nodetool -h localhost ring')

if conf.getConfig("AMI", "Email"):
    try:
        rawEmail = conf.getConfig("AMI", "Email")
        read = rawEmail.split(':')

        logger.info("Parsed Email Options: " + str(read))

        smtp = read[0]
        port = read[1]
        username = read[2]
        password = read[3]
    except:
        print "[ERROR] No emails will be sent. Error during parsing."

checkAndLaunchOpsCenter()
setupDemos()

if username and password:
    with open('ami.log', 'r') as f:
        amiLog = f.read()
    emailReport(reservationid + ' ::: ' + internalip + ' ::: ' + publichostname, amiLog)
    smokeTest()

#!/usr/bin/env python
### Script provided by DataStax.

import shlex, subprocess, time, sys, os

# Using this AMI: ami-cef405a7

# And this security group:
# SSH  tcp  22  22  0.0.0.0/0
# Custom  tcp  9160  9160  0.0.0.0/0
# Custom  tcp  7000  7000  0.0.0.0/0

def exe(command):
    process = subprocess.Popen(shlex.split(command))
    process.wait()
    return process

def pipe(command1, command2):
    # Helper function to execute piping commands and print traces of the commands and output for debugging/logging purposes
    p1 = subprocess.Popen(shlex.split(command1), stdout=subprocess.PIPE)
    p2 = subprocess.Popen(shlex.split(command2), stdin=p1.stdout)
    p1.stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
    output = p2.communicate()[0]
    return output

# Setup Repositories
exe('sudo add-apt-repository "deb http://archive.canonical.com/ lucid partner"')
exe('sudo add-apt-repository "deb http://debian.riptano.com/maverick maverick main"')
exe('sudo apt-get -y update')
exe('sudo apt-get -y upgrade')
time.sleep(5)

# Install Java and other recommended tools
exe('sudo apt-get -y install sun-java6-jdk libjna-java htop emacs23-nox sysstat iftop binutils pssh pbzip2 xfsprogs zip unzip ruby openssl libopenssl-ruby curl maven2 ant liblzo2-dev ntp')

# Install these for a much faster instance startup time
exe('sudo apt-get -y install ca-certificates-java icedtea-6-jre-cacao java-common jsvc libavahi-client3 libavahi-common-data libavahi-common3 libcommons-daemon-java libcups2 libjna-java')
exe('sudo apt-get -y install ca-certificates-java default-jre-headless icedtea-6-jre-cacao java-common jsvc libavahi-client3 libavahi-common-data libavahi-common3 libcommons-daemon-java libcups2 libjna-java libjpeg62 liblcms1 libnspr4-0d libnss3-1d openjdk-6-jre-headless openjdk-6-jre-lib tzdata-java jsvc libcommons-daemon-java libjna-java')

# Install RAID setup
exe('sudo apt-get -y --no-install-recommends install mdadm')

# Preinstall Maven packages as a convenience
exe('sudo -u ubuntu mvn install')
time.sleep(5)

# Remove OpenJDK
exe('sudo update-alternatives --set java /usr/lib/jvm/java-6-sun/jre/bin/java')
exe('sudo aptitude remove openjdk-6-jre-headless openjdk-6-jre-lib -y')

# Setup a link to the motd script that is provided in the git repository
fileToOpen = '/home/ubuntu/.profile'
exe('sudo chmod 777 ' + fileToOpen)
with open(fileToOpen, 'a') as f:
    f.write("""
python datastax_ami/ds4_motd.py
export JAVA_HOME=/usr/lib/jvm/java-6-sun
""")
exe('sudo chmod 644 ' + fileToOpen)

os.chdir('/root')
fileToOpen = '.profile'
exe('sudo chmod 777 ' + fileToOpen)
with open(fileToOpen, 'w') as f:
    f.write("""
export JAVA_HOME=/usr/lib/jvm/java-6-sun
""")
exe('sudo chmod 644 ' + fileToOpen)
os.chdir('/home/ubuntu')

# Create init.d script
initscript = """#!/bin/sh

### BEGIN INIT INFO
# Provides:          
# Required-Start:    $remote_fs $syslog
# Required-Stop:     
# Default-Start:     2 3 4 5
# Default-Stop:      
# Short-Description: Start AMI Configurations on boot.
# Description:       Enables AMI Configurations on startup.
### END INIT INFO

# Make sure variables get set
export JAVA_HOME=/usr/lib/jvm/java-6-sun

# Setup system properties
sudo ulimit -n 32768
echo 1 | sudo tee /proc/sys/vm/overcommit_memory

# Clear old ami.log
cd /home/ubuntu/datastax_ami
echo "\n======================================================\n" >> ami.log
echo "\n======================================================\n" >> error.log
python ds0_updater.py 2>> error.log
"""
exe('sudo touch /etc/init.d/start-ami-script.sh')
exe('sudo chmod 777 /etc/init.d/start-ami-script.sh')
with open('/etc/init.d/start-ami-script.sh', 'w') as f:
    f.write(initscript)
exe('sudo chmod 755 /etc/init.d/start-ami-script.sh')

# Setup limits.conf
pipe('echo "* soft nofile 32768"', 'sudo tee -a /etc/security/limits.conf')
pipe('echo "* hard nofile 32768"', 'sudo tee -a /etc/security/limits.conf')

# Setup AMI Script to start on boot
exe('sudo update-rc.d -f start-ami-script.sh start 99 2 3 4 5 .')

# Clear everything on the way out.
exe('sudo rm .ssh/authorized_keys')
subprocess.Popen("sudo rm -rf /etc/ssh/ssh_host_dsa_key*", shell=True)
subprocess.Popen("sudo rm -rf /etc/ssh/ssh_host_key*", shell=True)
subprocess.Popen("sudo rm -rf /etc/ssh/ssh_host_rsa_key*", shell=True)

subprocess.Popen("sudo rm -rf /tmp/*", shell=True)
subprocess.Popen("sudo rm -rf /tmp/.*", shell=True)
exe('rm -rf ~/.bash_history')

sys.exit(0)

# Allow SSH within the ring to be easier (only for private AMIs)
# exe('ssh-keygen')
# exe('cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys')

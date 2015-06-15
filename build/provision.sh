#!/bin/bash

# Enable xtrace for easier debugging. Echoes commands and variables.
set -x

# Exit on error so problems are obvious
set -e

# Collect system facts
OS_VERSION=`lsb_release -sr`
OS_CODENAME=`lsb_release -sc`

# Display environment variables, helpful to discover what variables packer
# defines automatically.
env

# FIXME: Is the hs1.8xlarge boot issue fix in pre_1.sh still needed?

### Install Software ###
# cloud-init updates /etc/apt/sources.list at startup, and the update tends to
# happen *after* ssh is up and breaks apt operations. Wait for it to
# finish. For more details see:
# https://github.com/mitchellh/packer/issues/41#issuecomment-21288589
# https://github.com/mitchellh/packer/issues/41#issuecomment-108001183
while [ ! -f /var/lib/cloud/instance/boot-finished ]; do
    sleep 1;
done

# Force both debconf and ucf to be non-interactive so apt doesn't prompt
APT_GET="apt-get -y -o 'Dpkg::Options::=--force-confdef' -o 'Dpkg::Options::=--force-confnew'"
export DEBIAN_FRONTEND=noninteractive
export UCF_FORCE_CONFFNEW=true

sudo ${APT_GET} dist-upgrade
sudo ${APT_GET} --no-install-recommends install mdadm # ComboAMI dependency
# FIXME: libopenssl-ruby is missing or has changed names, do we need it?
# FIXME: Emacs24? Or just emacs?
PACKAGES=(
    git xfsprogs ntp software-properties-common # ComboAMI dependencies
    libjna-java                                 # Cassandra dependencies
    htop sysstat iftop dstat                    # System monitoring convenience
    subversion maven2 ant make gcc binutils     # Compile Cassandra convenience
    emacs23-nox pssh pbzip2 zip unzip s3cmd     # Handy tools convenience
    curl tree python-pip ethtool
    ruby
    openssl
    liblzo2-dev
)
sudo ${APT_GET} install --fix-missing ${PACKAGES[@]}

### Install Java ###
# Need to do this in a separate apt-get run in order to ensure
# software-properties-common is installed which provides add-apt-repository
#
# For more details see:
# http://www.webupd8.org/2012/01/install-oracle-java-jdk-7-in-ubuntu-via.html
sudo echo oracle-java7-installer shared/accepted-oracle-license-v1-1 select true | sudo /usr/bin/debconf-set-selections
sudo add-apt-repository -y ppa:webupd8team/java
sudo apt-get update
sudo ${APT_GET} install oracle-java7-installer oracle-java7-set-default
sudo update-java-alternatives -s java-7-oracle
export JAVA_HOME=/usr/lib/jvm/java-7-oracle

### Install ec2-ami-tools
# Building instance-store backed images requires running the ec2-ami-tools
# on the instances while it's being built, ensure they're present.
case ${OS_VERSION} in
    12.04)
        # add-apt-repository only gained the ability to understand distribution
        # components like "multiverse" in Ubuntu 12.10. The sed commands look
        # for lines similar to these in sources.list to uncomment:
        # deb http://us-east-1.ec2.archive.ubuntu.com/ubuntu/ precise multiverse
        # deb-src http://us-east-1.ec2.archive.ubuntu.com/ubuntu/ precise multiverse
        # deb http://us-east-1.ec2.archive.ubuntu.com/ubuntu/ precise-updates multiverse
        # deb-src http://us-east-1.ec2.archive.ubuntu.com/ubuntu/ precise-updates multiverse
        sudo sed -i "s/^# \(deb .* precise multiverse\)/\1/" /etc/apt/sources.list
        sudo sed -i "s/^# \(deb-src .* precise multiverse\)/\1/" /etc/apt/sources.list
        sudo sed -i "s/^# \(deb .* precise-updates multiverse\)/\1/" /etc/apt/sources.list
        sudo sed -i "s/^# \(deb-src .* precise-updates multiverse\)/\1/" /etc/apt/sources.list
    ;;
    *)
        sudo add-apt-repository multiverse
    ;;
esac
sudo apt-get update
sudo ${APT_GET} install ec2-ami-tools

### Configure git ###
git config --global color.ui auto
git config --global color.diff auto
git config --global color.status auto

### Clone ComboAMI ###
git clone https://github.com/riptano/ComboAMI.git datastax_ami
cd datastax_ami
# The COMBOAMI_VERSION environment variable is set by packer
# and configured in the provisioner config
git checkout ${COMBOAMI_VERSION}

### Bash Profile ###
# Login message displays status
echo "python datastax_ami/ds4_motd.py" > /home/ubuntu/.profile

# JAVA_HOME and HADOOP_HOME for the ubuntu user
echo "export JAVA_HOME=/usr/lib/jvm/java-7-oracle" >> /home/ubuntu/.profile
echo "export HADOOP_HOME=/usr/share/dse/hadoop" >> /home/ubuntu/.profile
chmod 644 /home/ubuntu/.profile

# JAVA_HOME and HADOOP_HOME for root
sudo bash -c \
    'echo "export JAVA_HOME=/usr/lib/jvm/java-7-oracle" > /root/.profile'
sudo bash -c \
    'echo "export HADOOP_HOME=/usr/share/dse/hadoop" >> /root/.profile'
sudo chown root:root /root/.profile
sudo chmod 644 /root/.profile

### Sysctl ###
sudo bash -c 'echo "vm.max_map_count = 131072 > /etc/sysctl.d/99-cassandra.conf"'

### Limits ###
cat << EOF > /tmp/cassandra-limits.conf
cassandra - memlock unlimited
cassandra - nofile 100000
cassandra - nproc 32768
cassandra - as unlimited
root - memlock unlimited
root - nofile 100000
root - nproc 32768
root - as unlimited
EOF
sudo mv /tmp/cassandra-limits.conf /etc/security/limits.d/cassandra.conf
sudo chown root:root /etc/security/limits.d/cassandra.conf
sudo chmod 644 /etc/security/limits.d/cassandra.conf

### Init Script ###
cat << EOF > /tmp/start-ami-script.sh
#!/bin/sh

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
export JAVA_HOME=/usr/lib/jvm/java-7-oracle

# Setup system properties
echo 1 | sudo tee /proc/sys/vm/overcommit_memory

# Clear old ami.log
echo "\n======================================================\n" >> ami.log
cd /home/ubuntu/datastax_ami
python ds0_updater.py
EOF
sudo mv /tmp/start-ami-script.sh /etc/init.d/start-ami-script.sh
sudo chown root:root /etc/init.d/start-ami-script.sh
sudo chmod 755 /etc/init.d/start-ami-script.sh
sudo update-rc.d -f start-ami-script.sh start 99 2 3 4 5 .

### Clean up ###
# FIXME: Probably most of this isn't needed but dupe the old logic for now
rm -f ${HOME}/.ssh/*
sudo rm -f /etc/ssh/ssh_host_dsa_key*
sudo rm -f /etc/ssh/ssh_host_key*
sudo rm -f /etc/ssh/ssh_host_rsa_key*
sudo rm -rf /tmp/*
sudo sudo apt-get clean
sudo su -c 'history -c'
history -c

### Finished ###
# Print a completion line. Due to 'set -e' at the top of this script, this is
# only displayed if there are no errors.
echo "Provisioning successful."

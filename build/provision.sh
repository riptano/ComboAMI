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
APT_GET="DEBIAN_FRONTEND=noninteractive apt-get -y -q -q -o 'Dpkg::Options::=--force-confdef' -o 'Dpkg::Options::=--force-confnew'"

sudo apt-get -q -q update
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

### Fix HVM Booting Process ###
# Prepare the HVM instance per the AWS documentation at:
# http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/creating-an-ami-instance-store.html
#
# More context from other packerers:
# https://github.com/Lumida/packer/wiki/Building-Ubuntu-12.04-and-14.04-HVM-Instance-Store-AMIs
# https://gist.github.com/darron/ed7b2587a3415773f26a

# Are we an hvm build?
# Packer automatically exposes the name of the builder via the
# $PACKER_BUILD_NAME environment variable. ComboAMI packer configs should
# follow the convention of ending builder-names with their virt-type (-pv or
# -hvm). So we're in an hvm build if our builder looks like: us-east-1-1404-hvm
case ${PACKER_BUILD_NAME} in
    *-hvm)
        # HVM AMI's need to use legacy-grub, not grub2
        sudo ${APT_GET} install grub

        # Again, docs on this are pretty poor but /proc/cmdline on the booted
        # instance used to create the AMI suggests ttyS0 is the right console,
        # not hvc0 which is in menu.lst
        sudo sed -i 's/ro console=hvc0/ro console=ttyS0/' /boot/grub/menu.lst

        # The EFI system partition isn't part of the rootfs, remove it from
        # fstab. Only necessary for 14.04, but this sed command is a noop
        # if the offending line isn't present so can be run on both platforms
        sudo sed -i 's/LABEL=UEFI.*//' /etc/fstab

        # Output some potentially useful debugging information
        sudo lsblk
        sudo file -s /dev/xvda
        cat /proc/cmdline
        grep ^kernel /boot/grub/menu.lst
        cat /etc/fstab
esac

### Install Java ###
# Need to do this in a separate apt-get run in order to ensure
# software-properties-common is installed which provides add-apt-repository
#
# For more details see:
# http://www.webupd8.org/2012/01/install-oracle-java-jdk-7-in-ubuntu-via.html
sudo echo oracle-java7-installer shared/accepted-oracle-license-v1-1 select true | sudo /usr/bin/debconf-set-selections
sudo add-apt-repository -y ppa:webupd8team/java
sudo apt-get -q -q update
sudo ${APT_GET} install oracle-java7-installer oracle-java7-set-default
sudo update-java-alternatives -s java-7-oracle
export JAVA_HOME=/usr/lib/jvm/java-7-oracle

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
sudo su -c 'history -c'
history -c
# Clean up cloud-init boot files, especially the "lock" in
# /var/lib/cloud/instance/boot-finished that we use to check if
# cloud-init is finished on startup.
# I wasn't able to find any documentation on this cleanup process,
# so it's possible I'm missing things or doing things incorrectly.
sudo rm -f /var/lib/cloud/instance
sudo rm -rf /var/lib/cloud/instances/*

### Install ec2-ami-tools
# There are copies of the ami-tools in the Ubuntu repos, but they're old and
# may not support hvm AMI's properly. Download the latest tools from Amazon
# EC2_AMI_TOOLS VERSION and EC2_API_TOOLS_VERSION are set in the packer template
#
# We need these to build the AMI, but don't need them in the final image so
# installing into /tmp is fine. However, if we do that, we have to install after
# cleanup so we don't delete them at the end of provisioning, but before packer
# image-creation.

# Install dependencies
sudo ${APT_GET} install gdisk kpartx

# Download the ami-tools
EC2_AMI_TOOLS_ARCHIVE=ec2-ami-tools-${EC2_AMI_TOOLS_VERSION}.zip
EC2_AMI_TOOLS_DIR=/tmp/ec2-ami-tools-${EC2_AMI_TOOLS_VERSION}
curl http://s3.amazonaws.com/ec2-downloads/${EC2_AMI_TOOLS_ARCHIVE} \
    -o /tmp/${EC2_AMI_TOOLS_ARCHIVE}
unzip -q /tmp/${EC2_AMI_TOOLS_ARCHIVE} -d /tmp/

# Download the api-tools
EC2_API_TOOLS_ARCHIVE=ec2-api-tools-${EC2_API_TOOLS_VERSION}.zip
EC2_API_TOOLS_DIR=/tmp/ec2-api-tools-${EC2_API_TOOLS_VERSION}
curl http://s3.amazonaws.com/ec2-downloads/${EC2_API_TOOLS_ARCHIVE} \
    -o /tmp/${EC2_API_TOOLS_ARCHIVE}
unzip -q /tmp/${EC2_API_TOOLS_ARCHIVE} -d /tmp/

# Install the ami and api tools
mkdir -p /tmp/ec2/bin
mkdir /tmp/ec2/etc
mkdir /tmp/ec2/lib
mv ${EC2_AMI_TOOLS_DIR}/bin/* /tmp/ec2/bin/
mv ${EC2_AMI_TOOLS_DIR}/etc/* /tmp/ec2/etc/
mv ${EC2_AMI_TOOLS_DIR}/lib/* /tmp/ec2/lib/
mv ${EC2_API_TOOLS_DIR}/bin/* /tmp/ec2/bin/
# No etc dir for api-tools
mv ${EC2_API_TOOLS_DIR}/lib/* /tmp/ec2/lib/
export EC2_HOME=/tmp/ec2/bin
export PATH=${PATH}:${EC2_HOME}

# Clean the apt-cache
sudo sudo apt-get clean

### Finished ###
# Print a completion line. Due to 'set -e' at the top of this script, this is
# only displayed if there are no errors.
echo "Provisioning successful."

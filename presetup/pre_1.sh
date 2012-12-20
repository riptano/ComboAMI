# Now using these: http://cloud-images.ubuntu.com/releases/precise/release-20121218/
# Current as of 12/20/2012
### Script provided by DataStax.

if [ ! -f cert-*.pem ];
then
    echo "Cert files not found on machine!"
    exit
fi

# Download and install repo keys
gpg --keyserver pgp.mit.edu --recv-keys 2B5C1B00
gpg --export --armor 2B5C1B00 | sudo apt-key add -
wget -O - http://installer.datastax.com/downloads/ubuntuarchive.repo_key | sudo apt-key add -
wget -O - http://debian.datastax.com/debian/repo_key | sudo apt-key add -

# Prime for Java installation
sudo echo "sun-java6-bin shared/accepted-sun-dlj-v1-1 boolean true" | sudo debconf-set-selections

# Install Git
sudo apt-get -y update
sudo apt-get -y install git

# Git these files on to the server's home directory
git config --global color.ui auto
git config --global color.diff auto
git config --global color.status auto
git clone git://github.com/riptano/ComboAMI.git datastax_ami
cd datastax_ami
git checkout $(head -n 1 presetup/VERSION)

# Install Java
sudo su
wget https://s3.amazonaws.com/ds-java/jdk-6u31-linux-x64.bin
mkdir -p /opt/java/64
mv jdk-6u31-linux-x64.bin /opt/java/64/
cd /opt/java/64
chmod +x jdk*
./jdk*

# Setup java alternatives
exit
sudo update-alternatives --install "/usr/bin/java" "java" "/opt/java/64/jdk1.6.0_31/bin/java" 1
sudo update-alternatives --set java /opt/java/64/jdk1.6.0_31/bin/java
export JAVA_HOME=/opt/java/64/jdk1.6.0_31

# Begin the actual priming
git pull
sudo python presetup/pre_2.py
sudo chown -R ubuntu:ubuntu . 
rm -rf ~/.bash_history 
history -c


# git pull && rm -rf ~/.bash_history && history -c

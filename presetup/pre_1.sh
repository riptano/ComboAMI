# Now using these: http://cloud-images.ubuntu.com/releases/precise/release-20121218/
# Via: http://cloud-images.ubuntu.com/locator/ec2/: "12.04 LTS amd64 ebs|hvm"
# Current as of 2/5/2014
### Script provided by DataStax.

if [ ! -f cert-*.pem ];
then
    echo "Cert files not found on machine!"
    exit
fi

# Update the Kernel to 2.8 for Ubuntu 12.04 LTS (Can remove on 14.04 LTS)
sudo apt-get -y update
sudo apt-get install -y linux-image-generic-lts-raring linux-headers-generic-lts-raring
sudo shutdown -r now

# Download and install repo keys (won't get baked)
# gpg --keyserver hkp://pgp.mit.edu:80 --recv-keys 2B5C1B00
# gpg --export --armor 2B5C1B00 | sudo apt-key add -
# wget -O - http://installer.datastax.com/downloads/ubuntuarchive.repo_key | sudo apt-key add -
# wget -O - http://debian.datastax.com/debian/repo_key | sudo apt-key add -

# Prime for Java installation
sudo echo oracle-java7-installer shared/accepted-oracle-license-v1-1 select true | sudo /usr/bin/debconf-set-selections

# Install Git
sudo apt-get -y install git

# Git these files on to the server's home directory
git config --global color.ui auto
git config --global color.diff auto
git config --global color.status auto
git clone https://github.com/riptano/ComboAMI.git datastax_ami
cd datastax_ami
git checkout $(head -n 1 presetup/VERSION)

# Install Java
# http://www.webupd8.org/2012/01/install-oracle-java-jdk-7-in-ubuntu-via.html
sudo add-apt-repository -y ppa:webupd8team/java
sudo apt-get update
sudo apt-get install -y oracle-java7-installer oracle-java7-set-default

# Setup java alternatives
sudo update-java-alternatives -s java-7-oracle
export JAVA_HOME=/usr/lib/jvm/java-7-oracle

# Begin the actual priming
git pull
sudo python presetup/pre_2.py

# Fix booting issues on hs1.8xlarge
find /lib/modules |grep 'raid[456]' | sudo xargs -i rm -rf {} && sudo depmod -a
sudo update-initramfs -k all -c
gunzip -c /boot/initrd.img-3.8.0-35-generic | cpio --list | grep raid

sudo chown -R ubuntu:ubuntu . 
rm -rf ~/.bash_history 
history -c


# git pull && rm -rf ~/.bash_history && history -c

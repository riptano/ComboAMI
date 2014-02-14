# Launch AMIs across regions

Use `presetup/launch_amis` to launch AMIs. Copy-paste their strings to copy
cert-*.pem and pk-*.pem files to the instances. Use the ssh strings to ssh in.

# Install codebase

Copy-paste `presetup/pre_1.sh` in small chunks to confirm everything works.

# Baking Script (ebs-backed)

    cd
    sudo chown -R ubuntu:ubuntu datastax_ami

    sudo rm *.pem

    sudo /bin/rm -f /var/cache/apt/archives/*deb
    sudo su
        rm -rf ~/.bash_history
        history -c
        exit
    rm -rf ~/.bash_history && history -c

# Baking Script (instance-stores)

    cd
    sudo chown -R ubuntu:ubuntu datastax_ami

    # Get to the `root` user
    sudo mv *.pem /mnt
    sudo su
    cd

    # Setup EC2 AMI Tools
    curl http://s3.amazonaws.com/aws-dev-support/beta/ec2-ami-tools-1.4.0.10.zip > ec2-ami-tools.zip
    mkdir ec2
    cp ec2-ami-tools.zip ec2
    cd ec2
    unzip ec2-ami-tools.zip
    ln -s ec2-ami-tools-* current
    echo "export EC2_AMITOOL_HOME=~/ec2/current" > ~/.bashrc
    echo "export PATH=${PATH}:~/ec2/current/bin" >> ~/.bashrc
    source ~/.bashrc

    # Should error out, but still run
    ec2-bundle-vol -help


    # Setup credentials
    # AWSID as found here: https://portal.aws.amazon.com/gp/aws/manageYourAccount. Example: xxxx-xxxx-xxxx
    AWSID=<YOUR INFORMATION GOES HERE>
    ACCESSKEYID=<YOUR INFORMATION GOES HERE>
    SECRETACCESSKEY=<YOUR INFORMATION GOES HERE>
    CERT_PEM=/mnt/cert-*.pem
    PK_PEM=/mnt/pk-*.pem

    # Setup MetaData
    VERSION=$(head -1 /home/ubuntu/datastax_ami/presetup/VERSION)
    AMINAME=datastax_clustering_ami_${VERSION}_pv
    S3BUCKET=datastax
    AMITITLE="DataStax Auto-Clustering AMI $VERSION"
    DESCRIPTION='"Provides a way to automatically launch a configurable DataStax Enterprise or DataStax Community cluster by simply starting a group of instances."'
    MANIFEST=/mnt/$AMINAME.manifest.xml

    /bin/rm -f /var/cache/apt/archives/*deb


    # Bundle PV instances
    rm -rf ~/.bash_history && history -c && ec2-bundle-vol -p $AMINAME -d /mnt -k $PK_PEM -c $CERT_PEM -u $AWSID -r x86_64

    # Bundle HVM instances
    sudo apt-get install -y gdisk kpartx grub
    /bin/rm -f /var/cache/apt/archives/*deb

    AMINAME=datastax_clustering_ami_${VERSION}_hvm
    MANIFEST=/mnt/$AMINAME.manifest.xml
    sed -i 's;ro console=hvc0;ro console=ttyS0 xen_emul_unplug=unnecessary;' /boot/grub/menu.lst
    rm -rf ~/.bash_history && history -c && ec2-bundle-vol -p $AMINAME -d /mnt -k $PK_PEM -c $CERT_PEM -u $AWSID -r x86_64 -P mbr


    REGION=US;              yes | ec2-upload-bundle -m $MANIFEST -a $ACCESSKEYID -s $SECRETACCESSKEY -b $S3BUCKET-us-east-1 --location $REGION
    REGION=us-west-1;       yes | ec2-upload-bundle -m $MANIFEST -a $ACCESSKEYID -s $SECRETACCESSKEY -b $S3BUCKET-$REGION --location $REGION
    REGION=us-west-2;       yes | ec2-upload-bundle -m $MANIFEST -a $ACCESSKEYID -s $SECRETACCESSKEY -b $S3BUCKET-$REGION --location $REGION
    REGION=EU;              yes | ec2-upload-bundle -m $MANIFEST -a $ACCESSKEYID -s $SECRETACCESSKEY -b $S3BUCKET-eu-west-1 --location $REGION
    REGION=ap-southeast-1;  yes | ec2-upload-bundle -m $MANIFEST -a $ACCESSKEYID -s $SECRETACCESSKEY -b $S3BUCKET-$REGION --location $REGION
    REGION=ap-southeast-2;  yes | ec2-upload-bundle -m $MANIFEST -a $ACCESSKEYID -s $SECRETACCESSKEY -b $S3BUCKET-$REGION --location $REGION
    REGION=ap-northeast-1;  yes | ec2-upload-bundle -m $MANIFEST -a $ACCESSKEYID -s $SECRETACCESSKEY -b $S3BUCKET-$REGION --location $REGION
    REGION=sa-east-1;       yes | ec2-upload-bundle -m $MANIFEST -a $ACCESSKEYID -s $SECRETACCESSKEY -b $S3BUCKET-$REGION --location $REGION

    echo """
    cd ~/.ec2/

    # Register PV instances
    ec2-register $S3BUCKET-us-east-1/$AMINAME.manifest.xml -region us-east-1 -n '"$AMITITLE"-pv' -d $DESCRIPTION
    ec2-register $S3BUCKET-us-west-1/$AMINAME.manifest.xml -region us-west-1 -n '"$AMITITLE"-pv' -d $DESCRIPTION
    ec2-register $S3BUCKET-us-west-2/$AMINAME.manifest.xml -region us-west-2 -n '"$AMITITLE"-pv' -d $DESCRIPTION
    ec2-register $S3BUCKET-eu-west-1/$AMINAME.manifest.xml -region eu-west-1 -n '"$AMITITLE"-pv' -d $DESCRIPTION
    ec2-register $S3BUCKET-ap-southeast-1/$AMINAME.manifest.xml -region ap-southeast-1 -n '"$AMITITLE"-pv' -d $DESCRIPTION
    ec2-register $S3BUCKET-ap-southeast-2/$AMINAME.manifest.xml -region ap-southeast-2 -n '"$AMITITLE"-pv' -d $DESCRIPTION
    ec2-register $S3BUCKET-ap-northeast-1/$AMINAME.manifest.xml -region ap-northeast-1 -n '"$AMITITLE"-pv' -d $DESCRIPTION
    ec2-register $S3BUCKET-sa-east-1/$AMINAME.manifest.xml -region sa-east-1 -n '"$AMITITLE"-pv' -d $DESCRIPTION

    # Register HVM instances (add --sriov simple once Enhanced Networking works)
    ec2-register $S3BUCKET-us-east-1/$AMINAME.manifest.xml -region us-east-1 -n '"$AMITITLE"-hvm' -d $DESCRIPTION --virtualization-type hvm
    ec2-register $S3BUCKET-us-west-1/$AMINAME.manifest.xml -region us-west-1 -n '"$AMITITLE"-hvm' -d $DESCRIPTION --virtualization-type hvm
    ec2-register $S3BUCKET-us-west-2/$AMINAME.manifest.xml -region us-west-2 -n '"$AMITITLE"-hvm' -d $DESCRIPTION --virtualization-type hvm
    ec2-register $S3BUCKET-eu-west-1/$AMINAME.manifest.xml -region eu-west-1 -n '"$AMITITLE"-hvm' -d $DESCRIPTION --virtualization-type hvm
    ec2-register $S3BUCKET-ap-southeast-1/$AMINAME.manifest.xml -region ap-southeast-1 -n '"$AMITITLE"-hvm' -d $DESCRIPTION --virtualization-type hvm
    ec2-register $S3BUCKET-ap-southeast-2/$AMINAME.manifest.xml -region ap-southeast-2 -n '"$AMITITLE"-hvm' -d $DESCRIPTION --virtualization-type hvm
    ec2-register $S3BUCKET-ap-northeast-1/$AMINAME.manifest.xml -region ap-northeast-1 -n '"$AMITITLE"-hvm' -d $DESCRIPTION --virtualization-type hvm
    ec2-register $S3BUCKET-sa-east-1/$AMINAME.manifest.xml -region sa-east-1 -n '"$AMITITLE"-hvm' -d $DESCRIPTION --virtualization-type hvm

    # Duplicate this line and change to add internal-only permissions
    ec2-modify-image-attribute -l -region us-east-1 -a EMPLOYEEAWSID \$(ec2-describe-images -region us-east-1 | grep '"$AMITITLE"' | cut -f2)

    """ && rm -rf ~/.bash_history && history -c

# Setup ec2tools on your machine

    cd
    wget http://s3.amazonaws.com/ec2-downloads/ec2-api-tools.zip
    unzip ec2-api-tools.zip
    mv ec2-api-tools-*/bin ec2-api-tools-*/lib .ec2
    rm -rf ec2-api-tools-*
    cd .ec2
    open .

Setup these exports in `~/.profile`.

    # Setup Amazon EC2 Command-Line Tools
    export EC2_HOME=~/.ec2
    export PATH=$PATH:$EC2_HOME/bin
    export EC2_PRIVATE_KEY=`ls $EC2_HOME/pk-*.pem`
    export EC2_CERT=`ls $EC2_HOME/cert-*.pem`
    # For OSX
    export JAVA_HOME=/System/Library/Frameworks/JavaVM.framework/Home/

Now run the echo portions of the Baking Script above to register the AMIs.
Then, just make the images public.

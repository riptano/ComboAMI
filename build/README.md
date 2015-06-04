# Introduction
It's periodically necessary to create fresh ComboAMI images. This is necessary
to support new regions, deliver features that require changes to the update
script, or to ship up-to-date versions of operating system software. It can also
be useful for folks that want to customize the AMI for any reason.

Packer is used to perform AMI creation, and replaces the "presetup" code
previously used for AMI creation.

# Prerequisites
* Install packer on your workstation:
  https://www.packer.io/intro/getting-started/setup.html
* Install json_pp on your workstation: It ships with perl and is installed
  by default in MacOSX and most linuxes. This is used to strip comments from
  packer's json configs, many other javascript preprocessors can serve the same
  function.
* An AWS account: Packer will launch instances, provision them, and register
  images in this AMI account.
* Copy local-default.json to local.json and customize its contents.
** You'll need to know your AWS account id:
   http://docs.aws.amazon.com/IAM/latest/UserGuide/AccountAlias.html
   Official images are published via the AWS account id 056342137115.
** You'll need an access key id and secret access key:
   http://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSGettingStartedGuide/AWSCredentials.html
** You'll need an X.509 certificate to sign the AMI (if you're on the core-team
   you may lack AWS permissions to manage your own certificates, talk to another
   core-team member about getting a signing cert):
   http://docs.aws.amazon.com/AWSEC2/latest/CommandLineReference/ec2-cli-managing-certs.html

# Usage

WARNING: Inspect and understand the packer json configs before you execute them.
The configs used to publish the official images launch instances in every region
and save many AMI's. You WILL incur AWS usage fees.

./gopackgo.sh comboami-test.json

# Notes
* When updating base images, refer to this list of official Ubuntu AMI's to find
  the latest upstream AMI's:
  http://cloud-images.ubuntu.com/locator/ec2/
* Creating images backed by instance-stores is more complicated than creating
  ebs-backed images. See the AWS docs for details:
  http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/creating-an-ami-instance-store.html

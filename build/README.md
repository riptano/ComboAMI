# Introduction
It's periodically necessary to create fresh ComboAMI images. This is necessary
to support new regions, deliver features that require changes to the update
script, or to ship up-to-date versions of operating system software. It can also
be useful for folks that want to customize the AMI for any reason.

Packer is used to perform AMI creation, and replaces the "presetup" code
previously used for AMI creation.

# Usage and Examples

**WARNING: Inspect and understand the packer json configs before you execute them.
The configs used to publish the official images launch instances in every region
and save many AMI's. You WILL incur AWS usage fees.**

The simplest way to kick off a build is using the gopackgo.sh script.

Build private ebs-backed AMI's for testing:
`./gopackgo.sh test-ebs.json`

Build private instance-store-backed AMI's for testing:
`./gopackgo.sh test-instance.json`

Build in all regions:
`./gopackgo.sh publish-official-images`

Build in all regions but disable parallelism, which is useful for troubleshooting:
`./gopackgo.sh publish-official-images -parallel=false`

Build in all regions, pausing after every step, which can be both useful and tedious:
`./gopackgo.sh publish-official-images -debug`

Build in a single AMI using the official config:
`./gopackgo.sh publish-official-images -only us-east-1-1404-pv`

# Cleanup
Packer builds images, but does nothing to manage their lifecycle after that.
After a debugging session, make sure to clean up anything you don't intend
to keep.

* AMI's: Deregister them in the AWS control panel in the EC2 section.
* EBS Snapshots and Volumes: If you're building ebs-backed AMI's, they'll
  have snapshots and/or volumes associated with them. Delete them in the
  AWS control panel in the EC2 section.
* S3 buckets: If you're building instance-backed AMI's (including the official
  images), they'll have snapshots associated with them. Snapshots should all
  be prefixed with a unix epoch timestamp, so identifying the ones you've
  created shouldn't be difficult. Deleting these from the console is tedious
  use s3cmd: http://s3tools.org/kb/item5.htm (s3cmd --configure will walk you
  through one-time setup of s3cmd)

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
  * You'll need to know your AWS account id:
    http://docs.aws.amazon.com/IAM/latest/UserGuide/AccountAlias.html
    Official images are published via the AWS account id 056342137115.
  * You'll need an access key id and secret access key:
    http://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSGettingStartedGuide/AWSCredentials.html
  * You'll need an X.509 certificate to sign the AMI (if you're on the core-team
    you may lack AWS permissions to manage your own certificates, talk to another
    core-team member about getting a signing cert):
    http://docs.aws.amazon.com/AWSEC2/latest/CommandLineReference/ec2-cli-managing-certs.html

# Background
* Packer is used to build the AMI's. It's documentation is available at:
  https://www.packer.io/docs
* Multiple packer json config files are checked into the repository
  * test-ebs.json - A test-config that builds 2 ebs AMI's in us-east-1. Although
    ship instance-store backed AMI's in order to provide the best performance,
    ebs AMI's build more quickly and the build process is much simpler, making
    them handy for testing.
  * test-instance.json - A test-config that builds 2 instance-store backed AMI's
    in us-east-1. The process of building an instance store has many moving
    parts, and requires running
  * official-image-config.py - The packer templating language is great, but it's
    very verbose and not quite flexible enough for our build. This is a
    script contains config-data and a few helper functions that output a plain
    json configuration for packer, while giving us the full power of python for
    our templating needs.

# Notes
* When updating base images, refer to this list of official Ubuntu AMI's to find
  the latest upstream AMI's:
  http://cloud-images.ubuntu.com/locator/ec2/
* Creating images backed by instance-stores is more complicated than creating
  ebs-backed images. See the AWS docs for details:
  http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/creating-an-ami-instance-store.html

# Official AMI Checklist

When publishing the official AMI's follow this checklist:
1. Create a git tag 2.6-beta1 or 2.6.0 and push it to Github: `git tag 2.6-beta1; git push --tags`
2. Update official-image-config.py:
   1. Set COMBOAMI_VERSION to the newly created tag.
   2. Set AMI_PERMISSIONS FIXME
3. ./gopackgo.sh public-official-images
4. Update ../ami_ids.json

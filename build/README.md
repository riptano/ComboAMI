# Introduction
It's periodically necessary to create fresh versions of ComboAMI. This is
necessary to support new regions, deliver features that require changes to
the update script, or to ship up-to-date versions of operating system software.
It can also be useful for folks that want to customize the AMI for any reason.

Packer is used to perform AMI creation, and replaces the "presetup" code
previously used for AMI creation.

# Prerequisites
* Packer: https://www.packer.io/intro/getting-started/setup.html
* An AWS account: Note the default packer config launches instances in every
  region and saves many ami's, and will resource in AWS usage fees.

# Usage
```shell
packer build -var "aws_access_key=exampleid" -var "aws_secret_key=examplekey" comboami-test.json
```

# Notes
* When updating base images, refer to this list of official Ubuntu AMI's:
  http://cloud-images.ubuntu.com/locator/ec2/

# TODO
* Add comment to packer json and document stripping them with a minifier.
* Move from ebs to instance storage
* Set block_device_mappings (I don't think we need launch_block_device_mappings)

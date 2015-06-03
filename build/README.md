# Introduction
It's periodically necessary to create fresh ComboAMI images. This is necessary
to support new regions, deliver features that require changes to the update
script, or to ship up-to-date versions of operating system software. It can also
be useful for folks that want to customize the AMI for any reason.

Packer is used to perform AMI creation, and replaces the "presetup" code
previously used for AMI creation.

# Prerequisites
* An AWS account: Note the default packer config launches instances in every
  region and saves many ami's, and will resource in AWS usage fees.
* Install packer on your workstation:
  https://www.packer.io/intro/getting-started/setup.html
* Install json_pp on your workstation: It ships with perl and is installed
  by default in MacOSX and most linuxes. This is used to strip comments from
  packer's json configs, many other javascript preprocessors can serve the same
  function.

# Usage

## Strip JSON Comments
The JSON files used to configure packer have a lot going on in them. In order
to improve readability I've included comments that packer cannot process
directly.  Use json_pp or another javascript pre-processor to strip the comments
out:

```shell
cat comboami-test.json | json_pp > config.json
```

## Run the Packer Build
This will:
* Spin up several
```shell
packer build -var "aws_access_key=exampleid" -var "aws_secret_key=examplekey" config.json
```

# Notes
* When updating base images, refer to this list of official Ubuntu AMI's:
  http://cloud-images.ubuntu.com/locator/ec2/

# TODO
* Move from ebs to instance storage
* Set block_device_mappings (I don't think we need launch_block_device_mappings)

#!/usr/bin/python
import time
import calendar
import json

# The packer config templating language is nice, but when dealing with
# many ami-builders like we have there's a lot of repetition. The
# format is so verbose that it can be hard to follow, and there's lots
# of room for copy pasta errors. This script and its embedded configs
# output a valid JSON config for packer that can be used to build and
# public the official ComboAMI images to all supported regions.
#
# It's core is the builder_builder() function which accepts a concise list of
# params that are tailored to our use-case and outputs a full builder config.

COMBOAMI_VERSION = "2.6-beta1"
AMI_LIST = [
    # Don't use periods in the os_version. One of the places it's used is in
    # constructing s3 bucket names, which are then references via https,
    # and extra dots invalidate the hostname/certificate-validation scheme
    # used by S3.

    ### ap-northeast-1 ###
    {"region": "ap-northeast-1", "os_version": "12_04", "upstream_ami": "ami-f0f82ff0", "virt_type": "paravirtual"},
    {"region": "ap-northeast-1", "os_version": "12_04", "upstream_ami": "ami-b8e334b8", "virt_type": "hvm"},
    {"region": "ap-northeast-1", "os_version": "14_04", "upstream_ami": "ami-62b86462", "virt_type": "paravirtual"},
    {"region": "ap-northeast-1", "os_version": "14_04", "upstream_ami": "ami-eeb66aee", "virt_type": "hvm"},
    ### ap-southeast-1 ###
    {"region": "ap-southeast-1", "os_version": "12_04", "upstream_ami": "ami-7091a822", "virt_type": "paravirtual"},
    {"region": "ap-southeast-1", "os_version": "12_04", "upstream_ami": "ami-c690a994", "virt_type": "hvm"},
    {"region": "ap-southeast-1", "os_version": "14_04", "upstream_ami": "ami-a89ba0fa", "virt_type": "paravirtual"},
    {"region": "ap-southeast-1", "os_version": "14_04", "upstream_ami": "ami-9c99a2ce", "virt_type": "hvm"},
    ### ap-southeast-2 ###
    {"region": "ap-southeast-2", "os_version": "12_04", "upstream_ami": "ami-110e772b", "virt_type": "paravirtual"},
    {"region": "ap-southeast-2", "os_version": "12_04", "upstream_ami": "ami-a3017899", "virt_type": "hvm"},
    {"region": "ap-southeast-2", "os_version": "14_04", "upstream_ami": "ami-c19be3fb", "virt_type": "paravirtual"},
    {"region": "ap-southeast-2", "os_version": "14_04", "upstream_ami": "ami-259ae21f", "virt_type": "hvm"},
    # Packer 0.7.5 doesn't support cn-nort-1 or eu-central-1.
    # See for details: https://github.com/riptano/ComboAMI/issues/62
    ### cn-north-1 ###
    # {"region": "cn-north-1", "os_version": "12_04", "upstream_ami": "ami-32ef720b", "virt_type": "paravirtual"},
    # {"region": "cn-north-1", "os_version": "12_04", "upstream_ami": "ami-14ef722d", "virt_type": "hvm"},
    # {"region": "cn-north-1", "os_version": "14_04", "upstream_ami": "ami-08930e31", "virt_type": "paravirtual"},
    # {"region": "cn-north-1", "os_version": "14_04", "upstream_ami": "ami-7a930e43", "virt_type": "hvm"},
    ### eu-central-1 ###
    # {"region": "eu-central-1", "os_version": "12_04", "upstream_ami": "ami-78b38d65", "virt_type": "paravirtual"},
    # {"region": "eu-central-1", "os_version": "12_04", "upstream_ami": "ami-5cb08e41", "virt_type": "hvm"},
    # {"region": "eu-central-1", "os_version": "14_04", "upstream_ami": "ami-a4e1d8b9", "virt_type": "paravirtual"},
    # {"region": "eu-central-1", "os_version": "14_04", "upstream_ami": "ami-b6eed7ab", "virt_type": "hvm"},
    ### eu-west-1 ###
    {"region": "eu-west-1", "os_version": "12_04", "upstream_ami": "ami-7beb9d0c", "virt_type": "paravirtual"},
    {"region": "eu-west-1", "os_version": "12_04", "upstream_ami": "ami-73d6a004", "virt_type": "hvm"},
    {"region": "eu-west-1", "os_version": "14_04", "upstream_ami": "ami-47e09d30", "virt_type": "paravirtual"},
    {"region": "eu-west-1", "os_version": "14_04", "upstream_ami": "ami-9bdda0ec", "virt_type": "hvm"},
    ### sa-east-1 ###
    {"region": "sa-east-1", "os_version": "12_04", "upstream_ami": "ami-2bc24336", "virt_type": "paravirtual"},
    {"region": "sa-east-1", "os_version": "12_04", "upstream_ami": "ami-67c5447a", "virt_type": "hvm"},
    {"region": "sa-east-1", "os_version": "14_04", "upstream_ami": "ami-c99414d4", "virt_type": "paravirtual"},
    {"region": "sa-east-1", "os_version": "14_04", "upstream_ami": "ami-e99717f4", "virt_type": "hvm"},
    ### us-east-1 ###
    {"region": "us-east-1", "os_version": "12_04", "upstream_ami": "ami-2aa0ba42", "virt_type": "paravirtual"},
    {"region": "us-east-1", "os_version": "12_04", "upstream_ami": "ami-0aa8b262", "virt_type": "hvm"},
    {"region": "us-east-1", "os_version": "14_04", "upstream_ami": "ami-c51df2ae", "virt_type": "paravirtual"},
    {"region": "us-east-1", "os_version": "14_04", "upstream_ami": "ami-eb6b8480", "virt_type": "hvm"},
    ### us-west-1 ###
    {"region": "us-west-1", "os_version": "12_04", "upstream_ami": "ami-7d997139", "virt_type": "paravirtual"},
    {"region": "us-west-1", "os_version": "12_04", "upstream_ami": "ami-c99b738d", "virt_type": "hvm"},
    {"region": "us-west-1", "os_version": "14_04", "upstream_ami": "ami-1559b251", "virt_type": "paravirtual"},
    {"region": "us-west-1", "os_version": "14_04", "upstream_ami": "ami-6f5fb42b", "virt_type": "hvm"},
    ### us-west-2 ###
    {"region": "us-west-2", "os_version": "12_04", "upstream_ami": "ami-c36b57f3", "virt_type": "paravirtual"},
    {"region": "us-west-2", "os_version": "12_04", "upstream_ami": "ami-5f615d6f", "virt_type": "hvm"},
    {"region": "us-west-2", "os_version": "14_04", "upstream_ami": "ami-636a5353", "virt_type": "paravirtual"},
    {"region": "us-west-2", "os_version": "14_04", "upstream_ami": "ami-916e57a1", "virt_type": "hvm"}
]

packer_variables = {
    # The following are overridden during the packer build process by
    # local.json, but must also be defined in the main template.
    "aws_access_key": "",
    "aws_secret_key": "",
    "aws_account_id": "",
    "aws_signing_cert": "",
    "aws_signing_key": "",

    "launch_size": "m3.medium",
    "ssh_user": "ubuntu"
    }

packer_provisioners = [
    {
        "type": "shell",
        "script": "provision.sh",
        "environment_vars": ["COMBOAMI_VERSION=%s" % COMBOAMI_VERSION]
    }
]


def builder_builder(region, os_version, upstream_ami, virt_type):
    """Returns a dictionary representing a packer builder config for an ami"""
    AMI_BASE_NAME = "DataStax Auto-Clustering AMI"
    AMI_BASE_DESC = ("Launch a DataStax Enterprise or DataStax Community "
                     "cluster (https://github.com/riptano/ComboAMI).")

    if virt_type == "paravirtual":
        SHORT_VIRT_TYPE = "pv"
    else:
        SHORT_VIRT_TYPE = virt_type

    # UTC seconds since the epoch
    now = calendar.timegm(time.gmtime())
    return {
        "ami_name": "%s %s-%s-%s" % (AMI_BASE_NAME, COMBOAMI_VERSION,
                                     os_version, SHORT_VIRT_TYPE),
        # This is the name for the packer builder, which must be unique
        # within the list of potentially concurrently running builders
        "name": "%s-%s-%s" % (region, os_version, SHORT_VIRT_TYPE),
        "ami_description": AMI_BASE_DESC,
        "region": region,
        "source_ami": upstream_ami,
        "ami_virtualization_type": virt_type,
        "s3_bucket": "%s-%s-%s-%s" % (now, region, os_version,
                                      SHORT_VIRT_TYPE),

        "enhanced_networking": False,

        "type":                  "amazon-instance",
        "instance_type":         "{{user `launch_size`}}",
        "ssh_username":          "{{user `ssh_user`}}",
        "access_key":            "{{user `aws_access_key`}}",
        "secret_key":            "{{user `aws_secret_key`}}",
        "account_id":            "{{user `aws_account_id`}}",
        "x509_cert_path":        "{{user `aws_signing_cert`}}",
        "x509_key_path":         "{{user `aws_signing_key`}}",
        # Note that the packer template variables used in the bundle_* commands
        # Are builder-scoped, so this can't be extracted into a packer
        # user-variable.
        #
        # A custom bundle_vol_command is required for 12.04 because the
        # version of ec2-ami-tools available doesn't support the
        # --no-filter flag. We don't need that flag. It prevents the
        # filtering of sensitive file-types like ssh keys which is a feature
        # that we don't need since we know our build process doesn't include
        # sensitive information.  Can be safely applied to 14.04 ami's as well,
        # though the version of ec2-ami-tools with 14.04 supports the flag.
        "bundle_vol_command": ("sudo -n ec2-bundle-vol -k {{.KeyPath}} "
                               "-u {{.AccountId}} -c {{.CertPath}} "
                               "-r {{.Architecture}} -e {{.PrivatePath}}/* "
                               "-d {{.Destination}} -p {{.Prefix}} --batch"),
        # A custom bundle_upload_command is required because the versions
        # of the ec2-ami-tools available for Ubuntu 12.04 and 14.04 don't
        # support the --region flag. It's not needed though since we're
        # always uploading from the region we're trying to publish to.
        "bundle_upload_command": ("sudo -n ec2-upload-bundle "
                                  "-b {{.BucketName}} -m {{.ManifestPath}} "
                                  "-a {{.AccessKey}} -s {{.SecretKey}} "
                                  "-d {{.BundleDirectory}} --batch --retry")
    }

packer_builders = [builder_builder(**ami) for ami in AMI_LIST]

packer_config = {
    "variables": packer_variables,
    "provisioners": packer_provisioners,
    "builders": packer_builders
}

if __name__ == "__main__":
    print json.dumps(packer_config)

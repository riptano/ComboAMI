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

# The tag, branch or other commit-ref that will be checked out and baked
# into the AMI
COMBOAMI_VERSION = "2.6-beta8"

# The versions of Amazon AMI and API tools to download and install, used
# for building the instance-store backed AMI's
EC2_AMI_TOOLS_VERSION = "1.5.3"
EC2_API_TOOLS_VERSION= "1.7.4.0"

# All for publicly accessible builds, empty array for private beta builds
# AMI_PERMISSIONS = []
AMI_PERMISSIONS = ["all"]

AMI_LIST = [
    # Both region and os_version and used in the s3 bucket name that the rootfs
    # is uploaded to. S3 buckets have some unusual naming constraints that
    # these fields need to conform to:
    # - No periods. S3 bucket names are used as hostnames in https api-urls.
    #   Extra dots add subdomains and break certificate validation.
    # - No underscores. ec2-upload-bundle fails to create the bucket
    #   with an error of "The specified bucket is not S3 v2 safe" and then
    #   fails to find the non-existing bucket with "InvalidBucketName(400)"

    ### ap-northeast-1 ###
    {"region": "ap-northeast-1", "os_version": "1204", "upstream_ami": "ami-f0f82ff0", "virt_type": "paravirtual"},
    {"region": "ap-northeast-1", "os_version": "1204", "upstream_ami": "ami-b8e334b8", "virt_type": "hvm"},
    {"region": "ap-northeast-1", "os_version": "1404", "upstream_ami": "ami-62b86462", "virt_type": "paravirtual"},
    {"region": "ap-northeast-1", "os_version": "1404", "upstream_ami": "ami-eeb66aee", "virt_type": "hvm"},
    ### ap-southeast-1 ###
    {"region": "ap-southeast-1", "os_version": "1204", "upstream_ami": "ami-7091a822", "virt_type": "paravirtual"},
    {"region": "ap-southeast-1", "os_version": "1204", "upstream_ami": "ami-c690a994", "virt_type": "hvm"},
    {"region": "ap-southeast-1", "os_version": "1404", "upstream_ami": "ami-a89ba0fa", "virt_type": "paravirtual"},
    {"region": "ap-southeast-1", "os_version": "1404", "upstream_ami": "ami-9c99a2ce", "virt_type": "hvm"},
    ### ap-southeast-2 ###
    {"region": "ap-southeast-2", "os_version": "1204", "upstream_ami": "ami-110e772b", "virt_type": "paravirtual"},
    {"region": "ap-southeast-2", "os_version": "1204", "upstream_ami": "ami-a3017899", "virt_type": "hvm"},
    {"region": "ap-southeast-2", "os_version": "1404", "upstream_ami": "ami-37057e0d", "virt_type": "paravirtual"},
    {"region": "ap-southeast-2", "os_version": "1404", "upstream_ami": "ami-fb047fc1", "virt_type": "hvm"},
    # Packer 0.7.5 doesn't support cn-north-1 or eu-central-1.
    # See for details: https://github.com/riptano/ComboAMI/issues/62
    ### cn-north-1 ###
    # {"region": "cn-north-1", "os_version": "1204", "upstream_ami": "ami-32ef720b", "virt_type": "paravirtual"},
    # {"region": "cn-north-1", "os_version": "1204", "upstream_ami": "ami-14ef722d", "virt_type": "hvm"},
    # {"region": "cn-north-1", "os_version": "1404", "upstream_ami": "ami-08930e31", "virt_type": "paravirtual"},
    # {"region": "cn-north-1", "os_version": "1404", "upstream_ami": "ami-7a930e43", "virt_type": "hvm"},
    ### eu-central-1 ###
    # {"region": "eu-central-1", "os_version": "1204", "upstream_ami": "ami-78b38d65", "virt_type": "paravirtual"},
    # {"region": "eu-central-1", "os_version": "1204", "upstream_ami": "ami-5cb08e41", "virt_type": "hvm"},
    # {"region": "eu-central-1", "os_version": "1404", "upstream_ami": "ami-a4e1d8b9", "virt_type": "paravirtual"},
    # {"region": "eu-central-1", "os_version": "1404", "upstream_ami": "ami-b6eed7ab", "virt_type": "hvm"},
    ### eu-west-1 ###
    {"region": "eu-west-1", "os_version": "1204", "upstream_ami": "ami-7beb9d0c", "virt_type": "paravirtual"},
    {"region": "eu-west-1", "os_version": "1204", "upstream_ami": "ami-73d6a004", "virt_type": "hvm"},
    {"region": "eu-west-1", "os_version": "1404", "upstream_ami": "ami-47e09d30", "virt_type": "paravirtual"},
    {"region": "eu-west-1", "os_version": "1404", "upstream_ami": "ami-9bdda0ec", "virt_type": "hvm"},
    ### sa-east-1 ###
    {"region": "sa-east-1", "os_version": "1204", "upstream_ami": "ami-2bc24336", "virt_type": "paravirtual"},
    {"region": "sa-east-1", "os_version": "1204", "upstream_ami": "ami-67c5447a", "virt_type": "hvm"},
    {"region": "sa-east-1", "os_version": "1404", "upstream_ami": "ami-c99414d4", "virt_type": "paravirtual"},
    {"region": "sa-east-1", "os_version": "1404", "upstream_ami": "ami-e99717f4", "virt_type": "hvm"},
    ### us-east-1 ###
    {"region": "us-east-1", "os_version": "1204", "upstream_ami": "ami-2aa0ba42", "virt_type": "paravirtual"},
    {"region": "us-east-1", "os_version": "1204", "upstream_ami": "ami-0aa8b262", "virt_type": "hvm"},
    {"region": "us-east-1", "os_version": "1404", "upstream_ami": "ami-c51df2ae", "virt_type": "paravirtual"},
    {"region": "us-east-1", "os_version": "1404", "upstream_ami": "ami-eb6b8480", "virt_type": "hvm"},
    ### us-west-1 ###
    {"region": "us-west-1", "os_version": "1204", "upstream_ami": "ami-7d997139", "virt_type": "paravirtual"},
    {"region": "us-west-1", "os_version": "1204", "upstream_ami": "ami-c99b738d", "virt_type": "hvm"},
    {"region": "us-west-1", "os_version": "1404", "upstream_ami": "ami-1559b251", "virt_type": "paravirtual"},
    {"region": "us-west-1", "os_version": "1404", "upstream_ami": "ami-6f5fb42b", "virt_type": "hvm"},
    ### us-west-2 ###
    {"region": "us-west-2", "os_version": "1204", "upstream_ami": "ami-c36b57f3", "virt_type": "paravirtual"},
    {"region": "us-west-2", "os_version": "1204", "upstream_ami": "ami-5f615d6f", "virt_type": "hvm"},
    {"region": "us-west-2", "os_version": "1404", "upstream_ami": "ami-636a5353", "virt_type": "paravirtual"},
    {"region": "us-west-2", "os_version": "1404", "upstream_ami": "ami-916e57a1", "virt_type": "hvm"}
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
        "environment_vars": [
            "COMBOAMI_VERSION=%s" % COMBOAMI_VERSION,
            "EC2_AMI_TOOLS_VERSION=%s" % EC2_AMI_TOOLS_VERSION,
            "EC2_API_TOOLS_VERSION=%s" % EC2_API_TOOLS_VERSION
        ]
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

    # Need custom bundle and upload commands in order to set the path
    ec2_cmd_prefix = "sudo -n bash -c 'EC2_HOME=/tmp/ec2/bin "
    ec2_cmd_prefix += "PATH=${EC2_HOME}:${PATH} "
    # Closes the single-quote used to wrap the bash -c command
    ec2_cmd_postfix = "'"

    ec2_bundle_vol_cmd = ec2_cmd_prefix
    ec2_bundle_vol_cmd += "ec2-bundle-vol "
    ec2_bundle_vol_cmd += "-k {{.KeyPath}} "
    ec2_bundle_vol_cmd += "-u {{.AccountId}} "
    ec2_bundle_vol_cmd += "-c {{.CertPath}} "
    ec2_bundle_vol_cmd += "-r {{.Architecture}} "
    ec2_bundle_vol_cmd += "-e {{.PrivatePath}}/* "
    ec2_bundle_vol_cmd += "-d {{.Destination}} "
    ec2_bundle_vol_cmd += "-p {{.Prefix}} "
    # Ubuntu 14.04+ hvm ami's need to be switched from gpt to mbr partitions
    # per: http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/creating-an-ami-instance-store.html
    if virt_type == "hvm" and os_version != '1204':
        ec2_bundle_vol_cmd += "--partition mbr "
    ec2_bundle_vol_cmd += "--batch "
    ec2_bundle_vol_cmd += "--no-filter"
    ec2_bundle_vol_cmd += ec2_cmd_postfix

    ec2_bundle_upload_cmd = ec2_cmd_prefix
    ec2_bundle_upload_cmd += "ec2-upload-bundle "
    ec2_bundle_upload_cmd += "-b {{.BucketName}} "
    ec2_bundle_upload_cmd += "-m {{.ManifestPath}} "
    ec2_bundle_upload_cmd += "-a {{.AccessKey}} "
    ec2_bundle_upload_cmd += "-s {{.SecretKey}} "
    ec2_bundle_upload_cmd += "-d {{.BundleDirectory}} "
    ec2_bundle_upload_cmd += "--batch "
    ec2_bundle_upload_cmd += "--region {{.Region}} "
    ec2_bundle_upload_cmd += "--retry"
    ec2_bundle_upload_cmd += ec2_cmd_postfix

    return {
        "ami_name": "%s %s-%s-%s" % (AMI_BASE_NAME, COMBOAMI_VERSION,
                                     os_version, SHORT_VIRT_TYPE),
        # This is the name for the packer builder, which must be unique
        # within the list of potentially concurrently running builders
        # It should end with the virt-type (-pv or -hvm) because
        # provisioning.sh keys off this string when prepping hvm images
        "name": "%s-%s-%s" % (region, os_version, SHORT_VIRT_TYPE),
        "ami_description": AMI_BASE_DESC,
        "ami_groups": AMI_PERMISSIONS,
        "region": region,
        "source_ami": upstream_ami,
        "ami_virtualization_type": virt_type,
        "s3_bucket": "comboami-%s-%s/%s-%s-%s" % (COMBOAMI_VERSION, region,
                                                  now, os_version,
                                                  SHORT_VIRT_TYPE),
        "bundle_vol_command": ec2_bundle_vol_cmd,
        "bundle_upload_command": ec2_bundle_upload_cmd,

        "enhanced_networking": False,

        "type":                  "amazon-instance",
        "instance_type":         "{{user `launch_size`}}",
        "ssh_username":          "{{user `ssh_user`}}",
        "access_key":            "{{user `aws_access_key`}}",
        "secret_key":            "{{user `aws_secret_key`}}",
        "account_id":            "{{user `aws_account_id`}}",
        "x509_cert_path":        "{{user `aws_signing_cert`}}",
        "x509_key_path":         "{{user `aws_signing_key`}}"
    }

packer_builders = [builder_builder(**ami) for ami in AMI_LIST]

packer_config = {
    "variables": packer_variables,
    "provisioners": packer_provisioners,
    "builders": packer_builders
}

if __name__ == "__main__":
    print json.dumps(packer_config)

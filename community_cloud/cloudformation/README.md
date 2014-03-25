Summary
=======

The template uses an AMI created with the ComboAMI scripts.
It deploys cassandra in a scale group with the max and minimum set to the same size.  
It uses the AWS::StackID for the custom reservation to cause a cluster in multiple AZs to connect.

Limitations
===========

- This will not work for C* deploys that are not using vnodes.  (DSE 4.0 and earlier does not default to use vnodes)
- The reflector as provided does not remember state beyond N minutes, if AWS replaces a dead node, the new node will come back in the scale group, but will not rejoin the cluster if the new node is started beyond the reflector's memory.  You will need to manually update the seed to put it back into the cluster, and also remove the dead node.
- Your cluster (VPC) must be able to interact with sites on the internet to bootstrap the cluster.
- The template does not prompt for all supported parameters. 
- Deploying the DSE will require modifying the template to enable it.  (It is easy to deploy a broken DSE C* with this template)
 
Pre-Reqs
========

You must already have your VPC configured with any security groups and connectivity configured and usable.

You must edit the template file and update the mapping section providing:

  - the AMI that will be used in each region
  - your account ID
  - the subnet-IDs
  - availability zones
  - security groups

Quickstart
==========

Load the cloudformation template launcher, name your cluster, and select the launch template.

Supply the args, use the notes from AMI to supply your needed args.

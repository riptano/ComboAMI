Summary
=======

DataStax's Amazon Machine Image a quick way to test a DataStax Community or
DataStax Enterprise cluster on EC2.


Quickstart
==========

1. Log into the AWS console with your web browser
2. Select the EC2 service
3. Find the [ami-id's](ami_ids.json) for your region. Note that the AMI with
   the name of "DataStax Auto-Clustering AMI" that has no version number
   specified is from the 2.4 series and is deprecated. Select an ami-id from
   from the list in this repo to ensure you're getting the latest fixes.
4. "Launch Instance" -> Community AMI's -> Search for your ami-id -> "Select"
5. Select an instance type (m3.medium is good for low-throughput testing)
6. "Next: Configure Instance Details" -> "Advanced Details" -> add "User Data"
   of "--clustername test-cluster --totalnodes 1 --version community"
7. "Review and Launch" -> "Launch" -> Select keypair
8. SSH to your new cassandra cluster and run `nodetool status`

If you frequently launch scratch clusters, you may be interested in
[cassandralauncher](https://github.com/joaquincasares/cassandralauncher)

For detailed instructions on launching, visit
http://docs.datastax.com/en/latest-dsc-ami


Options
=======

##Basic AMI Switches:

    --clustername <name>
        The name of the Cassandra cluster
        REQUIRED

    --totalnodes <#>
        Cluster size
        REQUIRED

    --version [ community | enterprise ]
        Installs either DataStax Enterprise or
        DataStax Community Edition
        REQUIRED

    --rpcbinding
        Binds the rpc_address to the private IP
        address of the instance
        Default: false, uses 0.0.0.0

##DataStax Enterprise Specific:

    --username <user>
        The username provided during DSE registration
        --password is REQUIRED in order to use this option
        REQUIRED for a DSE installation

    --password <pass>
        The password provided during DSE registration
        --username is REQUIRED in order to use this option
        REQUIRED for a DSE installation

    --analyticsnodes <#>
        Number of analytics nodes that run with Spark
        Note: Uses Hadoop in versions earlier than DSE 4.5
        Default: 0

    --searchnodes <#>
        Number of search nodes that run with Solr
        Default: 0

    --hadoop
        Force Hadoop over Spark on analytics nodes
        Default: false, uses Spark on 4.5+

##Advanced:

    --release <release_version>
        Allows for the installation of a previous DSE version
        Example: 1.0.2
        Default: Ignored

    --cfsreplicationfactor <#>
        The CFS replication factor
        Note: --cfsreplicationfactor must be <= --analyticsnodes
        Default: 1

    --opscenter no
        Disables the installation of OpsCenter on the cluster
        Default: yes

    --reflector <url>
        Allows you to use your own reflector
        Default: http://reflector2.datastax.com/reflector2.php

    --repository <repository>
        Allows you to set a custom repository to pull configuration files from
        Default: none, falls back to repository used to create the AMI
        Examples: https://github.com/riptano/ComboAMI#2.5
                  https://github.com/riptano/ComboAMI#e5e3d41fb5f12461509aa1b6079413b381930d81

    --postscript_url <url>
        Allows you to download and execute a post install custom script
        Default: none

    --base64postscript <base64_encoded_commands>
        Allows you to specify a list of base64 encoded semi-colon/newline separated commands to be executed post installation
        Default: none
        Example: ZWNobyAtbiAiY2FzcyI7IGVjaG8gLW4gImFuZHJhIg== (echo -n "cass"; echo -n "andra")
                 c3VkbyBhcHQtZ2V0IGluc3RhbGwgY29sbGVjdGQ= (sudo apt-get install collectd)

Security Groups
===============

For information on setting up security groups, see the
[Datastax Documentation](http://www.datastax.com/documentation/datastax_enterprise/4.7/datastax_enterprise/install/installAMIsecurity.html)


Contributing
=================

Pull requests are welcome. Consider creating an issue to discus the feature
before doing the development work, or just fork and create a PR based off the
dev-2.6 branch.

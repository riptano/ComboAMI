Summary
=======
DataStax's Amazon Machine Image is the quickest way to get a DataStax
Community or DataStax Enterprise cluster up and running on EC2.


Quickstart
==========

1. Log into the AWS console with your web browser
2. Select the EC2 service
3. Find the [ami-id's](ami_ids.json) for your region.
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


Ports Needed
============

See:

    http://www.datastax.com/documentation/datastax_enterprise/4.5/datastax_enterprise/install/installAMIsecurity.html


Step-by-step
============

Visit http://docs.datastax.com/en/latest-dsc-ami for full installation instructions.


Post-install
============

To stop the service, simply run

    sudo service <cassandra | dse> stop

To start the service again, simply run

    sudo service <cassandra | dse> start


Implementation details
======================

See [FILES.txt](FILES.txt) for a description of how the scripts here configure the
AMI.




Branching details
=================

Feel free to fork off this project and offer any suggestions that you
find along the way.

Also, if you're interested in the whole process: read up on the saving
process here:
http://www.datastax.com/dev/blog/personalizing-your-own-brisk-ami

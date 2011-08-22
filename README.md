Summary
=======
DataStax's Amazon Machine Image is the quickest way to get a Cassandra
or DataStax' Brisk cluster up and running on EC2.

Search for AMIs by using the term: 

    datastax_clustering_ami


Quickstart
==========

Launch the number of instances desired in your cluster with the User
Data field set to

    -s <number of instances being started>


Options
=======

##AMI Command Switches

    -n <name> (or --clustername)
        The name of the Cassandra cluster
        Note: Spaces are not allowed
        REQUIRED for safety

    -s <#> (or --clustersize) 
        Cluster size
        REQUIRED for a balanced, high-performing ring

    -d <version> (or --deployment)
        Options are: 07x, 08x, or brisk.
        Default: 08x

    -e <smtpAddress>:<port>:<email>:<password> (or --email)
        Example: smtp.gmail.com:587:ec2@datastax.com:pa$$word

##OpsCenter Support

    -o <user>:<pass> (or --opscenter)
        Provide username and password provided during 
        the FREE OpsCenter registration

    -p <user>:<pass> (or --paidopscenter)
        Provide username and password provided during 
        the PAID OpsCenter registration

##Brisk Specific

    -v <#> (or --vanillanodes)
        Number of vanilla nodes that only run Cassandra
        -s is REQUIRED in order to use this option
        Default: 0

    -c <#> (--cfsreplication)
        The CFS replication factor
        At least these many non-vanilla nodes REQUIRED
        Default: 0

##Growing the Cluster
    
    -t <token> (or --token)
        Forces this token on the node 

    -z "<seed>,<seed>" (or --seeds)
        Allows a single node to join a cluster
        Note: Spaces are not allowed

    -w 1 (or --thisisvanilla)
        Setting the option with 1 forces the joining 
        node to be a vanilla Cassandra node
        Note: Optional and only for Brisk.


Ports Needed
============

    Public Facing:
        Cassandra:
            9160: Cassandra client port
            7199: Cassandra JMX port, (8080 in 07x)
        Brisk Specific:
            8012: Hadoop Job Tracker client port
            50030: Hadoop Job Tracker website port
            50060: Hadoop Task Tracker website port
        OpsCenter:
            8888: OpsCenter website port
    Internal:
        Cassandra:
            7000: Cassandra intra-node port
        OpsCenter:
            1024+: OpsCenter intra-node monitoring ports


Step-by-step
============

Visit http://www.datastax.com/ami for
full installation instructions.


Post-install
============

To stop the service, simply run

    sudo service <cassandra | brisk> stop

To start the service again, simply run

    sudo service <cassandra | brisk> start


Implementation details
======================

See FILES.txt for a description of how the scripts here configure the
AMI.


Branching details
=================

Feel free to fork off this project and offer any suggestions that you
find along the way.

Also, if you're interested in the whole process: read up on the saving
process here:
http://www.datastax.com/dev/blog/personalizing-your-own-brisk-ami

Summary
=======
DataStax's Amazon Machine Image is the quickest way to get a DataStax
Community or DataStax Enterprise cluster up and running on EC2.

Search for AMIs by using the term: 

    datastax_clustering_ami


Quickstart
==========

Launch the number of instances desired in your cluster with the User
Data field set to

    -n <number of instances being started> -v Community


Options
=======

##Basic AMI Switches:

    -c <name> (or --clustername)
        The name of the Cassandra cluster
        Note: Spaces are not allowed
        REQUIRED for safety

    -n <#> (or --totalnodes) 
        Cluster size
        REQUIRED for a balanced, high-performing ring

    -v [ community | enterprise ] (or --version)
        Installs either DataStax Enterprise or
        DataStax Community Edition
        REQUIRED

##DataStax Enterprise Specific:

    -u <user> (or --username)
        The username provided during DSE registration
        -p is REQUIRED in order to use this option
        REQUIRED for a DSE installation

    -p <pass> (or --password)
        The password provided during DSE registration
        -u is REQUIRED in order to use this option
        REQUIRED for a DSE installation

    -r <#> (or --realtimenodes)
        Number of vanilla nodes that only run Cassandra
        -n is REQUIRED in order to use this option
        Default: 0

    -f <#> (--cfsreplicationfactor)
        The CFS replication factor
        At least these many non-vanilla nodes REQUIRED
        Default: 0

##Advanced:

    -e <smtpAddress>:<port>:<email>:<password> (or --email)
        Sends emails to and from this address for easier
        error collecting
        Example: smtp.gmail.com:587:ec2@datastax.com:pa$$word

    -o no (or --opscenter)
        Disables the installation of OpsCenter on the cluster


Ports Needed
============

    Public Facing:
        Cassandra:
            9160: Cassandra client port
        DataStax Enterprise Specific:
            8012: Hadoop Job Tracker client port
            50030: Hadoop Job Tracker website port
            50060: Hadoop Task Tracker website port
        OpsCenter:
            8888: OpsCenter website port
    Internal:
        Cassandra:
            7000: Cassandra intra-node port
            8983: Portfolio Demo
            61621: OpsCenter agent port
            61622: OpsCenter agent port
        OpsCenter:
            61620: OpsCenter intra-node monitoring ports

Step-by-step
============

Visit http://www.datastax.com/ami for
full installation instructions.


Post-install
============

To stop the service, simply run

    sudo service <cassandra | dse> stop

To start the service again, simply run

    sudo service <cassandra | dse> start


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

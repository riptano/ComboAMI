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
        SSH:
            22: Default SSH port
        Cassandra:
            9160: Cassandra client port
        DataStax Enterprise Specific:
            8012: Hadoop Job Tracker client port
            8983: Portfolio Demo website port
            50030: Hadoop Job Tracker website port
            50060: Hadoop Task Tracker website port
        OpsCenter:
            8888: OpsCenter website port
    Internal:
        Cassandra:
            1024+: JMX reconnections
            7000: Cassandra intra-node port
            7199: Cassandra JMX monitoring port
        DataStax Enterprise Specific:
            9290: Hadoop thrift port
        OpsCenter:
            50031: OpsCenter job tracker proxy
            61620: OpsCenter intra-node monitoring ports
            61621: OpsCenter agent port


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


Upgrading
=========

1. Backup all the data on all your nodes using the snapshot utility. This provides you with the easiest way to revert any unwanted changes or incompatibilies that may arise. See http://www.datastax.com/docs/0.7/operations/scheduled_tasks#backing-up-data for more information.
2. On each of your Cassandra nodes, run `sudo apt-get install [ cassandra | apache-cassandra1 | dse-full ]`, depending on which version you were currently on and want to upgade to.  
    * `cassandra` upgrades to the latest in 0.8.x release.
    * `apache-cassandra` upgrades to the latest in the 1.0.x release.
    * `dse-full` upgrades to the latest DataStax Enterprise release.
    * If you are trying to upgrade across major versions, make sure to read NEWS.txt on the newer packages and consult http://docs.datastax.com for full details for upgrading packaged releases. Typically a new repository must be added followed by a `sudo apt-get update`.
3. Account for New and Changed Parameters in cassandra.yaml. If the default Cassandra configuration file has changed, you will find backups of it in the conf directory. You can use that to compare the two configurations and make appropriate changes.
4. Make sure any client drivers – such as Hector or Pycassa clients – are compatible with your current version.
5. Run nodetool drain to flush the commit log and then restart each Cassandra node, one at a time, monitoring the log files for any issues.
6. After upgrading and restarting all Cassandra nodes, restart client applications.
7. [Upgrading from 0.8 to 1.0] After upgrading, run nodetool scrub against each node before running repair, moving nodes, or adding new ones.


Branching details
=================

Feel free to fork off this project and offer any suggestions that you
find along the way.

Also, if you're interested in the whole process: read up on the saving
process here:
http://www.datastax.com/dev/blog/personalizing-your-own-brisk-ami

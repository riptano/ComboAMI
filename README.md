Summary
=======
DataStax's Amazon Machine Image is the quickest way to get a DataStax
Community or DataStax Enterprise cluster up and running on EC2.


Quickstart
==========

Use `cassandralauncher` as found and documented here: 
https://github.com/joaquincasares/cassandralauncher

This will ensure all options are processed correctly and easily.

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
        Number of analytics nodes that run with Hadoop
        Default: 0

    --searchnodes <#>
        Number of search nodes that run with Solr
        Default: 0

##Advanced:

    --release <release_version>
        Allows for the installation of a previous DSE version
        Example: 1.0.2-1
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


Ports Needed
============

    Public Facing:
        SSH:
            22: Default SSH port
        Cassandra:
            9160: Cassandra client port
        DataStax Enterprise Specific:
            8012: Hadoop Job Tracker client port
            8983: Portfolio Demo and Solr website port
            50030: Hadoop Job Tracker website port
            50060: Hadoop Task Tracker website port
        OpsCenter:
            8888: OpsCenter website port
    Intranode:
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

See [FILES.txt](FILES.txt) for a description of how the scripts here configure the
AMI.


Upgrading
=========

1. Backup all the data on all your nodes using the snapshot utility. This provides you with the easiest way to revert any unwanted changes or incompatibilities that may arise. See the [DataStax documentation](http://www.datastax.com/docs/1.0/operations/backup_restore) for more information.
2. On each of your Cassandra nodes, run `sudo apt-get install [ cassandra | apache-cassandra1 | dse-full ]`, depending on which version you were currently on and want to upgrade to.
    * `cassandra` upgrades to the latest in 0.8.x release.
    * `apache-cassandra` upgrades to the latest in the 1.0.x release.
    * `dse-full` upgrades to the latest DataStax Enterprise release.
    * If you are trying to upgrade across major versions, make sure to read NEWS.txt on the newer packages and consult [DataStax documentation](http://www.datastax.com/docs/datastax_enterprise2.0/upgrading_dse) for full details for upgrading packaged releases. Typically a new repository must be added followed by a `sudo apt-get update`.
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

## Basic AMI Switches:

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

## DataStax Enterprise Specific:

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

## Advanced:

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


## Ports Needed:
    Public Facing:
        SSH:
            22: Default SSH port
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
            9160: Cassandra client port
        DataStax Enterprise Specific:
            9290: Hadoop thrift port
        OpsCenter:
            50031: OpsCenter job tracker proxy
            61620: OpsCenter intra-node monitoring ports
            61621: OpsCenter agent port


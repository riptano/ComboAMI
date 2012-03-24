## Basic AMI Switches:

    --clustername <name>
        The name of the Cassandra cluster
        Note: Spaces are not allowed
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
        -p is REQUIRED in order to use this option
        REQUIRED for a DSE installation

    --password <pass>
        The password provided during DSE registration
        -u is REQUIRED in order to use this option
        REQUIRED for a DSE installation

    --analyticsnodes <#>
        Number of analytics nodes that run with Hadoop
        Default: 0

    --searchnodes <#>
        Number of search nodes that run with Solr
        Default: 0

## Advanced:

    --cfsreplicationfactor <#>
        The CFS replication factor
        At least these many analytics nodes REQUIRED
        Default: 1

    --email <smtpAddress>:<port>:<email>:<password>
        Sends emails to and from this address for easier
        error collecting
        Example: smtp.gmail.com:587:ec2@datastax.com:pa$$word

    --opscenter no
        Disables the installation of OpsCenter on the cluster
        Default: yes

    --heapsize <max_heap_size>,<heap_newsize>
        Sets the Cassandra heapsize as such
        Default: What /etc/dse/cassandra/cassandra-env.sh
        calculates to be the best fit for your instance size

    --reflector <url>
        Allows you to use your own reflector
        Default: http://reflector2.datastax.com/reflector2.php


## Ports Needed:
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


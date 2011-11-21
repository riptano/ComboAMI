Expanding a DataStax AMI Cluster
================================

    1. Start a 1-node cluster.
    2. Login and run: 'sudo service cassandra stop'
    3. Edit /etc/[dse/resources/]cassandra/cassandra.yaml
        * Change your seeds to match the cluster seeds.
        * Change your token to the position you want
            For more info: http://www.datastax.com/support/tokens
    4. Run: sudo rm -rf /raid0/cassandra/* 
        Note: the astrick here is important since you want to keep the cassandra folder and permissions
    5. Run 'sudo service cassandra start'
        Running 'nodetool -h `hostname` ring' should confirm you're up and running.

Tokens
------

You typically want to double a cluster size and you want to calculate based on the ring you want in the end.

Say you have 3 nodes, but want 6, calculate the tokens for a 6 node cluster. The nodes you currently have are 0, 2, and 4 and you'll be adding 1, 3, and 5.

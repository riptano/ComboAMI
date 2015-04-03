#!/usr/bin/env bash

# wait for Cassandra's native transport to start
while :
do
    echo "SELECT bootstrapped FROM system.local;" | cqlsh ${HOST} && break
    sleep 1
done


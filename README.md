Summary
=======
DataStax's Amazon Machine Image is the quickest way to get a Brisk
cluster up and running on EC2.

Search for AMIs by using the term: 

    datastax_brisk_cluster_ami


Quickstart
==========

Launch the number of instances desired in your cluster with the User
Data field set to

    -s <number of instances being started>


Options
=======

    --clustersize <size> (or -s <size>)
      Used by the configuration script to evenly space the Brisk node
      tokens so each machine gets an equal share of data.  If omitted,
      nodes will receive random tokens.

    --vanillanodes <size> (or -v <size>)
      Used by the configuration script to assign the first N nodes to be
      non-task tracker Brisk nodes.

    --cfsreplication <size> (or -c <size>)
      Sets the cfsreplication factor at startup.

    --opscenter <user>:<pass> (or -o <user>:<pass>)
      Installs OpsCenter using the provided username and password recieved
      during OpsCenter registration.
      
      Visit http://www.datastax.com/opscenter for a free registration.

    --paidopscenter <user>:<pass> (or -p <user>:<pass>)
      Installs OpsCenter using the provided username and password recieved
      during OpsCenter registration for paying customers.

    --clustername <name> (or -n <name>)
      Assigns the cluster with a chosen cluster name.


Step-by-step
============

Visit http://www.datastax.com/docs/0.8/brisk/install_brisk_ami for
full installation instructions.


Post-install
============

To stop Brisk, simply run

    ps auwx | grep brisk

and kill the associated PID without

    sudo kill <PID>

To start Brisk again, simply run

    sudo ~/brisk/bin/brisk cassandra -t

for a Brisk node, or

    sudo ~/brisk/bin/brisk cassandra

for a vanilla Cassandra node.

Important note on VM restarts
-----------------------------

EC2 is an unusual environment because a VM will get a different IP if
it reboots.  If you reboot all of your machines, they will contact the
reflector again and reconfigure themselves to be able to talk to each
other again, but if you reboot a single one, it won't be able to rejoin
the others without manual intervention (set the seed in cassandra.yaml
to one of the other nodes).

Adding nodes to the cluster
---------------------------

Adding nodes must currently be done manually (that is, you can create
extra nodes with the same clustername, but you'll have to edit
token, bootstrap setting, and seed manually to get them to join
the existing cluster).  See http://wiki.apache.org/cassandra/Operations
for details.


Implementation details
======================

See FILES.txt for a description of how the scripts here configure the
AMI for Brisk.

Branching details
=================

Feel free to fork off this project and offer any suggestions that you
find along the way.

Also, if you're interested in the whole process: read up on the saving
process here:
http://www.datastax.com/dev/blog/personalizing-your-own-brisk-ami
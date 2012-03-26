Pre-Combo AMI
=============

* A single 0.7.2 AMI
* A single 0.7.4 AMI
* A single 0.7.5 AMI
* A single 0.7.x auto-updating AMI
  * Where the cassandra package would install on launch
* A single 0.8.x auto-updating AMI

Combo AMI
=========

* 1.0
  * A DataStax Brisk/0.8 AMI
* 2.0
  * 0.7.x, 0.8.x, and Brisk on one AMI
* 2.1
  * DataStax Enterprise and DataStax Community
    * Specifically for the DSE/C 1.0 release
    * Added CQL Shell
    * Added Demos
* 2.2
  * DataStax Enterprise 2.0 and DataStax Community 1.0
    * Specifically for the DSE 2.0 release
    * _Completely_ rewritten codebase for easy reading and understanding
    * Solr assignment and integration
    * New tokentool that supports multiple datacenter spacing
    * Removed all short arguments (`-v`) and only long arguments
    are accepted (`--version`)
* Future (as of March 24, 2012)
    * Planned DataStax Enterprise 1.0 support in AMI 2.2
      * Within a week
      * Made possible via the `--release <version>` argument
    * Planned DataStax Community 2.0 support on AMI 2.2
      * After release

CassandraLauncher
=================

Additional features are being incorporated via the CassandraLauncher as found here:
https://github.com/joaquincasares/cassandralauncher

By using the CassandraLauncher, certain aspects are simpler to deploy from a central, non-EC2 location.

The list include:

* DataStax username and password memory
* AWS API key memory
* Instance size memory
* Input validation
* Automated RSA fingerprint checking
* Automatic separate known_hosts file
* Pre-built SSH strings
* Automatic OpsCenter agent installation
* Passwordless SSH around the cluster
* datastax_ssh tool
  * Allows for SSH commands to easily be run across an entire cluster
* Modified hosts file
  * Allows for easy jumping between machines, e.g. c0, c1, a0, a1, s0, ...
* nodelist file
  * An uploaded file onto the cluster for later, possible, use


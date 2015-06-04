#!/bin/bash

set -x
set -e

# Command line arguments
if [ -z ${1} ]; then
    echo "The first argument must be a packer config file."
    exit 1
else
    PACKER_CONF=${1}
    PACKER_CONF_MINIFIED=min-${PACKER_CONF}
fi

# Strip json comments, which packer cannot process
cat $PACKER_CONF | json_pp > ${PACKER_CONF_MINIFIED}

packer validate -var-file=local.json ${PACKER_CONF_MINIFIED}
packer build -var-file=local.json ${PACKER_CONF_MINIFIED}

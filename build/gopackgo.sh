#!/bin/bash

set -x
set -e

# Command line arguments
if [ -z ${1} ]; then
    echo "The first argument must be a packer config file "
    echo "or the string 'publish-official-images'."
    echo "Additional arguments are passed directly to the packer build command."
    exit 1
fi

if [ ${1} = "publish-official-images" ]; then
    shift
    PACKER_CONF=official-image-config.json
    ./official-image-config.py > ${PACKER_CONF}
else
    PACKER_CONF=${1}
fi

# Strip json comments, which packer cannot process
PACKER_CONF_MINIFIED=min-${PACKER_CONF}
cat $PACKER_CONF | json_pp > ${PACKER_CONF_MINIFIED}

# Packer Run
packer validate -var-file=local.json ${PACKER_CONF_MINIFIED}
packer build -var-file=local.json $@ ${PACKER_CONF_MINIFIED}

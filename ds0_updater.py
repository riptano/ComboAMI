#!/usr/bin/env python
# Script provided by DataStax.

# Updating this script requires a rebake of the ami.
#
# The baked version of this script is launched in order to fetch updated ami
# startup code for subsequent phases. Python has already read the baked
# version from disk by the time updates start, with the result that post-bake
# updates to this file are ignored.

import ds0_utils
import logger
import conf

# Update the AMI codebase if it's its first boot
if not conf.get_config("AMI", "CompletedFirstBoot"):
    # check if a specific commit was requested
    force_commit = ds0_utils.required_commit()

    # update the repo
    logger.exe('git pull')

    # ensure any AWS removed repo keys will be put back, if removed on bake
    logger.exe('git reset --hard')

    # force a commit, if requested
    if force_commit:
        logger.exe('git reset --hard %s' % force_commit)

    # ensure the latest commit is signed and verified
    while True:
        logger.exe('gpg --import /home/ubuntu/datastax_ami/repo_keys/DataStax_AMI.7123CDFD.key', expectError=True)
        output = logger.exe('git log --pretty="format:%G?" --show-signature HEAD^..HEAD')

        if "Can't check signature" in output[0]:
            logger.info('gpg keys cleared on startup. Trying again...')
            continue

        rsa_check = 'using RSA key ID 7123CDFD\n'
        signature_check = 'Good signature from "Joaquin Casares (DataStax AMI) <joaquin@datastax.com>"\n'
        if not rsa_check in output[0] or not signature_check in output[0]:
            logger.error('Scripts using a non-signed commit. Please ensure commit is valid.')
            logger.error('    If it was a missed signature, feel free to open a ticket at https://github.com/riptano/ComboAMI.')
        break

# Start AMI start code
try:
    import ds1_launcher
    ds1_launcher.run()
except:
    logger.exception('ds0_updater.py')

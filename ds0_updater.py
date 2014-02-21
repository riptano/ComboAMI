#!/usr/bin/env python
### Script provided by DataStax.

import ds0_utils
import logger
import conf

# Update the AMI codebase if it's its first boot
if not conf.get_config("AMI", "CompletedFirstBoot"):
    force_commit = ds0_utils.required_commit()
    logger.exe('git pull')

    if force_commit:
        logger.exe('git reset --hard %s' % force_commit)

    output = logger.exe('git log --pretty="format:%G?" --show-signature HEAD^..HEAD')
    rsa_check = 'using RSA key ID 7123CDFD\n'
    signature_check = 'Good signature from "Joaquin Casares (DataStax AMI) <joaquin@datastax.com>"\n'
    if not rsa_check in output[0] or not signature_check in output[0]:
        logger.error('Scripts using a non-signed commit. Please ensure commit is valid.')
        logger.error('    If it was a missed signature, feel free to open a ticket at https://github.com/riptano/ComboAMI.')

# Start AMI start code
try:
    import ds1_launcher
    ds1_launcher.run()
except:
    logger.exception('ds0_updater.py')

#!/usr/bin/env python
### Script provided by DataStax.

import ds0_utils
import logger
import conf

# keep it super simple for now because we don't really implement --allowed-keys yet.
def verify_latest_commit():
    allowed_keys = ds0_utils.allowed_keys()

    # ensure the latest commit is signed and verified
    while True:
        for key in allowed_keys:
            logger.exe('gpg --import ' + key['file'], expectError=True)
        output = logger.exe('git log --pretty="format:%G?" --show-signature HEAD^..HEAD')

        if "Can't check signature" in output[0]:
            logger.info('gpg keys cleared on startup. Trying again...')
            continue

        verified = False
        for key in allowed_keys:
            if key['rsa_check'] in output[0] and key['signature_check'] in output[0]:
                verified = True
        if not verified:
            logger.error('Scripts using a non-signed commit. Please ensure commit is valid.')
            logger.error('    If it was a missed signature, feel free to open a ticket at https://github.com/riptano/ComboAMI.')
        break

# Update the AMI codebase if it's its first boot
if not conf.get_config("AMI", "CompletedFirstBoot"):
    # check if a specific commit was requested
    force_commit = ds0_utils.required_commit()

    # update the repo
    repository = ds0_utils.repository()
    logger.exe('git pull ' + repository['origin'] + ' ' + repository['branch'])

    # ensure any AWS removed repo keys will be put back, if removed on bake
    logger.exe('git reset --hard')

    # force a commit, if requested
    if force_commit:
        logger.exe('git reset --hard %s' % force_commit)

    if ds0_utils.disable_commit_verification():
        logger.info('Latest commit verification disabled')
    else:
        verify_latest_commit()

# Start AMI start code
try:
    import ds1_launcher
    ds1_launcher.run()
except:
    logger.exception('ds0_updater.py')

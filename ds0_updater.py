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

# Figure out the argument we should use with git reset.
def get_git_reset_arg(commitish):
    if not commitish:
        return ''

    (commit_id, err) = logger.exe('git rev-parse ' + commitish)
    if err:
        return ''

    # If the commit-ish is a valid commit id, use it as-is.
    # Otherwise, prefix with the remote (always origin).
    if commit_id.strip() == commitish:
       return commit_id
    else:
        return 'origin/' + commitish

# Update the AMI codebase if it's its first boot
if not conf.get_config("AMI", "CompletedFirstBoot"):
    (repository, commitish) = ds0_utils.repository()
    if repository or commitish:
        logger.info('Repository: %s, Commit-ish: %s' % (repository, commitish))

    # Reset the origin if a repository was specified
    if repository:
        logger.exe('git remote remove origin')
        logger.exe('git remote add origin %s' % repository)

    # update the repo
    logger.exe('git fetch')

    # ensure any AWS removed repo keys will be put back, if removed on bake
    logger.exe('git reset --hard %s' % get_git_reset_arg(commitish))

    verify_latest_commit()

# Start AMI start code
try:
    import ds1_launcher
    ds1_launcher.run()
except:
    logger.exception('ds0_updater.py')

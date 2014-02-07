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

# Start AMI start code
try:
    import ds1_launcher
    ds1_launcher.run()
except:
    logger.exception('ds0_updater.py')

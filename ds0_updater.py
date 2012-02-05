#!/usr/bin/env python
### Script provided by DataStax.

import logger
import conf

# Update the AMI codebase if it's its first booot
if not conf.get_config("AMI", "CompletedFirstBoot"):
    logger.exe('git pull')

# Start AMI start code
try:
    import ds1_launcher
    ds1_launcher.run()
except:
    logger.exception('ds0_updater.py')

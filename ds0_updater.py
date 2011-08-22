#!/usr/bin/env python
### Script provided by DataStax.

import os
import logger
import conf

if not conf.getConfig("AMI", "CompletedFirstBoot"):
	logger.exe('git pull')

logger.exe('python ds1_launcher.py', False)

import gzip
import re
import shlex
import StringIO
import sys
import time
import urllib2
import logger

from email.parser import Parser
from argparse import ArgumentParser


def comboami_version():
    return "2.6.3"


def comboami_defaultbranch():
    return "2.6"


def curl_instance_data(url):
    for i in range(20):
        try:
            req = urllib2.Request(url)
            return req
        except urllib2.HTTPError:
            time.sleep(5)
    sys.exit('Couldn\'t curl instance data after 60 seconds')


def read_instance_data(req):
    data = urllib2.urlopen(req).read()
    try:
        stream = StringIO.StringIO(data)
        gzipper = gzip.GzipFile(fileobj=stream)
        return gzipper.read()
    except IOError:
        stream = StringIO.StringIO(data)
        return stream.read()


def is_multipart_mime(data):
    match = re.search('Content-Type: multipart', data)
    if match:
        return True


def get_user_data(req):
    data = read_instance_data(req)
    if is_multipart_mime(data):
        message = Parser().parsestr(data)
        for part in message.walk():
            if (part.get_content_type() == 'text/plaintext'):
                match = re.search('totalnodes', part.get_payload())
                if (match):
                    return part.get_payload()
    else:
        return data


def get_ec2_data():
    instance_data = {}
    # Try to get EC2 User Data
    try:
        req = curl_instance_data('http://169.254.169.254/latest/user-data/')
        instance_data['userdata'] = get_user_data(req)
    except Exception, e:
        instance_data['userdata'] = ''

    return instance_data


def parse_ec2_userdata():
    instance_data = get_ec2_data()

    # Setup parser
    parser = ArgumentParser()

    # Development options
    # Option that specifies repository to use for updating
    parser.add_argument("--repository", action="store", type=str, dest="repository")
    # Option that specifies the commit to use for updating (instead of the latest) -- kept for backwards compatibility
    parser.add_argument("--forcecommit", action="store", type=str, dest="forcecommit")

    try:
        (args, unknown) = parser.parse_known_args(shlex.split(instance_data['userdata']))
        return args
    except:
        return None

# Parse userdata options and return a git repository and commitish
# (a commitish is a string that represents a commit, it could be a branch,
# a tag, a short commit-hash, a long-hash, or anything that git rev-parse
# can handle)
#
# We'll use this to update the git-checkout baked into the AMI to deliver
# dynamic updates on boot
#
# This function is called from ds0_updater.py, and so if it is updated, the
# AMI must be rebaked. See the warning at the top of ds0_updater.py for details
def repository():
    options = parse_ec2_userdata()

    repository = None
    commitish = ''

    if options:
        # User specified a --repository parameter, pull the repo and commitish
        # out of it
        if options.repository:
            parts = options.repository.split('#')
            nparts = len(parts)
            if nparts > 0:
                repository = parts[0]
                if nparts > 1:
                    commitish = parts[1]
        # For backwards compatibility, --forcecommit should allow specifying
        # a commit from the default repository
        elif options.forcecommit:
            # Repository remains set to None in order to use the origin repo of
            # the git-checkout baked into the repo
            commitish = options.forcecommit
        # No special repository or commit parameters were passed, use default
        else:
            # Repository = None, use the baked-in repo
            commitish = comboami_defaultbranch()

    return (repository, commitish)


# Returns a commit-hash that can be passed to git reset
#
# This function is called from ds0_updater.py, and so if it is updated, the
# AMI must be rebaked. See the warning at the top of ds0_updater.py for details
def get_git_reset_arg(commitish):
    if not commitish:
        return ''

    # This will work if the commitish is a remote branch name
    (commit_id, err) = logger.exe('git rev-parse origin/' + commitish)
    if err:
        # This will work if the commitish is a short-hash or long-hash
        (commit_id, err) = logger.exe('git rev-parse ' + commitish)
        if err:
            # Can't figure out what commit is being referenced, return no
            # commit-id and git reset will simply hard reset the workspace
            # using the current commit in the git checkout baked into the AMI
            return ''

    return commit_id

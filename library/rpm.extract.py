#!/usr/bin/python

# Copyright: (c) 2022, Dee'Kej <devel@deekej.io>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: rpm.extract

short_description: Extracts the contents of given rpm

version_added: "1.0.0"

description: This module mimics the same behavior as the 'rpmdev-extract' shell
             script from rpmdevtools (https://pagure.io/rpmdevtools) for RPMs.

options:
    src:
        description: Path to the RPM that should be extracted.
        required: true
        type: str

    dest:
        description:
            - Name of the folder where the RPM should be extracted.
            - By default this corresponds to the RPM name without the '.rpm' suffix.
        required: false
        type: str

    chdir:
        description:
            - Directory to change into where the extraction of RPM should happen.
            - By default this is current working directory.
        requied: false
        type: str

    owner:
        description:
            - Name of the owner for all the extracted files.
            - Set by UNIX's chown utility.
        required: false
        type: str

    group:
        description:
            - Name of the group for all the extracted files.
            - Set by UNIX's chown utility.
        required: false
        type: str

    force:
        description:
            - Runs the RPM extraction even if previously extracted files exist.
            - Useful if the content of RPM changes, but the name stays same.
        required: false
        type: bool

author:
    - Dee'Kej (@deekej)
'''

EXAMPLES = r'''
- name: Extract the contents of RPM file
  rpm.extract:
    src:    ansible-core-2.12.9-1.fc36.noarch.rpm

- name: Extract the contents of RPM file to a different folder
  rpm.extract:
    src:    ansible-core-2.12.9-1.fc36.noarch.rpm
    dest:   ansible-core-extracted

- name: Extract the contents of RPM file in the /tpm folder
  rpm.extract:
    src:    ansible-core-2.12.9-1.fc36.noarch.rpm
    chdir:  /tmp

- name: Extract the contents of RPM file in the /tpm folder & custom folder
  rpm.extract:
    src:    ansible-core-2.12.9-1.fc36.noarch.rpm
    dest:   ansible-core-extracted
    chdir:  /tmp

- name: Extract the contents of RPM file and set different owner/group
  rpm.extract:
    src:    ansible-core-2.12.9-1.fc36.noarch.rpm
    owner:  root
    group:  ansible-automation

- name: Force the extraction of RPM file every time
  rpm.extract:
    src:    ansible-core-2.12.9-1.fc36.noarch.rpm
    dest:   ansible-core-extracted
    force:  true
'''

# =====================================================================

import os
import grp
import pwd
import shutil
from ansible.module_utils.basic import AnsibleModule


def run_module():
    # Ansible Module initialization:
    module_args = dict(
        src=dict(type='str', required=True),
        dest=dict(type='str', required=False, default=None),
        chdir=dict(type='str', required=False, default=None),
        owner=dict(type='str', required=False, default=None),
        group=dict(type='str', required=False, default=None),
        force=dict(type='bool', required=False, default=False)
    )

    # Parsing of Ansible Module arguments:
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    src   = os.path.expanduser(module.params['src'])
    dest  = None
    chdir = None
    owner = module.params['owner']
    group = module.params['group']
    force = module.params['force']

    if module.params['dest']:
        dest  = os.path.expanduser(module.params['dest'])

    if module.params['chdir']:
        chdir = os.path.expanduser(module.params['chdir'])

    result = dict(
        changed=False,
        src = src,
        dest = dest,
        chdir = chdir,
        owner = owner,
        group = group,
        force = force
    )

    # -----------------------------------------------------------------

    # Prepare the destination folder name:
    if not dest:
        dest = os.path.basename(src[:-len(".rpm")])
        result['dest'] = dest

    # Change into the specified directory if needed:
    if chdir:
        os.chdir(chdir)

    # Get current working & result directories:
    cwd = os.getcwd()
    result_dir = os.path.join(cwd, dest)

    # Here we have 3 possible scenarios:
    # 1) Create a new directory if it does not exist...
    # 2) Return back without a change if the folder already exists and
    #    force is set to 'false'...
    # 3) Delete the directory if it exists and force is set to 'true',
    #    then create the directory again...
    #
    # On top of that, we run the check mode first - if needed:
    if module.check_mode:
        if os.path.isdir(dest):
            if force:
                result['changed'] = True
            else:
                result['changed'] = False
        else:
            result['changed'] = True

        module.exit_json(**result)

    if os.path.isdir(dest):
        if force:
            shutil.rmtree(dest, ignore_errors=True)
        else:
            module.exit_json(**result)

    os.mkdir(dest)
    os.chdir(dest)

    # Construct the command to run (same as in rpmdev-extract):
    cmd = "rpm2cpio %s | cpio --quiet --no-absolute-filenames -idumv 2>&1" % src

    shell = os.popen(cmd)
    cmd_output = shell.read()

    # NOTE: close() returns None on successful exit code of cmd.
    if shell.close():
        module.fail_json(msg="failed to extract %s RPM file" % src, **result)

    # Default values for leaving owner/group unchanged with chown():
    uid = -1
    gid = -1

    # Obtain the UID / GID for given owner/group:
    if owner:
        try:
            uid = pwd.getpwnam(owner).pw_uid
        except KeyError:
            module.fail_json(msg="owner '%s' not found in password database" % owner)

    if group:
        try:
            gid = grp.getgrnam(group).gr_gid
        except KeyError:
            module.fail_json(msg="group '%s' not found in group database" % group)

    if owner or group:
        try:
            # NOTE: The 'dirnames' are ignored on purpose. More info:
            # https://stackoverflow.com/a/57458550/3481531
            for dirpath, dirnames, filenames in os.walk(result_dir):
                os.chown(dirpath, uid, gid, follow_symlinks=False)

                for filename in filenames:
                    os.chown(os.path.join(dirpath, filename), uid, gid, follow_symlinks=False)
        except PermissionError:
            module.fail_json(msg="failed to change permissions for path: %s [operation not permitted]" % result_dir)

    result['changed'] = True
    module.exit_json(**result)

# =====================================================================

def main():
    run_module()


if __name__ == '__main__':
    main()

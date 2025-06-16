#!/usr/bin/python
# coding=utf-8
# pylint: disable=I0011,R1734,R1735

#   Copyright 2021 getcarrier.io
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""
    Git tools
"""

import io
import os
import shutil
import getpass
import urllib3

import dulwich  # pylint: disable=E0401
from dulwich import refs, repo, porcelain, client  # pylint: disable=E0401
from dulwich.contrib.paramiko_vendor import ParamikoSSHVendor  # pylint: disable=E0401

import paramiko  # pylint: disable=E0401
import paramiko.transport  # pylint: disable=E0401
from paramiko import SSHException, Message  # pylint: disable=E0401

from . import log


def apply_patches():
    """ Patch dulwich and paramiko """
    # Set USERNAME if needed
    try:
        getpass.getuser()
    except:  # pylint: disable=W0702
        os.environ["USERNAME"] = "git"
    # Patch dulwich to work without valid UID/GID
    repo._get_default_identity = patched_repo_get_default_identity(repo._get_default_identity)  # pylint: disable=W0212
    # Patch dulwich to use paramiko SSH client
    client.get_ssh_vendor = ParamikoSSHVendor
    # Patch paramiko to skip key verification
    paramiko.transport.Transport._verify_key = patched_paramiko_transport_verify_key  # pylint: disable=W0212
    # Patch paramiko to support direct pkey usage
    paramiko.client.SSHClient._auth = patched_paramiko_client_SSHClient_auth(paramiko.client.SSHClient._auth)  # pylint: disable=C0301,W0212
    paramiko.client.SSHClient.__init__ = patched_paramiko_client_SSHClient_init(paramiko.client.SSHClient.__init__)  # pylint: disable=C0301,W0212
    dulwich.client.HttpGitClient.from_parsedurl = patched_dulwich_client_HttpGitClient_from_parsedurl(dulwich.client.HttpGitClient.from_parsedurl)  # pylint: disable=C0301,W0212


def patched_repo_get_default_identity(original_repo_get_default_identity):
    """ Allow to run without valid identity """
    def patched_function():
        try:
            return original_repo_get_default_identity()
        except:  # pylint: disable=W0702
            return ("Git User", "git@localhost")
    return patched_function


def patched_paramiko_transport_verify_key(self, host_key, sig):  # pylint: disable=W0613
    """ Only get key info, no deep verification """
    key = self._key_info[self.host_key_type](Message(host_key))  # pylint: disable=W0212
    if key is None:
        raise SSHException('Unknown host key type')
    # Patched: no more checks are done here
    self.host_key = key


def patched_paramiko_client_SSHClient_init(original_init):  # pylint: disable=C0103,C0116
    def patched_init(self, *args, **kwargs):
        retval = original_init(self, *args, **kwargs)

        ssl_cert_file = os.environ.get("SSL_CERT_FILE")
        if ssl_cert_file:
            self.load_system_host_keys(filename=ssl_cert_file)

        return retval

    return patched_init


def patched_dulwich_client_HttpGitClient_from_parsedurl(original_from_parsedurl):  # pylint: disable=C0103,C0116
    def patched_from_parsedurl(self, *args, config=None, **kwargs):
        ssl_cert_file = os.environ.get("SSL_CERT_FILE")
        if ssl_cert_file and config:
            try:
                config.set(b"http", b"sslCAInfo", ssl_cert_file)
            except:  # pylint: disable=W0702
                from dulwich.config import ConfigDict  # pylint: disable=E0401,C0415
                ssl_config = ConfigDict()
                ssl_config.set(b"http", b"sslCAInfo", ssl_cert_file)
                config.backends.insert(0, ssl_config)

        return original_from_parsedurl(self, *args, config=config, **kwargs)

    return patched_from_parsedurl


def patched_paramiko_client_SSHClient_auth(original_auth):  # pylint: disable=C0103
    """ Allow to pass prepared pkey in key_filename(s) """
    def patched_function(  # pylint: disable=R0913
            self, username, password, pkey, key_filenames, allow_agent, look_for_keys,  # pylint: disable=W0613
            gss_auth, gss_kex, gss_deleg_creds, gss_host, passphrase,
    ):
        if isinstance(key_filenames, list) and len(key_filenames) == 1 and \
                isinstance(key_filenames[0], paramiko.RSAKey):
            target_pkey = key_filenames[0]
            target_key_filenames = list()
            return original_auth(
                self,
                username, password, target_pkey, target_key_filenames, allow_agent, look_for_keys,
                gss_auth, gss_kex, gss_deleg_creds, gss_host, passphrase,
            )
        if isinstance(key_filenames, paramiko.RSAKey):
            target_pkey = key_filenames
            target_key_filenames = list()
            return original_auth(
                self,
                username, password, target_pkey, target_key_filenames, allow_agent, look_for_keys,
                gss_auth, gss_kex, gss_deleg_creds, gss_host, passphrase,
            )
        return original_auth(
            self,
            username, password, pkey, key_filenames, allow_agent, look_for_keys,
            gss_auth, gss_kex, gss_deleg_creds, gss_host, passphrase,
        )
    return patched_function


def clone(  # pylint: disable=R0913,R0912,R0914,R0915
        source, target, branch="main", depth=None, delete_git_dir=False,
        username=None, password=None, key_filename=None, key_data=None,
        track_branch_upstream=True,
):
    """ Clone repository """
    # Prepare auth args
    auth_args = dict()
    if username is not None:
        auth_args["username"] = username
    if password is not None:
        auth_args["password"] = password
    if key_filename is not None:
        auth_args["key_filename"] = key_filename
    if key_data is not None:
        key_obj = io.StringIO(key_data.replace("|", "\n"))
        pkey = paramiko.RSAKey.from_private_key(key_obj)
        auth_args["key_filename"] = pkey
    # Clone repository
    log.info("Cloning repository %s into %s", source, target)
    repository = porcelain.clone(
        source, target, checkout=False, depth=depth,
        errstream=log.DebugLogStream(),
        **auth_args
    )
    # Get current HEAD tree (default branch)
    try:
        head_tree = repository[b"HEAD"]
    except:  # pylint: disable=W0702
        head_tree = None
    # Get target tree (requested branch)
    branch_b = branch.encode("utf-8")
    try:
        target_tree = repository[b"refs/remotes/origin/" + branch_b]
    except:  # pylint: disable=W0702
        target_tree = None
    # Checkout branch
    branch_to_track = None
    if target_tree is not None:
        log.info("Checking out branch %s", branch)
        repository[b"refs/heads/" + branch_b] = repository[b"refs/remotes/origin/" + branch_b]
        repository.refs.set_symbolic_ref(b"HEAD", b"refs/heads/" + branch_b)
        repository.reset_index(repository[b"HEAD"].tree)
        #
        branch_to_track = branch
    elif head_tree is not None:
        try:
            default_branch_name = repository.refs.follow(b"HEAD")[0][1]
            if default_branch_name.startswith(refs.LOCAL_BRANCH_PREFIX):
                default_branch_name = default_branch_name[len(refs.LOCAL_BRANCH_PREFIX):]
            default_branch_name = default_branch_name.decode("utf-8")
            #
            log.warning(
                "Branch %s was not found. Checking out default branch %s",
                branch, default_branch_name
            )
            #
            branch_to_track = default_branch_name
        except:  # pylint: disable=W0702
            log.warning("Branch %s was not found. Trying to check out default branch", branch)
        #
        try:
            repository.reset_index(repository[b"HEAD"].tree)
        except:  # pylint: disable=W0702
            log.exception("Failed to checkout default branch")
    else:
        log.error("Branch %s was not found and default branch is not set. Skipping checkout")
    # Add remote tracking
    if track_branch_upstream and branch_to_track is not None:
        log.info("Setting '%s' to track upstream branch", branch_to_track)
        #
        branch_to_track_b = branch_to_track.encode("utf-8")
        #
        config = repository.get_config()
        config.set(
            (b"branch", branch_to_track_b),
            b"remote", b"origin",
        )
        config.set(
            (b"branch", branch_to_track_b),
            b"merge", b"refs/heads/" + branch_to_track_b,
        )
        config.write_to_path()
    # Delete .git if requested
    if delete_git_dir:
        log.info("Deleting .git directory")
        shutil.rmtree(os.path.join(target, ".git"))
    # Return repo object
    return repository
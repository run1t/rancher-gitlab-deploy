#!/usr/bin/env python
import os, sys, subprocess
import click
import requests
import json
import logging
import contextlib
import __tools as tools
import _service
import _stack
import _environment

try:
    from http.client import HTTPConnection # py3
except ImportError:
    from httplib import HTTPConnection # py2

from time import sleep

@click.command()
@click.option('--rancher-url', envvar='RANCHER_URL', required=True,
              help='The URL for your Rancher server, eg: http://rancher:8000')
@click.option('--rancher-key', envvar='RANCHER_ACCESS_KEY', required=True,
              help="The environment or account API key")
@click.option('--rancher-secret', envvar='RANCHER_SECRET_KEY', required=True,
              help="The secret for the access API key")
@click.option('--environment', 'environmentOpt', default=None,
              help="The name of the environment to add the host into " + \
                   "(only needed if you are using an account API key instead of an environment API key)")
@click.option('--stack', 'stackOpt', envvar='CI_PROJECT_NAMESPACE', default=None, required=True,
              help="The name of the stack in Rancher (defaults to the name of the group in GitLab)")
@click.option('--service', 'serviceOpt', envvar='CI_PROJECT_NAME', default=None, required=True,
              help="The name of the service in Rancher to upgrade (defaults to the name of the service in GitLab)")
@click.option('--start-before-stopping/--no-start-before-stopping', default=False,
              help="Should Rancher start new containers before stopping the old ones?")
@click.option('--batch-size', default=1,
              help="Number of containers to upgrade at once")
@click.option('--batch-interval', default=2,
              help="Number of seconds to wait between upgrade batches")
@click.option('--upgrade-timeout', default=5*60,
              help="How long to wait, in seconds, for the upgrade to finish before exiting. To skip the wait, pass the --no-wait-for-upgrade-to-finish option.")
@click.option('--wait-for-upgrade-to-finish/--no-wait-for-upgrade-to-finish', default=True,
              help="Wait for Rancher to finish the upgrade before this tool exits")
@click.option('--new-image', default=None,
              help="If specified, replace the image (and :tag) with this one during the upgrade")
@click.option('--finish-upgrade/--no-finish-upgrade', default=True,
              help="Mark the upgrade as finished after it completes")
@click.option('--sidekicks/--no-sidekicks', default=False,
              help="Upgrade service sidekicks at the same time")
@click.option('--new-sidekick-image', default=None, multiple=True,
              help="If specified, replace the sidekick image (and :tag) with this one during the upgrade", type=(str, str))
@click.option('--debug/--no-debug', default=False,
              help="Enable HTTP Debugging")
@click.option('--create/--no-debug', default=False,
              help='Create a new container in the stack')
@click.option('--image', envvar='RANCHER_URL',
              help='Choose image to launch')
def main(rancher_url, rancher_key, rancher_secret, environmentOpt, stackOpt, serviceOpt, new_image, batch_size, batch_interval, start_before_stopping, upgrade_timeout, wait_for_upgrade_to_finish, finish_upgrade, sidekicks, new_sidekick_image, debug, create, image):
    """Performs an in service upgrade of the service specified on the command line"""

    if debug:
        tools.debug_requests_on()

    # split url to protocol and host
    if "://" not in rancher_url:
        tools.bail("The Rancher URL doesn't look right")

    proto, host = rancher_url.split("://")
    api = "%s://%s:%s@%s/v2-beta" % (proto, rancher_key, rancher_secret, host)

    # 1 -> Find the environment id in Rancher
    environment_id, environment_name = _environment.fetch(api, host, environmentOpt)
    environmentTest = {
        'id': environment_id,
        'name': environment_name
    }
    
    if not create:
        service, mode = upgrade(api, host, environmentTest, stackOpt, serviceOpt, upgrade_timeout, batch_size, batch_interval, start_before_stopping)
    else:
        service, mode = _service.createService(api, environmentTest, serviceOpt, image)
        if service is None:
            service, mode = upgrade(api, host, environmentTest, stackOpt, serviceOpt, upgrade_timeout, batch_size, batch_interval, start_before_stopping)

    # 6 -> Wait for the upgrade to finish

    if not wait_for_upgrade_to_finish:
        tools.msg("Upgrade started")
    else:
        tools.msg("Upgrade started, waiting for upgrade to complete...")
        attempts = 0
        if mode == "create":
            checString = "active"
        else:
            checString = "upgraded"
        tools.msg("Upgrade started, waiting for upgrade to complete..." + checString)
        while service['state'] != checString:
            sleep(2)
            attempts += 2
            if attempts > upgrade_timeout:
                tools.bail("A timeout occured while waiting for Rancher to complete the upgrade")
            try:
                r = requests.get("%s/projects/%s/services/%s" % (
                    api, environment_id, service['id']
                ))
                r.raise_for_status()
            except requests.exceptions.HTTPError:
                tools.bail("Unable to fetch the service status from the Rancher API")
            else:
                service = r.json()

        if mode != 'create':
            tools.msg("Finishing upgrade...")
            try:
                r = requests.post("%s/projects/%s/services/%s/?action=finishupgrade" % (
                    api, environment_id, service['id']
                ))
                r.raise_for_status()
            except requests.exceptions.HTTPError as e:
                tools.bail("Unable to finish the upgrade in Rancher" + str(e.response.status_code))
        attempts = 0
        while service['state'] != "active":
            sleep(2)
            attempts += 2
            if attempts > upgrade_timeout:
                tools.bail("A timeout occured while waiting for Rancher to finish the previous upgrade")
            try:
                r = requests.get("%s/projects/%s/services/%s" % (
                    api, environment_id, service['id']
                ))
                r.raise_for_status()
            except requests.exceptions.HTTPError:
                tools.bail("Unable to request the service status from the Rancher API")
            else:
                service = r.json()

        tools.msg("Upgrade finished")

    sys.exit(0)



def upgrade(api, host, environment, stackOpt, serviceOpt, upgrade_timeout, batch_size, batch_interval, start_before_stopping):
     # 3 -> Find the stack in the environment
    stack = _stack.fetch(api, host, environment, stackOpt)
    
    # 3 -> Find the service in the stack
    service = _service.fetch(api, environment, stack, serviceOpt)
    # 4 -> Is the service elligible for upgrade?
    if service['state'] == 'upgraded':
        tools.warn("The current service state is 'upgraded', marking the previous upgrade as finished before starting a new upgrade...")
        service = _service.markHasFinished(api, environment, service, upgrade_timeout)
    
    tools.msg("Upgrading %s/%s in environment %s..." % (stack['name'], service['name'], environment['name']))

    upgrade = {'inServiceStrategy': {
        'batchSize': batch_size,
        'intervalMillis': batch_interval * 1000, # rancher expects miliseconds
        'startFirst': start_before_stopping,
        'launchConfig': service['launchConfig'],
        'secondaryLaunchConfigs': []
    }}

    service = _service.upgrade(api, environment, service, upgrade)
    return service, 'upgrade'
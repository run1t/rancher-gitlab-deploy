import os, sys, subprocess
import click
import requests
import json
import logging
import contextlib
import sys
import __tools as tools
try:
    from http.client import HTTPConnection # py3
except ImportError:
    from httplib import HTTPConnection # py2

from time import sleep

MODELS_PATH = 'rancher_gitlab_deploy/models/'

def createService(api, environment, name, image):
    with open(MODELS_PATH + 'createService.json') as upgrade:
        upgrade = json.load(upgrade)
    upgrade['name'] = name
    upgrade['image'] = image
    try:
        r = requests.post("%s/projects/%s/service" % (
            api, environment['id']
        ), json=upgrade)
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        return None, 'create'
    else:
        return r.json(), 'create'
        
        
    

def fetch(api, environment, stack, serviceOption):
    try:
        r = requests.get("%s/projects/%s/services?limit=1000" % (
            api,
            stack['id']
        ))
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        bail("Unable to fetch a list of services in the stack. Does your API key have the right permissions?")
    else:
        services = r.json()['data']

    for s in services:
        if s['name'].lower() == serviceOption.lower():
            return s
    bail("The current service doesn't exist on this stack")

def upgrade(api, environment, service, upgrade):
    try:
        r = requests.post("%s/projects/%s/services/%s/?action=upgrade" % (
            api, environment['id'], service['id']
        ), json=upgrade)
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        tools.bail("Unable to request an upgrade on Rancher")
    else:
        return r.json()

def markHasFinished(api, environment, service, upgrade_timeout):
    try:
        r = requests.post("%s/projects/%s/services/%s/?action=finishupgrade" % (
            api, environment['id'], service['id']
        ))
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        bail("Unable to finish the previous upgrade in Rancher")

    attempts = 0
    while service['state'] != "active":
        sleep(2)
        attempts += 2
        if attempts > upgrade_timeout:
            bail("A timeout occured while waiting for Rancher to finish the previous upgrade")
        try:
            r = requests.get("%s/projects/%s/services/%s" % (
                api, environment['id'], service['id']
            ))
            r.raise_for_status()
        except requests.exceptions.HTTPError:
            bail("Unable to request the service status from the Rancher API")
        else:
            service = r.json()
    if service['state'] != 'active':
        bail("Unable to start upgrade: current service state '%s', but it needs to be 'active'" % service['state'])
    return service

def msg(msg):
    click.echo(click.style(msg, fg='green'))

def warn(msg):
    click.echo(click.style(msg, fg='yellow'))

def bail(msg):
    click.echo(click.style('Error: ' + msg, fg='red'))
    sys.exit(1)

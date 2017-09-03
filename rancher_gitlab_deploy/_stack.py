import os, sys, subprocess
import click
import requests
import json
import logging
import contextlib
import __tools as tools
try:
    from http.client import HTTPConnection # py3
except ImportError:
    from httplib import HTTPConnection # py2

from time import sleep

def fetch(api, host, environment, stackOption):
    try:
        r = requests.get("%s/projects/%s/stacks?limit=1000" % (
            api,
            environment['id']
        ))
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        tools.bail("Unable to fetch a list of stacks in the environment '%s'" % environment['name'])
    else:
        stacks = r.json()['data']

    for s in stacks:
        if s['name'].lower() == stackOption.lower():
            stack = s
            break
    else:
        tools.bail("Unable to find a stack called '%s'. Does it exist in the '%s' environment?" % (stack, environment['name']))

    return stack
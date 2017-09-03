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
def fetch(api, host, environmentOption):
    try:
        r = requests.get("%s/projects?limit=1000" % api)
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        bail("impossible de réciupére le s")
    else:
        environments = r.json()['data']
    if environmentOption is None:
        environment = environments[0]
    else:
        environment = filter(lambda e: extractEnvironments(e, environmentOption))
        if environment is None:
            tools.bail("The '%s' environment doesn't exist in Rancher, or your API credentials don't have access to it" % environmentOption)
    return environment['id'], environment['name']

def extractEnvironments(option, environment):
    return option['id'].lower() == environment.lower() or option['name'].lower() == environment.lower()
#!/usr/bin/env python
import os, sys, subprocess
import click
import requests
import json
import logging
import contextlib
try:
    from http.client import HTTPConnection # py3
except ImportError:
    from httplib import HTTPConnection # py2


from time import sleep

def msg(msg):
    click.echo(click.style(msg, fg='green'))

def warn(msg):
    click.echo(click.style(msg, fg='yellow'))

def bail(msg):
    click.echo(click.style('Error: ' + msg, fg='red'))
    sys.exit(1)

def error(code):
    bail("Unable to connect to Rancher at %s - is the URL and API key right?")

def debug_requests_on():
    '''Switches on logging of the requests module.'''
    HTTPConnection.debuglevel = 0

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True

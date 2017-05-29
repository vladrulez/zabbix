#!/usr/bin/env python
# vim: set filetype=python ts=4 sw=4 et si
# -*- coding: utf-8 -*-

import sys,argparse

try:
    import urllib2
except ImportError:
    import urllib.request as urllib2 # python3

try:
    import simplejson as json
except ImportError:
    import json

NAGIOS_OK_RC = 0
NAGIOS_OK_STR = "ZABBIX OK\n"
NAGIOS_WARNING_RC  = 1
NAGIOS_WARNING_STR = "ZABBIX WARNING"
NAGIOS_CRITICAL_RC = 2
NAGIOS_CRITICAL_STR = "ZABBIX CRITICAL"
NAGIOS_UNKNOWN_RC = 3
NAGIOS_UNKNOWN_STR = "ZABBIX UNKNOWN\n"

HEADERS = {
              'Content-Type': 'application/json-rpc',
              'User-Agent': 'check_zabbix'
          }

def nagios_unknown():
    sys.stderr.write(NAGIOS_UNKNOWN_STR)
    sys.exit(NAGIOS_UNKNOWN_RC)

def login(url,user,password):
    authdata = {
                    "jsonrpc": "2.0",
                    "method": "user.login",
                    "params": {
                        "user": user,
                        "password": password
                    },
                    "id": 1,
                }
    try:
        req = urllib2.Request(url=url, data=json.dumps(authdata).encode('utf-8'), headers=HEADERS)
        return json.loads(urllib2.urlopen(req, timeout=10).read().decode('utf-8'))['result']
    except Exception as ex:
        sys.stderr.write("Can't authorize at url %s with error %s" % (url, str(ex)))
        nagios_unknown

def check_triggers(url, auth):
    trigdata = {
                   "jsonrpc": "2.0",
                    "method": "trigger.get",
                    "params": {
                        "active": 1,
                        "withUnacknowledgedEvents": 1,
                        "output": [
                            "triggerid",
                            "description",
                            "priority"
                        ],
                        "filter": { 
                             "value": 1
                        },
                        "sortfield": "priority",
                        "sortorder": "DESC"
                    },
                    "id": 2,
                    "auth": auth
                }
    try:
        req = urllib2.Request(url=url, data=json.dumps(trigdata).encode('utf-8'), headers=HEADERS)
        return json.loads(urllib2.urlopen(req).read().decode('utf-8'))['result']
    except Exception as ex:
        sys.stderr.write("Can't get triggers at url %s with error %s" % (url, str(ex)))
        nagios_unknown

if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description='Zabbix active triggers check')
        parser.add_argument('--url', help='zabbix server url', nargs='?', required=True)
        parser.add_argument('--user', help='zabbix user username', nargs='?', required=True)
        parser.add_argument('--pass', dest='password', help='zabbix user password', nargs='?', required=True)
        args = parser.parse_args()
    except Exception as ex:
        sys.stderr.write(str(ex))
        nagios_unknown
    
    if not all([args.password, args.url, args.user]):
        sys.stderr.write('\n--url, --user and --pass options are required and can not be empty\n\n')
        parser.print_help()
        nagios_unknown
    else:
        if args.url.endswith(('/zabbix', '/zabbix/')):
            args.url = args.url + '/api_jsonrpc.php'
        if not args.url.startswith(('http://', 'https://')):
            args.url = 'https://' + args.url

        auth = login(args.url, args.user, args.password)
        triggers = check_triggers(args.url, auth)
        isproblem = 0
        trigger_description = ''
        if triggers:
            for trigger in triggers:
                if trigger['priority'] >= 3:
                    sys.stderr.write( "%s %s \n" % (NAGIOS_CRITICAL_STR , trigger['description']))
                    sys.exit(NAGIOS_CRITICAL_RC)
                elif 0 < trigger['priority'] < 3:
                    isproblem = 1
                    trigger_description = trigger_description + " " + trigger['description']

        if isproblem == 1:
            sys.stderr.write("%s %s \n" % (NAGIOS_WARNING_STR, trigger_description))
            sys.exit(NAGIOS_WARNING_RC)
        elif isproblem == 0:
            sys.stderr.write(NAGIOS_OK_STR)
            sys.exit(NAGIOS_OK_RC)

#!/usr/bin/env python
# vim: set filetype=python ts=4 sw=4 et si
# -*- coding: utf-8 -*-

import urllib2, base64, re, time, socket, sys, datetime, os.path, subprocess

# Zabbix agent config file path
zabbix_config = '/etc/zabbix/zabbix_agentd.conf'   

# URL to php-fpm stat
stat_url = 'http://127.0.0.1:10061/fpm_status'

# Optional Basic Auth
username = ''
password = ''

def execute(command, stdin=None):
    child = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stdin=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True)
    output = child.communicate(input=stdin)[0]
    return child.returncode, output

def send_to_zabbix(metrics):
    # Build Zabbix sender input.
    rows = ''
    for key,value in metrics:
        clock = '%d' % time.time()
        row = "- php-fpm.status[%s] %s %s\n" % (key, clock, value)
        sys.stdout.write(row)
        rows += row

    # Submit metrics.
    rc, output = execute('zabbix_sender -T -r -i - %(config)s' % {
        'config':
            '-c "%s"' % zabbix_config
    }, stdin=rows)

    # Check return code.
    if rc == 0:
        sys.stdout.write(output)
    else:
        sys.stderr.write(output)
        sys.exit(1)

def get(url, login, passwd):
	req = urllib2.Request(url)
	if login and passwd:
		base64string = base64.encodestring('%s:%s' % (login, passwd)).replace('\n', '')
		req.add_header("Authorization", "Basic %s" % base64string)   
	q = urllib2.urlopen(req)
	res = q.read()
	q.close()
	return res

data = get(stat_url, username, password).split('\n')
data = filter(None, data)
metrics = []
for data_str in data:
    try:
        (key, value) = data_str.split(': ')
        key = key.replace(' ', '-')
        value = value.lstrip()
        metrics.append([key,value])
    except:
        pass

send_to_zabbix(metrics)

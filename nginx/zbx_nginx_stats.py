#!/usr/bin/env python
# vim: set filetype=python ts=4 sw=4 et si
# -*- coding: utf-8 -*-

import urllib2, base64, re, time, socket, sys, datetime, os.path, subprocess

# Zabbix agent config file path
zabbix_config = '/etc/zabbix/zabbix_agentd.conf'   

# grep interval in minutes
time_delta = 1              

# URL to nginx stat (http_stub_status_module)
stat_url = 'http://127.0.0.1:81/status'

# Nginx log file path
nginx_log_file_path = '/var/log/nginx/access.log'

# Optional Basic Auth
username = ''
password = ''

# Temp file, with log file cursor position
seek_file = '/tmp/nginx_log_stat'


class Metric(object):
    def __init__(self, key, value, clock=None):
        self.key = key
        self.value = value
        self.clock = clock

    def __repr__(self):
        if self.clock is None:
            return 'Metric(%r, %r)' % (self.key, self.value)
        return 'Metric(%r, %r, %r)' % (self.key, self.value, self.clock)


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
    for m in metrics:
        clock = m.clock or ('%d' % time.time())
        row = "- %s %s %s\n" % (m.key, clock, m.value)
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

def parse_nginx_stat(data):
	a = {}
	# Active connections
	a['active_connections'] = re.match(r'(.*):\s(\d*)', data[0], re.M | re.I).group(2)
	# Accepts
	a['accepted_connections'] = re.match(r'\s(\d*)\s(\d*)\s(\d*)', data[2], re.M | re.I).group(1)
	# Handled
	a['handled_connections'] = re.match(r'\s(\d*)\s(\d*)\s(\d*)', data[2], re.M | re.I).group(2)
	# Requests
	a['handled_requests'] = re.match(r'\s(\d*)\s(\d*)\s(\d*)', data[2], re.M | re.I).group(3)
	# Reading
	a['header_reading'] = re.match(r'(.*):\s(\d*)(.*):\s(\d*)(.*):\s(\d*)', data[3], re.M | re.I).group(2)
	# Writing
	a['body_reading'] = re.match(r'(.*):\s(\d*)(.*):\s(\d*)(.*):\s(\d*)', data[3], re.M | re.I).group(4)
	# Waiting
	a['keepalive_connections'] = re.match(r'(.*):\s(\d*)(.*):\s(\d*)(.*):\s(\d*)', data[3], re.M | re.I).group(6)
	return a


def read_seek(file):
    if os.path.isfile(file):
        f = open(file, 'r')
        try:
            result = int(f.readline())
            f.close()
            return result
        except:
            return 0
    else:
        return 0

def write_seek(file, value):
    f = open(file, 'w')
    f.write(value)
    f.close()


#print '[12/Mar/2014:03:21:13 +0400]'

d = datetime.datetime.now()-datetime.timedelta(minutes=time_delta)
minute = int(time.mktime(d.timetuple()) / 60)*60
d = d.strftime('%d/%b/%Y:%H:%M')

total_rps = 0
rps = [0]*60
tps = [0]*60
res_code = {}

nf = open(nginx_log_file_path, 'r')

new_seek = seek = read_seek(seek_file)

# if new log file, don't do seek
if os.path.getsize(nginx_log_file_path) > seek:
    nf.seek(seek)

line = nf.readline()
while line:
    if d in line:
        new_seek = nf.tell()
        total_rps += 1
        sec = int(re.match('(.*):(\d+):(\d+):(\d+)\s', line).group(4))
        code = re.match(r'(.*)"\s(\d*)\s', line).group(2)
        if code in res_code:
            res_code[code] += 1
        else:
            res_code[code] = 1

        rps[sec] += 1
    line = nf.readline()

if total_rps != 0:
    write_seek(seek_file, str(new_seek))

nf.close()

metric = (len(sys.argv) >= 2) and re.match(r'nginx\[(.*)\]', sys.argv[1], re.M | re.I).group(1) or False
data = get(stat_url, username, password).split('\n')
data = parse_nginx_stat(data)

data_to_send = []

# Adding the metrics to response
if not metric:
    for i in data:
        data_to_send.append(Metric(('nginx[%s]' % i), data[i]))
else:
    print data[metric]

# Adding the request per seconds to response
for t in range(0,60):
    data_to_send.append(Metric('nginx[rps]', rps[t], minute+t))

# Adding the response codes stats to respons
for t in res_code:
    data_to_send.append(Metric(('nginx[%s]' % t), res_code[t]))


send_to_zabbix(data_to_send)

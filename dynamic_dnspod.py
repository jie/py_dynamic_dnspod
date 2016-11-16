# -*- coding: UTF-8 -*-

'''
Usage:
  dynamic_dnspod.py [options]

Options:
  -h --help      Show this screen.
  -l LOG_PATH    Program log file [default: /var/log/dynamic_dnspod.log].
  -p PID_FILE    Use PID_FILE as daemon's pid file [default: /var/run/dynamic_dnspod.pid].
  -d ACTION      Run this script as a daemon (e.g. start,stop,restart).
'''


import os
import sys
import docopt
import time
import socket
import addict
import json
import requests
# import logging
from datetime import datetime
from daemon import runner


DNSPOD_CONFIG = None


def get_current_ip():
    sock = socket.create_connection(('ns1.dnspod.net', 6666), timeout=30)
    ip = sock.recv(16)
    sock.close()
    return ip


def dnspod_api(addr, data):
    response = requests.post(addr, data=data)
    if not response.ok:
        print('REQ-%s:%s:' % (addr, response.content))
        return

    content = response.json()
    if not content.get('status') or content['status']["code"] != "1":
        print('REQ-%s:%s:' % (addr, response.content))
        return
    return content


def load_config():
    global DNSPOD_CONFIG
    path = os.path.join(os.getcwd(), 'config.json')
    with open(path) as f:
        config = f.read()
    DNSPOD_CONFIG = addict.Dict(json.loads(config))


def update_dnspod_record(domain_config, current_ip=None):
    print('%s::period_tick' % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    global DNSPOD_CONFIG
    data = {
        'login_token': DNSPOD_CONFIG.token,
        'domain': domain_config.domain,
        'sub_domain': domain_config.sub_domain,
        'format': 'json'
    }
    result = dnspod_api(DNSPOD_CONFIG.addr.record_list, data=data)
    if not result:
        data = {
            'login_token': DNSPOD_CONFIG.token,
            'record_type': domain_config.record_type or 'A',
            'domain': domain_config.domain,
            'sub_domain': domain_config.sub_domain,
            'value': current_ip,
            'record_line': domain_config.record_line,
            'format': 'json'
        }
        dnspod_api(DNSPOD_CONFIG.addr.record_create, data=data)

    else:
        for item in result['records']:
            if item['name'] == domain_config.sub_domain and item['value'] != current_ip:
                data = {
                    'login_token': DNSPOD_CONFIG.token,
                    'domain': domain_config.domain,
                    'sub_domain': domain_config.sub_domain,
                    'record_id': item['id'],
                    'value': current_ip,
                    'record_line': domain_config.record_line,
                    'format': 'json'
                }
                dnspod_api(DNSPOD_CONFIG.addr.record_ddns, data=data)
                break



def main_loop():
    global DNSPOD_CONFIG
    while True:
        current_ip = get_current_ip()
        for item in DNSPOD_CONFIG['domains']:
            update_dnspod_record(item, current_ip)
        time.sleep(DNSPOD_CONFIG.system.sleep_minutes * 60)


class DNSPodDaemon(object):

    def __init__(self, args):
        self.stdin_path = os.devnull
        self.stdout_path = os.devnull
        self.stderr_path = os.devnull
        self.pidfile_path = args['-p']
        self.pidfile_timeout = 3

    def run(self):
        main_loop()


def main():

    try:
        arguments = docopt.docopt(__doc__)
    except docopt.DocoptExit:
        print(__doc__.strip())
        return

    dnspod_daemon = DNSPodDaemon(arguments)
    action = arguments['-d']
    load_config()
    if action is not None:
        if action in ['start', 'stop', 'restart']:
            sys.argv[1] = action
            daemon_runner = runner.DaemonRunner(dnspod_daemon)
            daemon_runner.do_action()
        else:
            print(__doc__.strip())
            return
    else:
        dnspod_daemon.run()

    main_loop()


if __name__ == '__main__':
    main()

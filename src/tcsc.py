#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CLI to manage the Wanda containers, the host containers holding the supportconfig and
running Trento checks.

Exit Codes:
-----------
    0   Everything went fine.
    1   Exception occurred accessing or parsing the configuration file.
    2   Exception occurred in communicating with Docker.
    3   Exception occurred in communicating with Wanda.
    4   A problem with Wanda occurred.
    5   A problem with a host container occurred.
    6   Something is wrong with the check.
    9   An unknown error occurred.
   10   Feature not yet implemented.
   12   A problem with the command line arguments occurred.

    
Changelog:
----------
01.03.2024      v0.0        - and so it begins...
21.11.2024      v1.0        - core stuff has been implemented
22.11.2024      v1.1        - adding support for HOST_ROOT_FS environment variable to
                              support containerization of `tcsc` command
                            - added -c|--config to allow arbitrary config files
25.11.2024      v1.1.1      - fixed a bug in creating new hosts when called locally and
                              not containerized
                            - fixed bug in starting a host container where the path handed
                              over to the docker volume still had the HOST_ROOT_FS prefix
12.12.2024      v1.2        - added trento-checks container to wanda status and check for
                              the presence of mandatory volumes
                            - added hosts rescan to reload supportfiles into a running host
                              container
                            - support supportconfig directories too
                            - fixed bug: hosts status ignored given host group
                            - string decoding not utf-8 per default but sys.getdefaultencoding()
16.12.2024      v1.3        - all Trento check environment entries are now set as label for host
                              containers with no auto detection from supportconfig except provider
                            - hosts status details contain environment entries
                            - starting and creating hosts are two commands now
                            - host environment entries can be overridden on creation
                            - `checks list` shows all environment entries
                            - `checks list` shows only supported checks except newly introduced
                              --a|--all is given
                            - introduce `checks show` command
"""

import argparse
import collections
import os
import docker
import sys
from collections import Counter
from rabbiteer import Rabbiteer
from typing import List, Dict, Tuple
import signal
import textwrap
from tcsc_config import *
from tcsc_cli import *
from tcsc_wanda import *
from tcsc_hosts import *
from tcsc_supportfiles import *


__version__ = '1.3'
__author__ = 'Sören Schmidt'
__email__ = 'soren.schmidt@suse.com'
__maintainer__ = __author__
__license__ = "GPLv3"
__status__ = 'Prototype'


class ArgParser(argparse.ArgumentParser):

    def format_help(self) -> str:
        """Prints full help message."""

        prog = os.path.basename(sys.argv[0])
        text = f'''
                Usage:  {prog} -h|--help
                        {prog} [-j|--json] [-c|--config CONFIG] wanda start|status|stop
                        {prog} [-j|--json] [-c|--config CONFIG] hosts create GROUPNAME [-e|--env KEY=VALUE...] SUPPORTFILE ...
                        {prog} [-j|--json] [-c|--config CONFIG] hosts start GROUPNAME
                        {prog} [-j|--json] [-c|--config CONFIG] hosts rescan GROUPNAME
                        {prog} [-j|--json] [-c|--config CONFIG] hosts stop GROUPNAME
                        {prog} [-j|--json] [-c|--config CONFIG] hosts status [-d|--details] GROUPNAME]
                        {prog} [-j|--json] [-c|--config CONFIG] hosts remove GROUPNAME
                        {prog} [-j|--json] [-c|--config CONFIG] hosts logs [-l|--lines N] CONTAINERNAME
                        {prog} [-j|--json] [-c|--config CONFIG] checks list [-d|--details] [-a|--all]
                        {prog} [-j|--json] [-c|--config CONFIG] checks show CHECK
                        {prog} [-j|--json] [-c|--config CONFIG] checks run [-p|--provider PROVIDER] [-f|--failure-only] -g|--group GROUP... GROUPNAME
                        {prog} [-j|--json] [-c|--config CONFIG] checks run [-p|--provider PROVIDER] [-f|--failure-only] -c|--check CHECK... GROUPNAME

                v{__version__}
            
                Interacts with Wanda using its API (https://www.trento-project.io/wanda/).

                Options:

                    -h, --help              print this help text
                    -j, --json              output in JSON
                    -c, --config CONFIG     alternative config file (default: ~/.config/tcsc/config) 

                Arguments: 

                    wanda           manages the Wanda containers
                    hosts           manages the supportconfig host containers
                    checks          manages Trento checks

                Command Options and Arguments:

                    wanda:

                        Manages the Wanda containers, like wanda, rabbitmq and postgres.

                        start       starts the Wanda containers
                        status      prints the status of the Wanda containers
                        stop        stops the Wanda containers
                    
                    hosts:
                    
                        Manages the containers which simulate the hosts based on the
                        supportfiles.
                    
                        create      creates a hostgroup and starts container
                        start       starts hostgroup containers
                        status      prints the status of host group containers
                        setenv      sets environment entries required by checks
                        stop        stops hostgroup containers
                        rescan      reloads supportfiles into the host containers
                    
                        GROUPNAME           arbitrary name for the hostgroup
                        SUPPORTFILE         a supportfile (e.g. supportconfig)
                        CONTAINERNAME       name of the host container
                        -e, --env KEY=VALUE environment entry key-value pair with keys:
                                            provider, cluster_type, architecture_type,
                                            ensa_version, mixed_versions, filesystem_type
                        -d, --details       prints more details about the container
                        -l, --lines N       limits log output to the last N lines
                        
                    checks:
                    
                        Lists and executes Trento checks.                        

                        list        lists all available checks
                        show        shows check
                        run         execute supported checks
                        
                        GROUPNAME                arbitrary name for the hostgroup
                        -d, --details            prints more details about the check
                        -a, --all                shows all checks 
                        -p, --provider PROVIDER  the provider (infrastructure)
                        -f, --failure-only       print only checks which did not pass
                        -g, --group GROUP        run only checks from that Trento check group
                        -c, --check CHECK        run only this check

                        Providers can be one of: default, kvm, vmware, azure, aws, gcp
                        
                Exit codes:

                     0   Everything went fine.
                     1   Exception occurred accessing or parsing the configuration file.
                     2   Exception occurred in communicating with Docker.
                     3   Exception occurred in communicating with Wanda.
                     4   A problem with Wanda occurred.
                     5   A problem with a host container occurred.
                     6   Something is wrong with the check.
                     9   An unknown error occurred.
                    10   Feature not yet implemented.
                    12   A problem with the command line arguments occurred.

                Examples:

                    Check the health of Wanda:                    {prog} wanda status
                    Start two fresh hosts:                        {prog} hosts start ACME scc_vmhana01_231011_1528.txz scc_vmhana02_231011_1533.txz
                    List all available checks (JSON dump):        {prog} -j checks list
                    Execute all checks and for (aws) hosts:       {prog} checks run -p aws ACME

                '''
        return textwrap.dedent(text)


def signal_handler(sig: int, frame: Any) -> None:
    sys.exit(0)


def argument_parse() -> dict:
    """Evaluates the command line arguments."""
    
    parser = ArgParser(prog=os.path.basename(sys.argv[0]), 
                       description='Manages containers to use Wanda checks on support files.',
                       add_help=False,
                       epilog='')

    parser.add_argument('-h', '--help', 
                        dest='help',
                        action='help',
                        default=argparse.SUPPRESS)  
    
    parser.add_argument('-j', '--json',
                        dest='json_output',
                        action='store_true',
                        required=False,
                        help='output is done in JSON')
    
    parser.add_argument('-c', '--config',
                        dest='config_file',
                        action='store',
                        required=False,
                        default='${HOME}/.config/tcsc/config',
                        help='path to the config file')  
     
    selectors = parser.add_subparsers(dest='selectors', metavar='wanda|hosts|checks')
    selectors.required = True
    
    # Selector: wanda
    wanda = selectors.add_parser('wanda', help='Manages Wanda container stack.')
    wanda_commands = wanda.add_subparsers(dest='wanda_commands', metavar='start|status|stop')
    wanda_commands.required = True
    
    wanda_start = wanda_commands.add_parser('start', help='Starts Wanda containers.')
    wanda_status = wanda_commands.add_parser('status', help='Prints status of Wanda.')
    wanda_stop = wanda_commands.add_parser('stop', help='Stops Wanda containers.') 

    # Selector: hosts
    hosts = selectors.add_parser('hosts', help='Manages host containers.')
    hosts_commands = hosts.add_subparsers(dest='host_commands', metavar='start|stop|rescan|remove|status|logs')
    hosts_commands.required = True
 
    hosts_create = hosts_commands.add_parser('create', help='Creates host group.')
    hosts_start = hosts_commands.add_parser('start', help='Starts host group.')
    hosts_stop = hosts_commands.add_parser('stop', help='Stops host group.')
    hosts_rescan = hosts_commands.add_parser('rescan', help='Reloads the supportfiles.')
    hosts_remove = hosts_commands.add_parser('remove', help='Removes host group.')
    hosts_status = hosts_commands.add_parser('status', help='Prints status of hosts.')
    hosts_logs = hosts_commands.add_parser('logs', help='Lists logs of a host container.')
    
    for p in  hosts_create, hosts_start, hosts_stop, hosts_rescan, hosts_remove:
        p.add_argument(metavar='GROUPNAME',
                       dest='hostgroup',
                       help='name of the host group')
        
    hosts_status.add_argument(metavar='GROUPNAME',
                              nargs='?',
                              dest='hostgroup',
                              help='name of the host group')
    
    hosts_create.add_argument(metavar='SUPPORTFILE',
                              dest='supportfiles',
                              nargs='+',
                              help='supportfiles (like supportconfig)')
    
    hosts_create.add_argument('-e', '--env',
                              action='append',
                              dest='envpairs',
                              default=[],
                              help='environment entry key-value pair')
 
    hosts_status.add_argument('-d', '--details',
                              dest='host_details',
                              action='store_true',
                              required=False,
                              help='shows more details.')  

    hosts_logs.add_argument(metavar='CONTAINERNAME',
                             dest='containername',
                             help='name of the host container')    
    hosts_logs.add_argument('-l', '--lines',
                              metavar='N',
                              dest='last_lines',
                              type=int,
                              required=False,
                              help='show only the last N lines')  
        
    # Selector: checks
    checks = selectors.add_parser('checks',  help='Manages checks.')
    checks_commands = checks.add_subparsers(dest='checks_commands', metavar='list|show|run')
    checks_commands.required = True
    
    checks_list = checks_commands.add_parser('list', help='Lists available checks.')
    
    checks_list.add_argument('-d', '--details',
                             dest='check_details',
                             action='store_true',
                             required=False,
                             help='shows more details.') 
    checks_list.add_argument('-a', '--all',
                             dest='show_all',
                             action='store_true',
                             required=False,
                             help='shows more details.')
    
    checks_show = checks_commands.add_parser('show', help='Shows check.')
    
    checks_show.add_argument(metavar='CHECK',
                             dest='check',
                             help='name of the check')
    
    checks_run = checks_commands.add_parser('run', help='Runs Trento checks.')
    
    checks_run.add_argument(metavar='GROUPNAME',
                            dest='hostgroup',
                            help='name of the host group')
    checks_run.add_argument('-p', '--provider',
                            metavar='PROVIDER',
                            dest='provider',
                            choices=['default','kvm','vmware','azure','aws','gcp'],
                            default='default',
                            type=str,
                            required=False,
                            help='provider to use for the check')
    checks_run.add_argument('-f', '--failure-only',
                            dest='failure_only',
                            action='store_true',
                            required=False,
                            help='returns only results that have not passed')
    run_exclusive = checks_run.add_mutually_exclusive_group()
    run_exclusive.add_argument('-g', '--group',
                               metavar='GROUP',
                               dest='check_groups',
                               action='append',
                               type=str,
                               required=False,
                               help='use only checks of that group')
    run_exclusive.add_argument('-c', '--check',
                               metavar='CHECK',
                               action='append',
                               type=str,
                               required=False,
                               dest='requested_checks',
                               help='use only the check with this ID')
    
    try:  
        args_parsed = parser.parse_args()
    except SystemExit:
        sys.exit(12)
        
    # Validate environment key value pairs.
    if 'envpairs' in args_parsed and args_parsed.envpairs:
        pairs = {'provider': ['azure', 'aws', 'gcp', 'kvm', 'nutanix', 'vmware', 'unknown'], 
                 'cluster_type': ['hana_scale_up', 'hana_scale_out', 'ascs_ers'], 
                 'architecture_type': ['classic', 'angi'], 
                 'ensa_version': ['ensa1', 'ensa2', 'mixed_versions'], 
                 'filesystem_type': ['resource_managed', 'simple_mount', 'mixed_fs_types']
        }
        entries = {}
        for pair in args_parsed.envpairs:
            if '=' not in pair:
                print(f'Error in pair "{pair}".', file=sys.stderr)
                sys.exit(1)        
            key, value = pair.split('=')
            if key not in pairs:
                print(f'Unsupported key "{key}".', file=sys.stderr)
                sys.exit(1) 
            if value not in pairs[key]:
                print(f'Unsupported value "{value}" for "{key}".', file=sys.stderr)
                sys.exit(1) 
            entries[key] = value
        args_parsed.envpairs = entries
    
    try:
        if args_parsed.last_lines < 0:
            print('The amount of lines must be greater 0.', file=sys.stderr)
            sys.exit(1)
    except: # args_parsed.last_lines either not existed or was not set
        pass 

    return args_parsed


def wanda_start(wanda: WandaStack) -> bool:
    """Starts the Wanda stack and returns the success."""

    try:
        started = wanda.start()   
    except WandaException as err:
        CLI.print_json({'success': False, 'error': err })
        CLI.print_fail(err)
        return False
    else:
        if started:
            CLI.print_info(f'''Started containers: {', '.join(started)}''')
        CLI.print_json({'success': True, 'started_containers': started})
        CLI.print_ok('Wanda completely started.')
    return True
 
        
def wanda_stop(wanda: WandaStack) -> bool:
    """Stops the Wanda stack and returns the success."""

    try:
        stopped = wanda.stop()
    except WandaException as err:
        CLI.print_json({'success': False, 'error': err })
        CLI.print_fail(err)
        return False
    else:
        if stopped:
            CLI.print_info(f'''Stopped containers: {', '.join(stopped)}''')
        CLI.print_json({'success': True, 'stopped_containers': stopped})                        
        CLI.print_ok('Wanda completely stopped.')
    return True


def wanda_status(wanda: WandaStack) -> bool:
    """Prints the status of Wanda stack on screen
    and returns operational state."""

    CLI.print_header('Wanda', margin_bottom=1)
    output = []
    json_obj = {'containers': []}
    for name, status in wanda.container_status.items():
        output.append({'name': name, 
                       'status': CLI.ok if status[0] == status[1] else CLI.error,
                       'status_text': status[0]})
        json_obj['containers'].append({'name': name, 'status': status})
    CLI.print_status(output)    

    volumes_ok = True
    json_obj['missing_volumes'] = []
    for container, mounts in wanda.mandatory_volume_present.items():
        if sorted(mounts[0]) != sorted(mounts[1]):
            volumes_ok = False
            CLI.print_fail(f'''{container} misses the mandatory volumes "{', '.join(mounts[0])}".''')
            json_obj['missing_volumes'].append({'name': name, 'volumes': mounts[0]})

    if wanda.status and volumes_ok:
        CLI.print_ok('\nWanda is operational.')
        json_obj['operational'] = True
    else:
        CLI.print_fail('\nWanda is not operational!')
        json_obj['operational'] = False    
    CLI.print_json(json_obj)
    
    return True if wanda.status and volumes_ok else False
    
    
def hosts_create(hosts: HostsStack, hostgroup: str, envpairs: Dict[str,str], supportfiles: List[str]) -> bool:
    """Creates and starts a host container with the given supportfiles as member of the given host group."""

    if hostgroup in hosts.hostgroups:
        CLI.print_fail(f'Host group "{hostgroup}" already exists!')
        CLI.print_json({'success': False})
        return False
    else:
        sf = SupportFiles(supportfiles)
        if sf.issues:
            for issue in sf.issues:
                CLI.print_fail(f'Error reading support files: {issue}')
            CLI.print_json({'success': False, 'errors': sf.issues})
            return False

        json_obj = {'success': True, 'started': [], 'failed': []}
        for host in sf.result:
            hostname = hosts.create(hostgroup, host, sf.result[host], envpairs)   # ADD ENV RO OVERWRITE
            if hostname:
                CLI.print_ok(f'Host container "{hostname}" started!')
                json_obj['started'].append(hostname)
            else:        
                CLI.print_fail(f'Could not start host container for host "{host}"!')
                json_obj['failed'].append(hostname)
        if json_obj['failed']:
            json_obj['success'] = False
        CLI.print_json(json_obj)
        
    return True


def hosts_start(hosts: HostsStack, hostgroup: str) -> bool:
    """Starts existing host containers of the given host group."""

    if hostgroup in hosts.hostgroups:

        if hosts.start_hostgroup(hostgroup):
            CLI.print_ok(f'Host group "{hostgroup}" started.')
            CLI.print_json({'success': True})
            return True        
        else:
            CLI.print_fail(f'Could not start host group "{hostgroup}!')
            CLI.print_json({'success': False})
            return False
        
    CLI.print_fail(f'Unknown host group "{hostgroup}!')
    CLI.print_json({'success': False})
    return False
        

def hosts_status(hosts: HostsStack, hostgroup: str, details: bool = False) -> bool:
    """Prints the status of the host containers for all/requested host groups on screen
    and returns operational state."""
        
    overall_state = True

    json_obj = {}
        
    for group in hosts.hostgroups:
        
        if hostgroup and group != hostgroup:
            continue
                
        CLI.print_header(group, margin_bottom=1)

        json_obj[group] = []
        output = []

        for host in hosts.filter_containers(filter={'hostgroup': group}, sortkey='hostgroup'):
            
            host_status = {'name': host['name'], 
                        'status': CLI.ok if host['status'] == 'running' else CLI.error,
                        'status_text': host['status']
                        }
            host_json = {'name': host['name'], 'status': host['status']}
            if details:    
                host_status['details'] = {}
                host_json['details'] = {}
                for key in 'container_id', 'container_short_id', 'agent_id', 'hostname', 'hostgroup', 'supportconfig', 'supportfiles', 'provider', 'cluster_type', 'architecture_type', 'ensa_version', 'filesystem_type':
                    value = host[key]
                    host_json['details'][key] = value
                    if isinstance(value, list):
                        value = '\n\t'.join(value.split())
                    host_status['details'][key] = value
                manifest = hosts.get_manifest(host['container'])[1]
                host_json['details']['manifest'] = manifest
                if isinstance(manifest, dict):
                        manifest = '\n'.join([f'{k}: {v}' for k, v in manifest.items()])
                host_status['details']['manifest'] = manifest
                                       
            output.append(host_status)       
            json_obj[group].append(host_json)
            
        CLI.print_status(output)
        CLI.print()
    CLI.print_json(json_obj)
   
    return overall_state
  

def hosts_stop(hosts: HostsStack, hostgroup: str) -> bool:
    """Stops host containers of a given hostgroup."""

    if hostgroup not in hosts.hostgroups:
        CLI.print_fail(f'Host group "{hostgroup}" does not exist!')
        CLI.print_json({'success': False, 'error': f'Host group "{hostgroup}" does not exist!.'})
        return False

    success = True
    json_obj = {'success': True, 'stopped': [], 'failed': []}
    try:
        stopped = hosts.stop_hostgroup(hostgroup)
    except HostsException as err:
        CLI.print_fail(err)
        json_obj['success'] = False
        json_obj['failed'] = stopped
        success = False
    else:
        if stopped:
            CLI.print_info(f'''Stopped containers: {', '.join(stopped)}''')
            json_obj['stopped'] = stopped
        CLI.print_ok(f'Host group "{hostgroup}" completely stopped.')
    CLI.print_json(json_obj)
    
    return success


def hosts_rescan(hosts: HostsStack, hostgroup: str) -> bool:
    """Triggers a reload of the supportfiles of all host containers of a given hostgroup."""

    if hostgroup not in hosts.hostgroups:
        CLI.print_fail(f'Host group "{hostgroup}" does not exist!.')
        CLI.print_json({'success': False, 'error': f'Host group "{hostgroup}" does not exist!.'})
        return False
    hostgroups = [hostgroup]

    success = True
    json_obj = {'success': True, 'failed': {}}
    try:
        results = hosts.rescan_hostgroup(hostgroup)
        for name, result in results.items():
            if not result[0]:
                CLI.print_fail(f'Reloading supportfiles of "{name}" failed: {result[1]}')
                success = False
                json_obj['failed'][name] = result[1]
        if success:
            CLI.print_ok(f'Reloading supportfiles successful.')
    except HostsException as err:
        CLI.print_fail(err)
        json_obj['success'] = False
        json_obj['error'] = str(err)
        success = False
    CLI.print_json(json_obj)
        
    return success


def hosts_remove(hosts: HostsStack, hostgroup: str) -> bool:
    """Removes host containers of a given hostgroup."""

    if hostgroup not in hosts.hostgroups:
        CLI.print_fail(f'Host group "{hostgroup}" does not exist!.')
        CLI.print_json({'success': False, 'error': f'Host group "{hostgroup}" does not exist!.'})
        return False
    hostgroups = [hostgroup]
   
    success = True
    json_obj = {'success': True, 'removed': [], 'failed': []}
    try:
        removed = hosts.remove_hostgroup(hostgroup)
    except HostsException as err:
        CLI.print_fail(err)
        json_obj['success'] = False
        json_obj['failed'] = removed
        success = False
    else:
        if removed:
            CLI.print_info(f'''Removed containers: {', '.join(removed)}''')
            json_obj['removed'] = removed
        CLI.print_ok(f'Host group "{hostgroup}" completely removed.')
    CLI.print_json(json_obj)
        
    return success


def hosts_logs(hosts: HostsStack, containername: str, last_lines: int) -> None:
    """Prints logs of given container."""
    
    if containername not in [e['name'] for e in hosts.containers]:
        CLI.print_fail(f'Container "%{containername}" does not exist!')
        CLI.print_json({'success': False, 'error': f'Container "%{containername}" does not exist!'})
        return False
    
    if last_lines:
        CLI.print_logline(hosts.logs(containername)[-last_lines:])
        json_obj = hosts.logs(containername)[-last_lines:]
    else:
        CLI.print_logline(hosts.logs(containername))
        json_obj = hosts.logs(containername)
    CLI.print_json(json_obj)
    

def checks_list(wanda: WandaStack, details: bool = False, show_all: bool = False) -> None:
    """Prints the checks on screen returned by Wanda."""

    requested_attributes = ['id', 
                            'description', 
                            'group', 
                            'metadata.provider', 
                            'metadata.cluster_type',
                            'metadata.architecture_type',
                            'metadata.ensa_version',
                            'metadata.filesystem_type',
                            'facts[].gatherer',
                            'expectations[].type',
                           ] if details else ['id', 'description', 'group']
    check_counter, supported, unsupported, unknown  = 0, 0, 0, 0

    check_groups = {}

    for check in wanda.checks(requested_attributes):
        if check.group not in check_groups:
                check_groups[check.group] = []
        check_groups[check.group].append(check)

    json_obj = {'checks': {}}
    for check_group in check_groups:
    
        CLI.print_header(check_group, margin_bottom=1)
        output = []
        json_obj['checks'][check_group] = []
        for check in check_groups[check_group]:
            check_counter += 1
            support = getattr(check, 'tcsc_support')
            if support == 'yes':
                supported += 1
                status = CLI.ok
                status_text = 'supported'
            elif support == 'no': 
                unsupported += 1
                status = CLI.error
                status_text = 'not supported'
            else:
                unknown += 1
                status = CLI.warn
                status_text = 'unknown'
            
            if support != 'yes' and not show_all:
                continue
            
            check_output = {'name': f'{check.id} - {check.description}', 
                            'status': status,
                            'status_text': status_text 
                           }
            check_json = {'name': f'{check.id} - {check.description}', 'status': status}
            if details:
                check_output['details'] = {}
                for attribute in ['id', 'description', 'group', 'check_type', 'provider', 'cluster_type', 'architecture_type', 'ensa_version', 'filesystem_type', 'gatherer']:
                    value = getattr(check, attribute)
                    if isinstance(value, list):
                        value = ' '.join(set(value))
                    check_output['details'][attribute] = value
                    check_json[attribute] = value
            output.append(check_output) 
            json_obj['checks'][check_group].append(check_json)
                   
        CLI.print_status(output)
        CLI.print()
                
    CLI.print()
    json_obj['stats'] = {'available:': check_counter, 
                         'supported': supported, 
                         'unsupported': unsupported,
                         'unknown': unknown
                        }
    CLI.print_json(json_obj) 
    CLI.print_info(f'{check_counter} checks available ({supported=} {unsupported=} {unknown=}).')


def checks_show(wanda: WandaStack, check: str) -> None:
    """Shows given check on screen returned by Wanda."""

    requested_attributes = ['id', 
                            'description', 
                            'group', 
                            'metadata.provider', 
                            'metadata.cluster_type',
                            'metadata.architecture_type',
                            'metadata.ensa_version',
                            'metadata.filesystem_type',
                            'facts[].gatherer',
                            'expectations[].type',
                            'remediation'
                           ]
    check_details = wanda.check(check, requested_attributes)
    
    json_obj = []
    output = {}
    if check_details:
        for attribute in ['id', 'description', 'group', 'tcsc_support', 'check_type', 'provider', 'cluster_type', 'architecture_type', 'ensa_version', 'filesystem_type', 'gatherer', 'remediation']:
            value = getattr(check_details, attribute)
            output[attribute] = value
            json_obj.append(f'{attribute}: {value}')
    CLI.print_keyvalue_pairs(output)
    CLI.print_json(json_obj) 


def checks_run(wanda: WandaStack, 
               hosts: HostsStack,
               hostgroup: str, 
               provider: str, 
               check_groups: List[str],
               requested_checks: List[str],
               failure_only: bool) -> bool:
    """Executed the requested checks."""
    
    status_codes = {'passing': CLI.ok,
                    'warning': CLI.warn,
                    'error': CLI.error,
                    'critical': CLI.error
                    }
    json_obj = {}
    
    # Build host target list.
    targets = []
    agent2host = {}
    for host in hosts.filter_containers({'hostgroup': hostgroup}):
        if host['status'] != 'running':
            err_text = f'''Host "{host['name']}" is not running, but has status "{host['status']}".'''
            CLI.print_fail(err_text)
            CLI.print_json({'success': False, 'error': err_text})
            return False
        targets.append(host)
        agent2host[host['agent_id']] = host['name']
    
    # Print overview about hosts to check.
    host_count = len(targets)
    if not targets:
        err_text = f'No hosts for host group "{hostgroup}" found.'
        CLI.print_fail(err_text)
        CLI.print_json({'success': False, 'error': err_text})
        return False
    json_obj['hostgroup'] = hostgroup
    json_obj[hostgroup] = [h['name'] for h in targets]
    CLI.print_info(f'''{host_count} hosts for "{hostgroup}": {', '.join(h['name'] for h in targets)}''')

    # Build effective checks list and print overview.
    checks2run = collections.defaultdict(list)
    available, selected = set(), set()
    remediations = {}
    for check in wanda.checks(['id', 'description', 'group', 'expectations[].type', 'remediation']):
        if check.tcsc_support != 'yes':
            continue
        available.add(check.id)
        if host_count == 1 and check.check_type.startswith('multi'):
            continue
        if check_groups and check.group not in check_groups:
            continue
        if requested_checks and check.id not in requested_checks:
            continue 
        selected.add(check.id)
        checks2run[check.group].append((check.id, check.description, check.check_type)) 
        remediations[check.id] = check.remediation
    skipped = available - selected
    json_obj['checks'] = {'available': list(available),'skipped': list(skipped), 'selected checks':list(selected)}
    CLI.print_info(f'''{len(skipped)} of {len(available)} checks skipped: {', '.join(skipped)}''')
    CLI.print_info(f'''{len(selected)} of {len(available)} checks selected: {', '.join(selected)}''')    
    if not available:
        err_text = 'No checks to run.'
        CLI.print_fail(err_text)
        CLI.print_json({'success': False, 'error': err_text})
        return False
       
    # Walk through check groups and their checks and run them.
    output = []
    for check_group in checks2run:
        print()
        CLI.print_header(check_group)
        check_group_json = []
        for check in checks2run[check_group]:
            
            id, description, check_type = check
            check_results, err = wanda.execute_check(provider, [h['agent_id'] for h in targets], id)

            if err:
                results = [{'name': f'{id} - {description}',
                            'status': CLI.error,
                            'status_text': 'error',
                            'details': {'error': check_results}}]
            else:    
                results = []
                for check_result in json.loads(check_results):
                    
                    # For the paranoid. This should never happen.
                    if id != check_result['check']:
                        results = [{'name': f'{id} - {description}',
                                    'status': CLI.error,
                                    'status_text': 'error',
                                    'details': {'error': '''The check id from the call "{id}" and the result "{check_result['check']}" differ. You found a bug!'''}}]
                    else:             
                        details = {'hostname': agent2host[check_result['agent_id']],
                                'hostgroup': hostgroup,
                                'agent id': check_result['agent_id']}
                        if 'messages' in check_result:
                            details['messages'] = check_result['messages']
                        if status_codes[check_result['result']] != CLI.ok:
                            details['remediation'] = remediations[id]

                        if failure_only and status_codes[check_result['result']] == CLI.ok:
                            continue
                    
                    results.append({'name': f'{id} - {description}',
                                    'status': status_codes[check_result['result']],
                                    'status_text': check_result['result'],
                                    'details': details})

            CLI.print_status(results)
            if results:
                check_group_json.append(results)
        if check_group_json:
            json_obj[check_group] = check_group_json
    CLI.print_json(json_obj)


def wanda_must_run(wanda: WandaStack, autostart: bool) -> None:
    """If requested, starts the Wanda stack and terminates with an error message,
    if Wanda is not operational."""
    
    if not wanda.status:
        if autostart:
            if wanda_start(wanda):
                return
        CLI.print_fail('Wanda is not operational!') 
        sys.exit(4)
                
                
def main() -> None:
        
    global json_output
    
    signal.signal(signal.SIGINT, signal_handler)

    arguments = argument_parse()  

    try:
        config = Config(arguments.config_file)
        wanda = WandaStack(config)

        CLI.no_color = not config.colored_output
        CLI.json = arguments.json_output

        if arguments.selectors == 'wanda':
            
            # tcsc wanda start
            if arguments.wanda_commands == 'start':
                sys.exit(0) if wanda_start(wanda) else sys.exit(4)

            # tcsc wanda stop                
            elif arguments.wanda_commands == 'stop':
                sys.exit(0) if wanda_stop(wanda) else sys.exit(4)
            
            # tcsc wanda status
            elif arguments.wanda_commands == 'status':
                sys.exit(0) if wanda_status(wanda) else sys.exit(4)

        elif arguments.selectors == 'hosts': 
            
            hosts = HostsStack(config)
            
            # tcsc hosts create GROUPNAME [-e|--env KEY=VALUE...] SUPPORTFILE... 
            if arguments.host_commands == 'create':
                wanda_must_run(wanda, config.wanda_autostart)
                sys.exit(0) if hosts_create(hosts, arguments.hostgroup, arguments.envpairs, arguments.supportfiles) else sys.exit(5)

            # tcsc hosts start GROUPNAME
            if arguments.host_commands == 'start':
                wanda_must_run(wanda, config.wanda_autostart)
                sys.exit(0) if hosts_start(hosts, arguments.hostgroup) else sys.exit(5)
                                
            # tcsc hosts status [GROUPNAME]
            elif arguments.host_commands == 'status':
                sys.exit(0) if hosts_status(hosts, arguments.hostgroup, arguments.host_details) else sys.exit(5)

            # tcsc hosts stop GROUPNAME
            elif arguments.host_commands == 'stop':
                    sys.exit(0) if hosts_stop(hosts, arguments.hostgroup) else sys.exit(5)
                    
            # tcsc hosts rescan GROUPNAME
            elif arguments.host_commands == 'rescan':
                    sys.exit(0) if hosts_rescan(hosts, arguments.hostgroup) else sys.exit(5)
                    
            # tcsc hosts remove GROUPNAME
            elif arguments.host_commands == 'remove':
                    sys.exit(0) if hosts_remove(hosts, arguments.hostgroup) else sys.exit(5)

            # tcsc hosts logs [-l LINES] CONTAINERNAME 
            elif arguments.host_commands == 'logs':
                hosts_logs(hosts, arguments.containername, arguments.last_lines)
                sys.exit(0) 
        
        elif arguments.selectors == 'checks': 
            wanda_must_run(wanda, config.wanda_autostart)
            hosts = HostsStack(config)
                            
            # tcsc checks list [-d|--details] [-a|--all]
            if arguments.checks_commands == 'list':
                checks_list(wanda, arguments.check_details, arguments.show_all)
                sys.exit(0)  
                
            # tcsc checks show CHECK
            if arguments.checks_commands == 'show':
                checks_show(wanda, arguments.check)
                sys.exit(0) 
                
            # tcsc checks run [-r|--response] [-p|--provider PROVIDER] ([-g|--group GROUP]... | [-c|--checks CHECK]...) GROUPNAME
            if arguments.checks_commands == 'run':
                sys.exit(0) if checks_run(wanda, hosts, 
                                          arguments.hostgroup, 
                                          arguments.provider, 
                                          arguments.check_groups,
                                          arguments.requested_checks,
                                          arguments.failure_only,
                                         ) else sys.exit(6)
    
    except ConfigException as err:
        CLI.print_fail(err, file=sys.stderr)
        sys.exit(1)
    except docker.errors.DockerException as err:
        CLI.print_fail(f'Docker error: {err}', file=sys.stderr)
        sys.exit(2)
    except WandaException as err:
        CLI.print_fail(f'Wanda error: {err}', file=sys.stderr)
        sys.exit(3)
    except HostsException as err:
        CLI.print_fail(f'Hosts error: {err}', file=sys.stderr)
        sys.exit(5)
    except CheckException as err:
        CLI.print_fail(f'Check error: {err}', file=sys.stderr)
        sys.exit(6) 
    except BrokenPipeError:  # https://docs.python.org/3/library/signal.html#note-on-sigpipe
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(1)
    
    # Bye.
    CLI.print_fail('An unknown error ocurred!')
    sys.exit(9)

    
if __name__ == '__main__':
    main()
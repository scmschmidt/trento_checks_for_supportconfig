#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Interacts with Wanda using its API (https://www.trento-project.io/wanda/).

ToDo:
-----
    - Switch from polling to callback
    - Implement support for x-csrf-token

    
Changelog:
----------
08.12.2022      v0.1        - and so it begins...
12.12.2022      v0.2beta    - first working version, but not fully tested
                              for lack of an environment
13.02.2023      v0.3        - removed beta status
                            - added support for authorization keys (-a|-A)
13.02.2023      v0.4        - added support for fetching authorization keys from web interface (-f|-F)
14.02.2023      v0.5        - print dot when waiting for a still running test 
30.03.2023      v0.6        - bug fixed in Rabbiteer.execute_check(): API change in reporting a not (yet) found execution?
30.10.2023      v0.7        - Latest changes in the API require the presence of the key `target_type` in the check execution request, 
                              which must match the value in the check. Fetching the check catalog now and add the key to the request.
                            - Also implementing "healthz" and "readyz".
                            - Issue: For some reason starting an execution requires explicitly "v1" in the uri. Its a bug.
30.10.2023      v0.7.1      - Fixed two typos and removed the "v1" from the URI to start executions. Trento Core Team has fixed the issue.
10.04.2024      v0.8        - Removed -p in favor of -e which allows setting newly available environment parameters.
12.04.2024      v0.9        - Some minor code cleaning.
                            - Reworked Rabbiteer class (execute_check) to use exceptions and do not terminate directly. 
                              This was necessary for integration into the project https://github.com/scmschmidt/trento_checks_for_supportconfig.
                            - Running dots can now be disabled (--no-progress) and are printed to stderr to not disrupt output processing.  
                            - Increased polling interval on Rabbiteer.execute_check() from 0.5 to 1s.
                            - Support for -c CHECK for ListChecks.
20.11.2024      v1.0        - Rework check execution to get unambiguous results (`critical`, `warning`, `passing`) for each check and not only
                              a summarized overall worst result. This means, that for each check first the expectation type gets evaluated
                              (`ListChecks`) and depending on the type, one or multiple execution calls get fired (`expect_same` is one call for
                              all agents and `expect` and `expect_enum` are separate calls per agent for the check).
                            - Add --json and --brief to ExecuteCheck. The option --json is required for the project
                              https://github.com/scmschmidt/trento_checks_for_supportconfig.
20.11.2024      v1.1        - Moved formatting of ExecuteCheck output to function evaluate_check_results(), so it can be called from tcsc
                              (https://github.com/scmschmidt/trento_checks_for_supportconfig).
06.01.2024      v1.2        - Bug fix: wrong output in environment error messages
                            - Support for environment key `hana_scenario'.
                            - Dependency check between environment keys added.
"""

import argparse
import logging
import os
import requests
import signal
import sys
import textwrap
import time
import json
import uuid
from typing import List, Dict, Any


__version__ = '1.2'
__author__ = 'soeren.schmidt@suse.com'


class Rabbiteer():
    """Class to communicate with Wanda's API."""

    def __init__(self, baseurl: str, access_key: str = None, credential: str = None) -> None:
        self.baseurl = baseurl
        self.access_key = access_key
        self.trento_credential = credential

    def make_request(self, endpoint: str, post_data: dict = None) -> None:
        """Makes a request to the endpoint and expects a JSON response.
        The response is available in self.response.
        If post_data is given, a POST otherwise a GET request is done.
        
        If the HTTP connection fails, an exception will be raised.
        
        If the Wanda API requires authentication, either the access key
        or credentials to the Trento web interface must be given to retrieve
        it.
        """

        # Retrieve access key from Trento, if required.
        if self.trento_credential:       
            try:
                response = requests.post(f'''{self.trento_credential['url']}/api/session''', 
                                     data={'username': self.trento_credential['username'],  
                                           'password': self.trento_credential['password']},
                                     timeout=10)
            except Exception as err:
                raise RabbiteerConnectionError(f'Connection error:{err}')

            if not response.ok:
                raise RabbiteerTrentoError(f'Could not authenticate against Trento. Error:{response.status_code}\n{response.text}')
            else:
                try:
                    self.access_key = response.json()['access_token']
                except Exception as err:
                    raise RabbiteerTrentoError(f'Could not retrieve access key from Trento: {err}')  

        # Build the headers
        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        if self.access_key:
            headers['Authorization'] = f'Bearer {self.access_key}'
        url = f'{self.baseurl}{endpoint}'

        try:
            if post_data:
                self.response = requests.post(url, headers=headers, data=post_data)
                logging.debug(f'POST REQUEST\n\tURL: {url}\n\theaders: {headers}\n\tdata: {post_data}')
            else: 
                self.response = requests.get(url, headers=headers)
                logging.debug(f'GET REQUEST\n\tURL: {url}\n\theaders: {headers}\n\thttp status: {self.response.status_code}\n\tresponse: {self.response.text}')
        except Exception as err:
            raise RabbiteerConnectionError(f'Error connecting to "{url}": {err}')

    def _http_status_err(self) -> None:
        """Raises RabbiteerConnectionError exception if the request returned with a error HTTP status code."""
        if not self.response.ok:
            raise RabbiteerConnectionError(f'Failed with status code: {self.response.status_code}\n{self.response.text}')

    def list_executions(self) -> dict:
        """Returns executions from Wanda."""

        self.make_request('/api/checks/executions')
        self._http_status_err() 
        return self.response.json()

    def list_catalog(self) -> dict:
        """Returns check catalog from Wanda."""

        self.make_request('/api/checks/catalog')
        self._http_status_err() 
        return self.response.json()
    
    def health(self) -> dict:
        """Returns health of Wanda."""

        self.make_request('/api/healthz')
        self._http_status_err() 
        return self.response.json()

    def readiness(self) -> dict:
        """Returns readiness of Wanda."""

        self.make_request('/api/readyz')
        self._http_status_err() 
        return self.response.json()

    def execute_checks(self, 
                       agent_ids: List[str], 
                       environment: Dict[str, str], 
                       check_ids: List[str], 
                       timeout: int = None,
                       running_dots: bool = True
                      ) -> List[Any]:
        """Execute checks on agents and returns the results as list.
        Raises exceptions if anything goes wrong or the result is not as expected. 
        Each check is treated separately and depending on the expectation type one 
        (`expect_same`) or multiple execution calls (`expect` and `expect_enum`)
        get fired.
        """

        # Get check catalog.
        catalog = self.list_catalog()['items']

        # We need to fetch keys from the check's metadata, which have to be part of the request.
        # and we extract the expectation type.
        checks_metadata = {}
        checks_expectationtype = {}
        responses = []
        for check in catalog:
            if check['id'] in check_ids:
                metadata = {}
                try:
                    for mandatory_key in ['target_type']:
                       metadata[mandatory_key] = check['metadata'][mandatory_key]
                except:
                    raise RabiteerMetadataError(f'''Mandatory key "{mandatory_key}" is not part of metadata of check {check['id']}.\nThis is a bug in the check.''')
                checks_metadata[check['id']] = metadata
                try:               
                    checks_expectationtype[check['id']] = check['expectations'][0]['type']
                except:
                    raise RabiteerMetadataError(f'''Could not retrieve execution type of check {check['id']}.''')
        
        # Walk through each requested check.
        for check_id in check_ids:
            data = {'env': environment,
                'execution_id': None,
                'group_id': str(uuid.uuid4()),
                'targets': []
               }
            data.update(checks_metadata[check_id])

            # If we have a `expect_same` check, we execute a single call for
            # all agents,...
            if checks_expectationtype[check_id] == 'expect_same':
                for agent_id in agent_ids:
                    data['targets'].append({'agent_id': agent_id, 'checks': [check_id]})
                data['execution_id'] = str(uuid.uuid4())                    
                responses.append(self._call_execute(data, timeout=timeout, running_dots=running_dots))
            # ... otherwise one call per agent.
            else:
                for agent_id in agent_ids:
                    data['targets'] = [{'agent_id': agent_id, 'checks': [check_id]}]
                    data['execution_id'] = str(uuid.uuid4())
                    responses.append(self._call_execute(data, timeout=timeout, running_dots=running_dots))
             
        return responses

    def _call_execute(self, data: Dict[str, Any],
                            timeout: int = None,
                            running_dots: bool = True) -> dict:
        """Starts a single execution call and polls for the execution to be finished.
        Raises exceptions in case of errors otherwise returns a response object
        """

         # Start execution.
        self.make_request('/api/checks/executions/start', post_data=json.dumps(data))
        
        # Check if the check does not exist.
        if self.response.status_code == 422:
            detail = self.response.json().get('error', {}).get('detail')
            if detail and detail == 'no_checks_selected':
                raise RabbiteerRepsonseError(f'Check does not exist! Header: {data}', None)
            raise RabbiteerRepsonseError(f'Wanda response: 422 - Unprocessable content. Header: {data}', None)
        else:
            self._http_status_err()  

        execution_id = data['execution_id']
        endpoint = f'/api/checks/executions/{execution_id}'
        start_time = time.time()
        running = True
        first_dot = False
        while running:
            self.make_request(endpoint)

            # Check if execution might not yet exist.
            if self.response.status_code == 404:
                error_titles = [e['title'] for e in self.response.json()['errors'] if 'title' in e.keys()]
                if 'Not Found' in error_titles:
                    logging.debug(f'Execution {execution_id} not yet available...\n\t{self.response.text}')
                    if timeout and time.time() - start_time > timeout:
                        raise RabbiteerTimeOut(f'Execution {execution_id} did not show up in time (within {timeout}s)!')
                    time.sleep(.5)
                    continue

            # Terminate if we encounter an unknown error response. 
            self._http_status_err() 

            # Check if execution has been completed yet.
            status = self.response.json()['status']
            if status == 'running':
                if running_dots:
                    print('.', end='', flush=True, file=sys.stderr)
                    first_dot = True
                
                logging.debug(f'Execution {execution_id} still running...\n\t{self.response.text}')
                if timeout and time.time() - start_time > timeout:
                    raise RabbiteerTimeOut(f'Execution {execution_id} did not finish in time (within {timeout}s)!')
                time.sleep(1)
                continue
            elif status == 'completed':
                if running_dots and first_dot:
                    print('', flush=True, file=sys.stderr) 
                logging.debug(f'Execution {execution_id} has been completed.\n\t{self.response.text}')
                running = False
            else:
                raise RabbiteerRepsonseError(f'Execution {execution_id} returned an unknown status: {status}', self.response.text)

        logging.debug(f'Response of {execution_id}: {self.response.text}')
        return self.response.json()


class RabbiteerConnectionError(Exception):
    pass


class RabbiteerTrentoError(Exception):
    pass


class RabiteerMetadataError(Exception):
    pass    

    
class RabbiteerRepsonseError(Exception):
    
    def __init__(self, message, response):
        message_redone = [message]
        if response:
            for error in json.loads(response)['errors']:
                message_redone.append(f'''{error['title']}: {error['detail']}: {error['source']}''')
        super().__init__('\n'.join(message_redone))


class RabbiteerTimeOut(Exception):
    pass


class ArgParser(argparse.ArgumentParser):

    def format_help(self) -> str:
        """Prints full help message."""

        prog = os.path.basename(sys.argv[0])
        text = f'''
                Usage:  {prog} -h|--help
                        {prog} [-d|--debug] [-r|--raw] [-a KEY|-A KEYFILE|-f CRED|-F CREDFILE] URL ListExecutions [SCOPE]
                        {prog} [-d|--debug] [-r|--raw] [-a KEY|-A KEYFILE|-f CRED|-F CREDFILE] URL ExecuteCheck -e ENV_PARAM...
                        {len(prog) * ' '} -t|--target TARGET... -c|--check CHECK... [--timeout TIMEOUT] [--json] [--brief]
                        {prog} [-d|--debug] [-r|--raw] [-a KEY|-A KEYFILE|-f CRED|-F CREDFILE] URL ListChecks [-c|--check CHECK...]
                        {prog} [-d|--debug] [-r|--raw] [-a KEY|-A KEYFILE|-f CRED|-F CREDFILE] URL Health
                        {prog} [-d|--debug] [-r|--raw] [-a KEY|-A KEYFILE|-f CRED|-F CREDFILE] URL Ready

                v{__version__}
            
                Interacts with Wanda using its API (https://www.trento-project.io/wanda/).

                Options:

                    -h, --help      print this help text
                    -d, --debug     enables debug output written to stderr
                    -r, --raw       prints raw response (JSON) instead evaluation
                    -a KEY          API access token
                    -A KEYFILE      file with the API access token
                    -f CRED         credentials to fetch API access token from Trento
                    -F CREDFILE     file with the credentials to fetch API access token from Trento
                    
                    CREDENTIALS must be a JSON string: {{ "url": "URL", "username": "USER", "password": "PASSWORD" }}
                    like {{ "url": "http://20.8.99.2:80", "username": "admin", "password": "456Hsd3a&5" }}). 

                Arguments: 

                    URL             URL to Wanda including the port (e.g http//localhost:4000)
                    ListExecutions  list executions (for options and arguments see below) 
                    ExecuteCheck    execute checks on target hosts (for options and arguments see below)
                    ListChecks      list all available checks
                    Health          gives the health status of Wanda
                    Ready           gives the readiness status of Wanda

                Command Options and Arguments:

                    ListExecutions:

                        Lists all executions Wanda currently has.
                        Use SCOPE to restrict the output.

                        SCOPE       One of: all running completed failed unknown
                                    (has no effect, if raw output is requested) 
                    
                    ExecuteCheck:

                        Executes checks for the platform on target hosts, waits for
                        the execution to be finished and prints the results.
                
                        -e, --env ENV_PARAM...      sets environment parameter (https://www.trento-project.io/wanda/specification.html#evaluation-scope)
                                                        provider            one of: azure, aws, gcp, kvm, nutanix, vmware, default;   Default: default
                                                        cluster_type        one of: hana_scale_up, hana_scale_out, ascs_ers;   Default: -
                                                        hana_scenario	    one of: performance_optimized, cost_optimized, unknown;   Default: -
                                                                            (must be set, if cluster_type is hana_scale_up)
                                                        architecture_type   one of: classic, angi;   Default: -
                                                                            (must be set, if cluster_type is hana_scale_up or hana_scale_out)
                                                        ensa_version	    one of: ensa1, ensa2, mixed_versions
                                                                            (must be set, if cluster_type is ascs_ers)
                                                        filesystem_type     one of: resource_managed, simple_mount, mixed_fs_types   Default: -
                                                                            (must be set, if cluster_type is ascs_ers)
                        -c, --check CHECK...        Trento check id (e.g. 21FCA6)
                        -t, --target                agent uuid of target host (e.g. )
                        --timeout TIMEOUT           timeout in seconds waiting for an execution to appear or to complete 
                        --no-progress               disables progress dots during check execution
                        --json                      print results as JSON string
                        --brief                     print only check id, agent id and result

                    ListChecks:
                    
                        Lists all checks present in Wanda. 
                        Use -c|--check CHECK to limit the output.
                    
                        -c|--check CHECK...         Trento check id (e.g. 21FCA6)
                        
                Exit codes:

                    0   Everything went fine. 
                    1   Issues talking to the API.
                    2   Issues with the command line parameters.
                    3   Problems with the response from the API.
                    4   Timeout reached.

                Examples:

                    Check the health of Wanda:                  rabbiteer.py http://localhost:4000 Health
                    List all available checks:                  rabbiteer.py http://localhost:4000 ListChecks
                    List all available checks (JSON dump):      rabbiteer.py -r http://localhost:4000 ListChecks
                    Execute a check for a (azure) host:         rabbiteer.py http://localhost:4000 ExecuteCheck -e provider=azure -c 156F64 -t b651491b-904d-5448-9350-fe817c1f2c6e

                '''
        return textwrap.dedent(text)


def signal_handler(sig: int, frame: Any) -> None:
    sys.exit(0)

def argument_parse() -> argparse.Namespace:
    """Evaluates the command line arguments."""

    parser = ArgParser(prog=os.path.basename(sys.argv[0]), 
                       #usage='\n'.join(usage),
                       description='Executes commands using the Wanda API.',
                       add_help=False,
                       epilog='')

    # Global flags and arguments.   
    parser.add_argument('-h', '--help', 
                        dest='help',
                        action='help',
                        default=argparse.SUPPRESS)                                 
    parser.add_argument('-d', '--debug',
                        dest='debug',
                        action='store_true',
                        required=False)      
    parser.add_argument('-r', '--raw',
                        dest='raw_output',
                        action='store_true',
                        required=False)
    parser.add_argument('url', 
                        metavar='URL',
                        type=str)
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-a',
                       dest='access_key',
                       action='store',
                       required=False)  
    group.add_argument('-A',
                       dest='access_keyfile',
                       action='store',
                       required=False)
    group.add_argument('-f',
                       dest='credential',
                       action='store',
                       required=False)  
    group.add_argument('-F',
                       dest='credential_file',
                       action='store',
                       required=False)
    
    subparsers = parser.add_subparsers(dest='command')
    
    # Command: ListExecutions
    parser_list_executions = subparsers.add_parser('ListExecutions', usage=None)
    parser_list_executions.add_argument('scope',
                                         action='store',
                                         choices=['all', 'running', 'completed', 'failed', 'unknown'], 
                                         type=str)                                      
    
    # Command: ExecuteCheck
    parser_execute_check = subparsers.add_parser('ExecuteCheck')
    parser_execute_check.add_argument('--no-progress',
                                      dest='progress_dots',
                                      action='store_false',
                                      required=False)
    parser_execute_check.add_argument('-e', '--env',
                                      dest='environment',
                                      action='append',
                                      required = False)
    parser_execute_check.add_argument('-c', '--check',
                                      dest='checks',
                                      action='append',
                                      required = True,
                                      nargs='+',
                                      type=str)
    parser_execute_check.add_argument('-t', '--target',
                                      dest='agents',
                                      action='append',
                                      required = True,
                                      nargs='+',
                                      type=str)
    parser_execute_check.add_argument('--timeout',
                                      dest='timeout',
                                      action='store',
                                      required = False,
                                      type=int)
    parser_execute_check.add_argument('--json',
                                      dest='json_output',
                                      action='store_true',
                                      required = False) 
    parser_execute_check.add_argument('--brief',
                                      dest='brief',
                                      action='store_true',
                                      required = False)   

    # Command: ListChecks
    parser_list_checks = subparsers.add_parser('ListChecks')
    parser_list_checks.add_argument('-c', '--check',
                                    dest='checks',
                                    action='append',
                                    required = False,
                                    nargs='+',
                                    type=str) 
    # Command: Health
    parser_health = subparsers.add_parser('Health')
    
    # Command: Ready
    parser_ready = subparsers.add_parser('Ready')

    # Parse arguments.
    args_parsed = parser.parse_args()

    # Subparser cannot be forced to be required before Python 3.7.0a2 (introduction of 'required').
    # Therefore the presence of the command is not enforced.
    if not args_parsed.command:
        message = f'''
        usage: {os.path.basename(sys.argv[0])} [-h] [-d] [-r]
                             URL {{ListExecutions,ExecuteCheck,ListChecks}} ...
        {os.path.basename(sys.argv[0])}: error: the following arguments are required: {{ListExecutions,ExecuteCheck,ListChecks}}
        '''
        print(textwrap.dedent(message), file=sys.stderr)
        sys.exit(2)

    # Check and rework environment parameters.
    env = {}
    if 'environment' in args_parsed and args_parsed.environment:
        for parameter in args_parsed.environment:
            try:
                key, value = parameter.split('=', maxsplit=1)
            except ValueError:
                print(f'environment parameters must have the form "key=value", but got: {parameter}', file=sys.stderr)
                sys.exit(2)
                                
            if key == 'provider':
                if value not in ['azure', 'aws', 'gcp', 'kvm', 'nutanix', 'vmware', 'default']:
                    print(f'invalid value for "provider": {value}', file=sys.stderr)
                    sys.exit(2)
            elif key == 'cluster_type':
                if value not in ['hana_scale_up', 'hana_scale_out', 'ascs_ers']:
                    print(f'invalid value for "cluster_type": {value}', file=sys.stderr)
                    sys.exit(2)
            elif key == 'hana_scenario':
                if value not in ['performance_optimized', 'cost_optimized', 'unknown']:
                    print(f'invalid value for "hana_scenario": {value}', file=sys.stderr)
                    sys.exit(2)
            elif key == 'architecture_type':
                if value not in ['classic', 'angi']:
                    print(f'invalid value for "architecture_type": {value}', file=sys.stderr)
                    sys.exit(2)
            elif key == 'ensa_version':
                if value not in ['ensa1', 'ensa2', 'mixed_versions']:
                    print(f'invalid value for "ensa_version": {value}', file=sys.stderr)
                    sys.exit(2)
            elif key == 'filesystem_type':
                if value not in ['resource_managed', 'simple_mount', 'mixed_fs_types']:
                    print(f'invalid value for "filesystem_type": {value}', file=sys.stderr)
                    sys.exit(2)
            else:
                print(f'invalid environment parameter: {key}', file=sys.stderr)
                sys.exit(2)
            env[key] = value
        if 'cluster_type' in env:                 
            if env['cluster_type'] == 'hana_scale_up':
                if 'hana_scenario' not in env:
                        print('"hana_scenario" must be set, if "cluster_type" is "hana_scale_up"', file=sys.stderr)
                        sys.exit(2)
            if env['cluster_type'] == 'hana_scale_up' or env['cluster_type'] == 'hana_scale_out':    
                if 'architecture_type' not in env:
                        print('"architecture_type" must be set, if "cluster_type" is "hana_scale_up" or "hana_scale_out"', file=sys.stderr)
                        sys.exit(2)
            if env['cluster_type'] == 'ascs_ers':    
                if 'ensa_version' not in env:
                        print('"ensa_version" must be set, if "cluster_type" is "ascs_ers"', file=sys.stderr)
                        sys.exit(2)
                if 'filesystem_type' not in env:
                        print('"filesystem_type" must be set, if "cluster_type" is "ascs_ers"', file=sys.stderr)
                        sys.exit(2)                                                            
            
    if 'provider' not in env:
        env['provider'] = 'default'
    args_parsed.environment = env
        
    # Set debugging.
    if args_parsed.debug:
        logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(asctime)s\n%(message)s\n---')
        
    # Retrieving access key, if file was given.
    if args_parsed.access_keyfile:
        try:
            with open(args_parsed.access_keyfile, 'r') as f:
                args_parsed.access_key = f.read().strip()
        except Exception as err:
            print(f'Error reading access key from "{args_parsed.access_keyfile}": {err}')
            sys.exit(2)
            
    # Retrieving Trento credentials, if file was given.
    if args_parsed.credential_file:
        try:
            with open(args_parsed.credential_file, 'r') as f:
                args_parsed.credential = f.read()
        except Exception as err:
            print(f'Error reading credentials from "{args_parsed.credential_file}": {err}')
            sys.exit(2)
            
    # Loading credentials as JSON and checking completeness. 
    if args_parsed.credential:
        try:
            args_parsed.credential = json.loads(args_parsed.credential)
        except Exception as err:
            print(f'Error reading credentials: {err}')
            sys.exit(2)
        missing = {'url', 'username', 'password'} - set(args_parsed.credential)
        if missing:
            print(f'''Credentials miss: {', '.join(missing)}''')
            sys.exit(2)

    return args_parsed

def unknown_response(response: dict, error: Exception):
    """Prints response and error message and terminates with exit code 3."""

    print(f'Could not evaluate response:\n{response}\n\nError: {error}', file=sys.stderr)
    sys.exit(3)
    
def prune_object(obj: Any):
    """Recursively walks through an object (list or dict) and deletes everything except
    dictionary keys with are in the valid key list. This is used to prune the complex 
    response object from a check execution to a few needed entries."""

    valid_keys = ['result', 'message', 'failure_message', 'return_value', 'agent_id', 'checks', 'check_id']
    
    if isinstance(obj, dict):
        for k, v in obj.copy().items():
            if isinstance(v, dict) or isinstance(v, list):
                prune_object(v)
                if not v:
                    del(obj[k])
            else:
                if k not in valid_keys:
                    del(obj[k])
    elif isinstance(obj, list):
        for e in list(obj):
            if isinstance(e, dict) or isinstance(e, list):
                prune_object(e)
                if not e:
                    obj.remove(e)
            else:
                obj.remove(e)

def evaluate_check_results(responses: List[Any], brief: bool, json_output: bool) -> str:
    """Takes responses list from Rabbiteer.execute_checks() and formats them to a (JSAON ) string"""
    
    try:
        # Walk trough all the responses of the execution requests.
        results = []
        for response in responses:
            
            # With one check per execution request, the `check_results`
            # list has only one element.
            check_result = response['check_results'][0]
            
            # Walk through the agent's results.    
            for agents_check_result in check_result['agents_check_results']:
                result = {'check': check_result['check_id'],
                            'agent_id': agents_check_result['agent_id'],
                            'result': check_result['result']
                            }
                if not brief:
                    result['execution_id'] = response['execution_id']

                    # Collect all (error) messages.
                    messages = []
                    if 'message' in agents_check_result:
                        messages.append(agents_check_result['message'])                           
                    for fact in agents_check_result['facts']:
                        if 'message' in fact:
                            messages.append(fact['message'])                                
                    if 'expectation_evaluations' in agents_check_result:
                        for evaluation in agents_check_result['expectation_evaluations']:
                            if 'failure_message' in evaluation :
                                messages.append(evaluation['failure_message'])
                    if messages:
                        result['messages'] = '; '.join(messages)
                        
                    # Add error type if present.
                    if 'type' in agents_check_result:
                        result['type'] = agents_check_result['type']
                
                results.append(result)                                
                        
        # print "human-readable" line or JSON string.
        if json_output:
            output_string = json.dumps(results)
        else:
            output_string = ''
            for result in results:
                for key, value in result.items():
                    output_string += f'{key}="{value}" '
                output_string += '\n'  
        return  output_string

    except Exception as err:
        unknown_response(responses, err)


def main():

    signal.signal(signal.SIGINT, signal_handler)

    arguments = argument_parse()
    connection = Rabbiteer(arguments.url, arguments.access_key, arguments.credential)
    try:
        
        # Command: ExecuteCheck
        if arguments.command == 'ExecuteCheck':

            # Start check(s) execution.
            responses = connection.execute_checks(sum(arguments.agents, []), arguments.environment, sum(arguments.checks, []),
                                                 timeout=arguments.timeout,
                                                 running_dots=arguments.progress_dots
                                                )
            
            # Print full responses or evaluation.
            if arguments.raw_output:
                print(json.dumps(responses))    
            else:   
                print(evaluate_check_results(responses, brief=arguments.brief, json_output=arguments.json_output))            
                    
        # Command: ListExecutions
        elif arguments.command == 'ListExecutions':
            
            # Retrieve Executions.
            response = connection.list_executions()

            # Print full response or evaluation.
            if arguments.raw_output:
                print(json.dumps(response))
            else:
                try:
                    count = 0
                    for item in response['items']:
                        if item['status'] != arguments.scope and arguments.scope != 'all':
                            continue
                        count += 1
                        print(f'''{item['execution_id']}: {item['status']}\n    start : {item['started_at']}\n    end   : {item['completed_at']}\n    group : {item['group_id']}''')
                        for targets in item['targets']:
                            print(f'''    target: {targets['agent_id']}   checks: {' '.join(targets['checks'])}''') 
                    print(f'''\n{len(response['items'])} execution(s) found, {count} listed.''')
                except Exception as err:
                    unknown_response(response, err)

        # Command: ListChecks
        elif arguments.command == 'ListChecks':
        
            # Retrieve checks.
            response = connection.list_catalog()
            
            try:
                # Filter checks.
                if arguments.checks:
                    requested_checks = sum(arguments.checks, [])
                    new_response = {'items': []}
                    for check in response['items']:
                        if check['id'] in requested_checks:
                            new_response['items'].append(check)  
                    response = new_response
                    
                # Print full response or evaluation.
                if arguments.raw_output:
                    print(json.dumps(response))
                else:
                    checks = response['items']
                    for check in checks:
                        print(f'''{check['id']} - {check['name']} ({check['group']})''')
                    print(f'\n{len(checks)} check(s) found.')
            except Exception as err:
                print(f'Could not evaluate response:\n{response}\n\nError: {err}', file=sys.stderr)
                sys.exit(3)
                
        # Command: Health
        elif arguments.command == 'Health':
        
            # Retrieve health.
            response = connection.health()

            # Print full response or evaluation.
            if arguments.raw_output:
                print(json.dumps(response))
            else:
                try:
                    for key, value in response.items():
                        print(f'{key}: {value}')
                except Exception as err:
                    print(f'Could not evaluate response:\n{response}\n\nError: {err}', file=sys.stderr)
                    sys.exit(3)

        # Command: Ready
        elif arguments.command == 'Ready':
        
            # Retrieve health.
            response = connection.readiness()

            # Print full response or evaluation.
            if arguments.raw_output:
                print(json.dumps(response))
            else:
                try:
                    print(f'''{response['ready']}''')
                except Exception as err:
                    print(f'Could not evaluate response:\n{response}\n\nError: {err}', file=sys.stderr)
                    sys.exit(3)

    # Catch Rabbiteer exceptions.
    except (RabbiteerConnectionError, RabbiteerTrentoError) as err:
        print(err, file=sys.stderr)
        sys.exit(1)  
    except RabiteerMetadataError as err:
        print(err, file=sys.stderr)
        sys.exit(2)  
    except RabbiteerRepsonseError as err:
        print(err, file=sys.stderr)
        sys.exit(3)  
    except RabbiteerTimeOut as err:
        print(err, file=sys.stderr)
        sys.exit(4) 

    sys.exit(0)


if __name__ == '__main__':
    main()

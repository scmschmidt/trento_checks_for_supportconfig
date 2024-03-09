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
03.03.2024      v0.8        - Introduced Rabbiteer exception classes, reworked Rabbiteer class to throw exceptions and moved
                              all printing into a main() by catching the exceptions.
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


__version__ = '0.8'
__author__ = 'soeren.schmidt@suse.com'


class Rabbiteer():
    """Class to communicate with Wanda's API."""

    def __init__(self, baseurl, access_key=None, credential=None):
        self.baseurl = baseurl
        self.access_key = access_key
        self.trento_credential = credential

    def make_request(self, endpoint, post_data=None):
        """Makes a request to the endpoint and expects a JSON response.
        The response is available in self.response.
        If post_data is given, a POST else a GET request is done.
        
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

    def _http_status_err(self):
        """Raises RabbiteerConnectionError exception if the request returned with a error HTTP status code."""
        
        if not self.response.ok:
            raise RabbiteerConnectionError(f'Failed with status code: {self.response.status_code}\n{self.response.text}')

    def list_executions(self):
        """Returns executions from Wanda."""

        self.make_request('/api/checks/executions')
        self._http_status_err() 
        return self.response.json()

    def list_catalog(self):
        """Returns check catalog from Wanda."""

        self.make_request('/api/checks/catalog')
        self._http_status_err() 
        return self.response.json()
    
    def health(self):
        """Returns health of Wanda."""

        self.make_request('/api/healthz')
        self._http_status_err() 
        return self.response.json()

    def readiness(self):
        """Returns readiness of Wanda."""

        self.make_request('/api/readyz')
        self._http_status_err() 
        return self.response.json()

    def execute_checks(self, agent_ids, provider, check_ids, timeout=None, running_dots=True):
        """Execute checks for provider on agents and returns 
        the result as dictionary.
        Terminates if anything goes wrong or the result is not as expected. 
        """

        # We need to fetch keys from the check's metadata, which have to be part of the request.
        metadata = {}
        for check in self.list_catalog()['items']:
            if check['id'] in check_ids:
                current_metadata = {}
                try:
                    for mandatory_key in ['target_type']:
                        current_metadata[mandatory_key] = check['metadata'][mandatory_key]
                except:
                    raise RabiteerMetadataError(f'''Mandatory key "{mandatory_key}" is not part of metadata of check {check['id']}.\nThis is a bug in the check.''')
                if metadata:
                    if metadata != current_metadata:
                        raise RabiteerMetadataError(f'''If multiple checks are executed, the metadata must be identical!\n"{current_metadata}" of check {check['id']} differs from the metadata of the previous checks "{metadata}".''')
                else:
                    metadata = current_metadata

        execution_id = str(uuid.uuid4())
        data = {'env': {'provider': provider},
                'execution_id': execution_id,
                'group_id': str(uuid.uuid4()),
                'targets': []
               }
        data.update(metadata)
        for agent_id in agent_ids:
            data['targets'].append({'agent_id': agent_id, 'checks': check_ids})

        # Start execution.
        self.make_request('/api/checks/executions/start', post_data=json.dumps(data))

        # Check if the check does not exist.
        if self.response.status_code == 422:
            detail = self.response.json().get('error', {}).get('detail')
            if detail and detail == 'no_checks_selected':
                raise RabbiteerRepsonseError('None of the checks exist!', None)
            raise RabbiteerRepsonseError('Wanda response: 422 - Unprocessable content', None)
        else:
            self._http_status_err()  

        endpoint = f'/api/checks/executions/{execution_id}'
        start_time = time.time()
        running = True
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
                    print('.', end='', flush=True) 
                
                logging.debug(f'Execution {execution_id} still running...\n\t{self.response.text}')
                if timeout and time.time() - start_time > timeout:
                    raise RabbiteerTimeOut(f'Execution {execution_id} did not finish in time (within {timeout}s)!')
                time.sleep(.5)
                continue
            elif status == 'completed':
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

    def format_help(self):
        """Prints full help message."""

        prog = os.path.basename(sys.argv[0])
        text = f'''
                Usage:  {prog} -h|--help
                        {prog} [-d|--debug] [-r|--raw] [-a KEY|-A KEYFILE|-f CRED|-F CREDFILE] URL ListExecutions [SCOPE]
                        {prog} [-d|--debug] [-r|--raw] [-a KEY|-A KEYFILE|-f CRED|-F CREDFILE] URL ExecuteCheck -p|--provider PROVIDER -t|--target TARGET... -c|--check CHECK... [--timeout TIMEOUT]
                        {prog} [-d|--debug] [-r|--raw] [-a KEY|-A KEYFILE|-f CRED|-F CREDFILE] URL ListChecks
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
                
                        -p, --provider PROVIDER...  provider string (e.g. azure)
                        -c, --check CHECK...        Trento check id (e.g. 21FCA6)
                        -t, --target                agent uuid of target host (e.g. )
                        --timeout TIMEOUT           timeout in seconds waiting for an execution to appear or to complete 

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
                    Execute a check for a (azure) host:         rabbiteer.py http://localhost:4000 ExecuteCheck -p azure -c 156F64 -t b651491b-904d-5448-9350-fe817c1f2c6e

                '''
        return textwrap.dedent(text)


def signal_handler(sig, frame):
    sys.exit(0)

def argument_parse():
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
    parser_execute_check.add_argument('-p', '--provider',
                                      dest='provider',
                                      action='store',
                                      required = True,
                                      type=str)
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

    # Command: ListChecks
    parser_list_checks = subparsers.add_parser('ListChecks')
  
    # Command: Health
    parser_list_checks = subparsers.add_parser('Health')
    
    # Command: Ready
    parser_list_checks = subparsers.add_parser('Ready')  

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

    # Set debugging.
    if args_parsed.debug:
        logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(asctime)s\n%(message)s')
        
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

def unknown_response(response, error):
    """Prints response and error message and terminates with exit code 3."""

    print(f'Could not evaluate response:\n{response}\n\nError: {error}', file=sys.stderr)
    sys.exit(3)


def main():

    signal.signal(signal.SIGINT, signal_handler)

    arguments = argument_parse()
    connection = Rabbiteer(arguments.url, arguments.access_key, arguments.credential)
    
    try: 
    
        # Command: ExecuteCheck
        if arguments.command == 'ExecuteCheck':

            # Start check(s) execution.
            response = connection.execute_checks(sum(arguments.agents, []), arguments.provider, sum(arguments.checks, []), timeout=arguments.timeout)

            # Print full response or evaluation.
            if arguments.raw_output:
                print(json.dumps(response))
            else:
                try:
                    for check_result in response['check_results']:
                        for agents_check_result in check_result['agents_check_results']:
                            message = f'''check={check_result['check_id']} agent_id={agents_check_result['agent_id']} result={check_result['result']} execution_id={response['execution_id']}'''
                            if 'message' in agents_check_result:
                                message += f''' message="{agents_check_result['message']}" type={agents_check_result['type']}'''
                            print(message)    

                except Exception as err:
                    unknown_response(response, err)
                    
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

            # Print full response or evaluation.
            if arguments.raw_output:
                print(json.dumps(response))
            else:
                try:
                    checks = response['items']
                    for check in checks:
                        print(f'''{check['id']} - {check['name']} ({check['group']})''')
                except Exception as err:
                    print(f'Could not evaluate response:\n{response}\n\nError: {err}', file=sys.stderr)
                    sys.exit(3)
                print(f'\n{len(checks)} check(s) found.')
                
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

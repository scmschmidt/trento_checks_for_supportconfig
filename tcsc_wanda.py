#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-

"""
Contains classes to handle the Wanda container stack.
"""


import docker
import functools
import time
from rabbiteer import Rabbiteer
from typing import List, Dict, Any, Tuple
from tcsc_config import *


class WandaStack():
    """Represents a Wanda container stack.
    
        - self._containers (Dict[str, Container]):  Dict with the Wand container instances referenced by name.
        - self._docker (docker.DockerClient):  Instance of DockerClient.
        - self._rabbiteer (Rabbiteer):  Rabbiteer instance to talk to Wanda.
        - self.timeout (int):  Timeout for Docker and Wanda operations.
    """

    def __init__(self, config: Config) -> None:
        self._docker: docker.DockerClient = docker.from_env()
        self.timeout: int = config.docker_timeout
        self._containers: Dict[str, docker.Container] = {container.name: container for container in 
                                                         self._docker.containers.list(
                                                             all=True, 
                                                             filters={'label': config.wanda_label})
                                                        }
        if set(self._containers.keys()) != set(config.wanda_containers):
            raise WandaException('Not all required Wanda containers are present.')
        self._rabbiteer = Rabbiteer(config.wanda_url)

    @property
    def container_status(self) -> Dict[str, str]:
        """Returns a dictionary with all Wanda containers and there current status."""
        
        self._update()
        return {container.name: container.status for container in self._containers.values()}
        
    @property
    def status(self) -> bool:
        """Returns a boolean with the Wanda status."""    
        
        for status in self.container_status.values():
            if status != 'running':
                return False

        try:
            health: str = self._rabbiteer.health()['database']
            ready: bool = self._rabbiteer.readiness()['ready']
        except:
            return False
        else:
            if ready and health == 'pass':
                return True 

        return False
        
    def checks(self, attributes: List[str] = None) -> List[dict]:
        """Returns list of Check instances for all available checks (content of 'items').
        The Check instance will have only the requested attributes.""" 
    
        return [Check(c, attributes) for c in self._rabbiteer.list_catalog().get('items')]   
       
    def start(self) -> List[str]:
        """Initiate start of Wanda containers. Only containers, which are in the states
        'exited' or 'created' are going to be started. The method will *not* wait for 
        the containers to be up.
        Returns the names of the started containers."""
        
        started: List[str] = []
        self._update()
        for container in [c for c in self._containers.values() if c.status in ['exited', 'created']]:
            started.append(container.name)
            container.start()
            
        start_time = time.time()    
        while not self.status:
            if  (time.time() - start_time) > self.timeout: 
                raise WandaException(f'''Timeout of {self.timeout}s reached. Wanda did not became operational after start of containers: {', '.join(started)}''')
            time.sleep(1) 
        
        return started

    def stop(self) -> List[str]:
        """Stops all Wanda containers. Only containers, which are in the state 'running'
        are going to be stopped.
        Returns the names of the stopped containers."""
        
        stopped: List[str] = []
        self._update()
        for container in [c for c in self._containers.values() if c.status in ['running']]:
            stopped.append(container.name)
            container.stop(timeout=self.timeout)
            
        start_time: time.Time = time.time()
        while True:
            self._update()
            not_exited = [name for name, status in self.container_status.items() if status != 'exited']
            if not not_exited:
                break
            if  (time.time() - start_time) > self.timeout: 
                raise WandaException(f'''Timeout of {self.timeout}s reached. Container not yet exited: {', '.join(not_exited)}''')
            time.sleep(1)   
        
        return stopped

    def execute_check(self, provider: str, agent_ids: List[str], check_ids: List[str]) -> Tuple[str, dict]:
        """Executes checks on the given hosts."""

        try:
            response = self._rabbiteer.execute_checks(agent_ids, provider, check_ids, timeout=self.timeout, running_dots=False)                 
            check_result = response['check_results'][0] #TODO: Is the assumption of one result always correct?
            host_data = []
            for agents_check_result in check_result['agents_check_results']:
                host_data.append((agents_check_result['agent_id'],
                                 (agents_check_result['message'], agents_check_result['type']) 
                                  if 'message' in agents_check_result else None
                                 )
                                ) 
            result = check_result['result'], host_data
        except Exception as err: # RETURN NOT RAISE!
            result = 'error', err
           
        #import pprint    
        #pprint.pprint(response)
 
        return result

    def _update(self) -> None:
        """Updates the container objects."""
        for container in self._containers.values():
            container.reload()


class WandaException(Exception):
    pass


class Check():
    """Represents a Trento check.
    The representation reads takes the original dictionary created from JSON
    and creates a reduced flat dictionary with only the parts required."""
 
    _known_gatherers = ['cibadmin@v1',
                        'corosync-cmapctl@v1',
                        'corosync.conf@v1',
                        'hosts@v1',
                        'package_version@v1',
                        'saphostctrl@v1',
                        'sbd_config@v1',
                        'sbd_dump@v1',
                        'systemd@v1',
                        'verify_password@v1'
                       ]
    _valid_gatherers = ['cibadmin@v1',
                        'corosync.conf@v1', 
                        'package_version@v1',
                        'sbd_config@v1',
                        'sbd_dump@v1',
                       ]
   
    _attribute_table = {'id': 'id', 
                        'description': 'description', 
                        'group': 'group', 
                        'metadata.provider': 'provider', 
                        'metadata.cluster_type': 'cluster_type', 
                        'facts[].gatherer': 'gatherer',
                        'expectations[].type': 'check_type'
                       }
    
    
    @staticmethod
    def _retrieve_attributes(dictionary: Dict, keys: List[str]):
        """Retrieves key-value pairs in a nested dictionary. The result is always a flat dictionary.
        Keys are written in dot-notation (e.g. 'metadata.cluster_type'). 
        Intermediate lists must be indicated by '[]' at the end of the key containing 
        the list (e.g. 'expectations[].type').
        If keys or indices are not found, None is returned."""
        
        def walk(subtree: Dict[str, Any], components: List[str]) -> Any:
            if components[0].endswith('[]'):
                real_key = components[0][:-2]
                elements = []
                for elem in subtree[real_key]:
                    elements.append(walk(elem, components[1:]))
                return elements    
            if len(components) > 1:
                return walk(subtree[components[0]], components[1:])
            return subtree[components[0]]

        data = {}
        for attribute in keys:
            components = attribute.split('.')
            try:
                value = walk(dictionary, components)
            except (KeyError, IndexError):
                value = None
            data[attribute] = value
        
        return data    
    
    def __init__(self, check: Dict, attributes: List[str] = None) -> None:
                
        if not attributes:
            attributes = Check._attribute_table.keys()
        if not set(attributes).issubset(Check._attribute_table.keys()):
            raise CheckException(f'Unsupported attributes: {set(attributes) - Check._attribute_table.keys()}')
        
        for key, value in Check._retrieve_attributes(check, attributes).items():
            if key == 'metadata.provider':
                if isinstance(value, str):
                    value = [value]
            if key == 'expectations[].type':
                if len(set(value)) != 1:
                    raise CheckException(f'Unexpected expectation types: {value}')
                try:
                    value = {'expect': 'single', 'expect_same': 'multi'}[value[0]]
                except KeyError:
                    raise CheckException(f'Unexpected expectation types: {value[0]}')
            if isinstance(value, str):
                value = value.strip()
            setattr(self, Check._attribute_table[key], value)   # value is always None, str or list

            gatherers = set(Check._retrieve_attributes(check, ['facts[].gatherer'])['facts[].gatherer'])
            if gatherers.issubset(Check._valid_gatherers):
                self.tcsc_support = 'yes'
            elif gatherers.issubset(Check._known_gatherers):
                self.tcsc_support = 'no'
            else:
                self.tcsc_support = 'unknown'
                
class CheckException(Exception):
    pass       
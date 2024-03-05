#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-

"""
Contains classes to handle the Wanda container stack.
"""


import docker
import functools
import time
from rabbiteer import Rabbiteer
from typing import List, Dict, Any
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
        
    @property    
    def checks(self) -> List[dict]:
        """Returns list of all available checks.""" 
        
        return self._rabbiteer.list_catalog().get('items')       
    
    def filter_checks(self, requested: List[str]) -> List[dict]:
        """Returns list of all available checks, with the requested attributes only.
        It is possible to use dot notation to access nested objects. The result will
        always be a flat dictionary with deep references resolved.""" 
       
        def deep_get(dictionary: dict, keys: Any, default=None) -> Any:
            return functools.reduce(lambda d, key: d.get(key, default) if isinstance(d, dict) else default, keys.split("."), dictionary)
        
        result: List[Dict[str, Any]] = []
        for check in self.checks:
            result.append({attribute: deep_get(check, attribute) for attribute in requested})
        return result
     
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

    def _update(self) -> None:
        """Updates the container objects."""
        for container in self._containers.values():
            container.reload()


class WandaException(Exception):
    pass

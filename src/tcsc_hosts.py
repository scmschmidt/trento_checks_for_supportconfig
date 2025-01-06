#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-

"""
Contains classes to handle the hosts container stack.
"""


import docker
import sys
import time
import subprocess
from typing import List, Dict, Any, Tuple, Set

import docker.models
import docker.models.containers
from tcsc_config import *


class HostsStack():
    """Represents a Hosts container stack.
    
        - self._docker (docker.DockerClient):  Instance of DockerClient.
        - self.timeout (int):  Timeout for Docker and host operations.
        - self.start_timeout (int):  Timeout for containers to start and stay alive.
        - self.id (str):  UUID of this tcsc installation.
        - self.image (str):  Image used for hosts container.
    """

    def __init__(self, config: Config) -> None:
        self._docker: docker.DockerClient = docker.from_env()
        self.timeout = config.docker_timeout
        self.start_timeout = config.startup_timeout
        self.id = config.id
        self.image = config.hosts_image
        self.host_label = config.hosts_label

    def _wait4start(self, host: docker.models.containers.Container):
        """Waits until given container is running and stays running."""
    
        start_time = time.time()    
        while True:
            host.reload()
            if host.status == 'running':
                break
            if  (time.time() - start_time) > self.start_timeout: 
                raise HostsException(f'Start timeout of {self.start_timeout}s reached. "{host.name}" did not became operational.')
            time.sleep(.2)

        start_time = time.time()    
        while (time.time() - start_time) <= self.start_timeout:
            host.reload()
            if host.status != 'running':
                raise HostsException(f'"Start timeout of {self.start_timeout}s reached. {host.name}" stopped running.')
            time.sleep(.2)

    def create(self, hostgroup: str, name: str, host_description: Dict, environment: Dict[str, str]) -> str:
        """Creates and starts a new host container for the requested group and returns its name."""

        dbus_uuid, agent_id = self._generate_id()

        supportconfig_path = os.path.abspath(host_description['supportconfig'])
        supportconfig_name = os.path.basename(supportconfig_path)
        
        # If HOST_ROOT_FS is set, we run inside a container and usually all
        # paths need to be prefixed with the content of that variable: the 
        # mount point of the host's rootfs.
        # This has to be removed from `supportconfig_path` because it is
        # referenced from inside the container!
        if 'HOST_ROOT_FS' in os.environ:
            supportconfig_path = supportconfig_path.removeprefix(os.getenv('HOST_ROOT_FS'))
        
        host = self._docker.containers.run(
            image = self.image,
            name = f'tcsc-host-{hostgroup}-{name}-{self.id}',
            command = '/sc/startup',
            environment = {'SUPPORTCONFIG' : f'/{supportconfig_name}',
                           'MACHINE_ID': dbus_uuid
                          },
            volumes = [f'{supportconfig_path}:/{supportconfig_name}'],
            network = 'tcsc_default',
            labels = {'com.suse.tcsc.stack': 'host',
                      'com.suse.tcsc.hostgroup': hostgroup,
                      'com.suse.tcsc.hostname': name,
                      'com.suse.tcsc.supportfiles': supportconfig_path,
                      'com.suse.tcsc.supportconfig': supportconfig_path,
                      'com.suse.tcsc.env.provider': environment['provider'] if 'provider' in environment else host_description['provider'],
                      'com.suse.tcsc.env.cluster_type': environment['cluster_type'] if 'cluster_type' in environment else host_description['cluster_type'],
                      'com.suse.tcsc.env.architecture_type': environment['architecture_type'] if 'architecture_type' in environment else host_description['architecture_type'],
                      'com.suse.tcsc.env.ensa_version': environment['ensa_version'] if 'ensa_version' in environment else host_description['ensa_version'],
                      'com.suse.tcsc.env.filesystem_type': environment['filesystem_type'] if 'filesystem_type' in environment else host_description['filesystem_type'],
                      'com.suse.tcsc.env.hana_scenario': environment['hana_scenario'] if 'hana_scenario' in environment else host_description['hana_scenario'],
                      'com.suse.tcsc.uuid': self.id,
                      'com.suse.tcsc.agent_id': agent_id
                     },
            detach = True)
        self._wait4start(host)
        
        return host.name

    def start_hostgroup(self, hostgroup: str) -> bool:
        """Starts all hosts of given host group and returns the success."""

        for container in self.filter_containers(filter={'hostgroup': hostgroup}):
            if container['container'].status == 'running':
                return True
            container['container'].start()
            self._wait4start(container['container'])

        return True

    def stop_hostgroup(self, hostgroup) -> List[str]:
        """Stops all running host containers of the given host group and returns the names of the stopped containers."""

        stopped: List[str] = []
        for container in [c for c in self.filter_containers(filter={'hostgroup': hostgroup}) if c['status'] in ['running']]:
            stopped.append(container['name'])
            container['container'].stop(timeout=self.timeout)
        
        return stopped     
            
    def remove_hostgroup(self, hostgroup) -> List[str]:
        """Removes all host containers of the given host group and returns the names of the destroyed containers."""
        
        removed: List[str] = []
        for container in [c for c in self.filter_containers(filter={'hostgroup': hostgroup})]:
            removed.append(container['name'])
            container['container'].remove(v=True, force=True)        
        return removed    

    def rescan_hostgroup(self, hostgroup: str) -> Dict[str, Tuple[bool, str]]:
        """Initiates a re-processing of the supportfiles on all host containers for
        the given hostgroup. An exception is risen if something went wrong."""

        scanned_hosts = {}
        for container in self.filter_containers(filter={'hostgroup': hostgroup}):
            if container['status'] != 'running':
                state = (False, f'''Container status: {container['status']}''')
            else:
                for cmd in ['rm', '-f', '/manifest'], ['sc/process_supportfiles']:
                    error, _, stderr = self._run_cmd(container['container'], cmd, exception_on_error=True)
                    if error == 0:
                        state = (True, '')
                    else:
                        state = (False, stderr)
            scanned_hosts[container['name']] = state
        return scanned_hosts

    def logs(self, containername: str) -> List[str]:
        """Retrieves log for given container name."""
        
        container = self.filter_containers(filter={'name': containername})
        if container:
            return container[0]['container'].logs().decode("utf-8").strip().split(os.linesep)
        return None

    @property
    def containers(self) -> List[Dict[str, str]]:
        """Retrieves all current host containers from Docker and returns a data dictionary.""" 
        
        return [{'name': container.name or '-', 
                 'container_id': container.id,
                 'container_short_id': container.short_id,
                 'supportfiles': container.labels.get('com.suse.tcsc.supportfiles') or '-',
                 'supportconfig': container.labels.get('com.suse.tcsc.supportconfig') or '-',
                 'provider': container.labels.get('com.suse.tcsc.env.provider') or 'default',
                 'cluster_type': container.labels.get('com.suse.tcsc.env.cluster_type') or None,
                 'architecture_type': container.labels.get('com.suse.tcsc.env.architecture_type') or None,
                 'ensa_version': container.labels.get('com.suse.tcsc.env.ensa_version') or None,
                 'filesystem_type': container.labels.get('com.suse.tcsc.env.filesystem_type') or None,
                 'hana_scenario': container.labels.get('com.suse.tcsc.env.hana_scenario') or None,
                 'hostgroup': container.labels.get('com.suse.tcsc.hostgroup') or '-',
                 'hostname': container.labels.get('com.suse.tcsc.hostname') or '-',
                 'status': container.status or 'unknown',
                 'agent_id': container.labels.get('com.suse.tcsc.agent_id') or '-',
                 'container': container
                } for container in
                self._docker.containers.list(all=True, filters={'label': [self.host_label, f'com.suse.tcsc.uuid={self.id}']}) 
               ]

    def filter_containers(self, filter: Dict[str, Any] = {}, sortkey: str = 'hostgroup') -> List[Dict[str, str]]:
        """Retrieve and return current host containers matching the filter from Docker.
        Currently supported filters: 
            - hostgroup: List[str]
            - name: List[str]
        A sort key can be given to sort the results (default: hostgroup).""" 

        containers: List[str, str] = []
        for container in self.containers:
            if filter.get('hostgroup') and container['hostgroup'] != filter.get('hostgroup'):
                continue
            if filter.get('name') and container['name'] != filter.get('name'):
                continue
            containers.append(container)
        return sorted(containers, key=lambda x: x[sortkey])
    
    @classmethod
    def get_manifest(self, container: docker.models.containers.Container) -> Tuple[str, str]:
        """Retrieves the manifest of the given container object. A tuple is returned.
        If everything went well the tuple is (True, error message) or (False, command output)
        if not.""" 

        error, stdout, stderr = self._run_cmd(container, ['cat', '/manifest'], exception_on_error=False)
        if error != 0:
            return True, stderr
        manifest = {}        
        try:
            for key, value in [line.split(':') for line in stdout.split()]:                
                manifest[key] = {'ok': 'ok', 'failed': 'failed'}[value]
        except:
            return True, 'Could not parse manifest. Invalid format!'
        return False, manifest, 
    
    @classmethod
    def _run_cmd(self, 
                 container: docker.models.containers.Container, 
                 command: List[str], 
                 exception_on_error=False
                ) -> Tuple[int, str, str]:
        """Executes a command on the given container and returns a tuple with the exit code,
        stdout and stderr. The error behaviour can be switched between raising an exception 
        or returning the exit code as well the error message (stderr)."""
        
        try:
            error, output = container.exec_run(command, demux=True)
        except Exception as err:
            return 255, '', str(err)
        stdout = str(output[0], sys.getdefaultencoding()) if output[0] else ''
        stderr = str(output[1], sys.getdefaultencoding()) if output[1] else ''
        if error != 0 and exception_on_error == True:
            error_text = stderr if stderr else stdout
            raise HostsException(f'''Executing "{' '.join(command)}" on {container.name} failed. Exit code: {error} error:{error_text}''')    
        return error, stdout, stderr 
    
    @classmethod
    def _generate_id(self) -> Tuple[str]:
        """Return a generated dbus uuid by calling `dbus-uuidgen` and the derived trento-agent id."""
        
        try:
            dbus_uuid = subprocess.run(['dbus-uuidgen'],
                                        stdout=subprocess.PIPE, 
                                        stderr=subprocess.STDOUT
                                        ).stdout.decode('utf-8').strip()
            agent_id = subprocess.run(['uuidgen', 
                                       '-N', dbus_uuid, 
                                       '-n', 'fb92284e-aa5e-47f6-a883-bf9469e7a0dc', 
                                       '--sha1'
                                       ],
                                       stdout=subprocess.PIPE, 
                                       stderr=subprocess.STDOUT
                                    ).stdout.decode('utf-8').strip()
        except Exception as err:
            raise HostsException(f'Error generating IDs for D-Bus and Trento agent: {err}')

        return dbus_uuid, agent_id
        
    @property
    def hostgroups(self) -> Set[str]:
        """Returns all current host groups."""
        
        return set([c['hostgroup'] for c in self.filter_containers()])
    
    
class HostsException(Exception):
    pass


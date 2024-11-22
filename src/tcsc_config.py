#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-

"""
Contains classes to handle the tcsc configuration.
"""


import os
import json
import uuid 


class Config():
    """Represents tcsc configuration.
    
        - self.id (str):
            UUID used to mark the created containers.
            default: random uuid 
            example: 73f31f16-eaba-11ee-994d-5b663d913758
            
        - self.wanda_containers (List[str]):
            List of all Wanda container names.  
            default: ['tcsc-rabbitmq', 'tcsc-postgres', 'tcsc-wanda']
            
        - self.wanda_label (str):
            Label used to identify Wanda containers for tcsc.
            default: com.suse.tcsc.stack=wanda
          
        - self.hosts_label (str):
            Label used to identify tcsc hosts container.
            default: com.suse.tcsc.stack=host
            
        - self.docker_timeout (int):
            Timeout in seconds for docker (and Wanda) operations.
            default: 10
            
        - self.startup_timeout (int):
            Timeout in seconds for host containers to start and keep alive.
            default: 3
            
        - self.wanda_url (str):
            URL to connect to the Wanda container.
            default: http://localhost:4000
            
        - self.hosts_image (str):
            Name of the hosts container image.
            default: tscs_host

        - self.wanda_autostart (bool):
            Determines if Wanda shall be started automatically when required.
            default: true
            
        - self.colored_output (bool):
            Determines if the output should be colored or not.
            default: true
    """

    def __init__(self, configfile: str, create: bool = True) -> None:
        """Loads the configuration from `configfile`. If `create` is
        true and `configfile` does not exists, a default configuration
        will be created.

        Args:
            configfile (str):           Filename of JSON configuration.
            create (bool, optional):    Flag if a default configuration shall be created,
                                        if the config file is missing. Defaults to True.
        """

        configfile = os.path.expandvars(os.path.expanduser(configfile))
        
        # If HOST_ROOT_FS is set, we run inside a container and all paths
        # need to be prefixed with the content of that variable: the mount
        # point of the host's rootfs.
        # Also we have to prefix relative paths with the (imported) $PWD
        # to be correct first.
        if 'HOST_ROOT_FS' in os.environ:
            configfile = f'''{os.getenv('HOST_ROOT_FS')}{configfile}''' if configfile.startswith('/') else  f'''{os.getenv('HOST_ROOT_FS')}/{os.getenv('PWD')}/{configfile}'''   
      
        try:
            with open(configfile) as f:
                config = json.load(f)
                self.id = config['id']
                self.wanda_containers = config['wanda_containers']
                self.wanda_label = config['wanda_label']
                self.hosts_label = config['hosts_label']
                self.docker_timeout = abs(int(config['docker_timeout']))
                self.wanda_url = config['wanda_url']
                self.hosts_image = config['hosts_image']
                self.startup_timeout = config['startup_timeout']
                self.wanda_autostart = config['wanda_autostart']
                self.colored_output = config['colored_output']
        except Exception as err:
            raise ConfigException(f'Error accessing configuration: {err}')


class ConfigException(Exception):
    pass


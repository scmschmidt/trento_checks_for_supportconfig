#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-

"""
Contains classes to handle CLI handling.
"""

import shlex
import sys
import termcolor
import json
from typing import TextIO, List
       
                   
class CLI():
    """Provides methods to print colored messages on the terminal."""
    
    no_color = False
    ok = 0
    warn = 1
    error = 2
    colors = {error: 'red', warn: 'yellow', ok: 'green'}
    json = False

    @classmethod
    def print(cls, text: str = '', file: TextIO = sys.stdout) -> None:
        if not cls.json:
            print(text, file=file)
    
    @classmethod
    def print_header(cls, text: str, margin_top: int = 0, margin_bottom: int = 0, file: TextIO = sys.stdout) -> None:
        if not cls.json:
            for i in range(0, margin_top):
                print(file=file)
            print(termcolor.colored(text, 'blue', attrs=['bold', 'underline'], no_color=cls.no_color), file=file)
            for i in range(0, margin_bottom):
                print(file=file)
    
    @classmethod
    def print_info(cls, text: str, file: TextIO = sys.stdout) -> None:
        if not cls.json:
            print(termcolor.colored(text, 'blue', no_color=cls.no_color), file=file)

    # @classmethod
    # def print_details(cls, text: str, file: TextIO = sys.stdout) -> None:
    #     if not cls.json:
    #         print(termcolor.colored(text, 'grey', no_color=cls.no_color), file=file)
                
    @classmethod
    def print_fail(cls, text: str, file: TextIO = sys.stdout) -> None:
        if not cls.json:
            print(termcolor.colored(text, 'red', no_color=cls.no_color), file=file)

    @classmethod
    def print_warn(cls, text: str, file: TextIO = sys.stdout) -> None:
        if not cls.json:
            print(termcolor.colored(text, 'yellow', no_color=cls.no_color), file=file)

    @classmethod
    def print_ok(cls, text: str, file: TextIO = sys.stdout) -> None:
        if not cls.json:
            print(termcolor.colored(text, 'green', no_color=cls.no_color), file=file)

    @classmethod
    def print_status(cls, status_object: List[dict], status_first: bool = True, file: TextIO = sys.stdout) -> None:
        """Prints status object.
        
        The status object is a list of dicts. Each dict describes one entry and has the following keys:
            - name          str     Name of the entry.
            - status        int     The entries status. One of CLI.ok, CLI.warn, CLI.err.
            - status_text   str     The text displayed in the status field.
            - details       dict    Dictionary with key value pairs with detailed information.  (optional)               
        """
        
        if cls.json:
            return

        max_len_name, max_len_status = 0, 0
        filler = ' '
        
        for item in status_object:
            max_len_name = max(max_len_name, len(item['name']))
            max_len_status = max(max_len_status, len(item['status_text']))

        for item in status_object:
            name = item['name']
            status_text = termcolor.colored(f'''{item['status_text']:^{max_len_status}}''', 
                                            cls.colors.get(item['status'], 2), 
                                            no_color=cls.no_color
                                           )
            if status_first:
                spacing = max(18 - max_len_status, 4)
                detail_indent = ' ' * (spacing + max_len_status + 2)
                print(f'[{status_text:^{max_len_status}}]{filler:<{spacing}}{name:<{max_len_name}}', file=file)
            else:
                spacing = max(100 - max_len_name, 4)
                detail_indent =  ''
                print(f'{name:<{max_len_name}}{filler:<{spacing}}[{status_text:^{max_len_status}}]', file=file)
            
            if 'details' in item:
                for key, value in item['details'].items():
                    try:
                        if '\n' in value:
                            indent = f'''\n{detail_indent}{len(key)*' '}  '''
                            value = value.replace('\n', indent)
                    except:    # value is not a string
                        pass
                    text = f'{detail_indent}{key}: {value}'
                    print(termcolor.colored(text, 'grey', no_color=cls.no_color), file=file)
                print(file=file) 
        
    @classmethod
    def print_json(cls, json_object: dict, force_output: bool = False, file: TextIO = sys.stdout) -> None:
        if cls.json or force_output:
            print(json.dumps(json_object), file=file)
            
    @classmethod
    def print_logline(cls, loglines: List[ſtr], file: TextIO = sys.stdout) -> None:
        
        level_color = {'emerg': 'red',
                       'panic': 'red',
                       'alert': 'light_red',
                       'crit': 'light_red',
                       'err': 'light_red',
                       'error': 'light_red',
                       'warn': 'yellow',                       
                       'warning': 'yellow',
                       'notice': 'green',
                       'info': 'green',
                       'debug': 'blue',
                      }
        level_attributes = {'emerg': ['bold'],
                            'panic': ['bold'],
                            'alert': ['bold'],
                            'crit': ['bold'],
                            'err': ['bold'],
                            'error': ['bold'],
                            'warn': [],                       
                            'warning': [],
                            'notice': [],
                            'info': [],
                            'debug': [],
                      }
        
        if cls.json:
            return
        
        if not loglines:
            return
        
        loglines_processed = []
        columns_width = [0, 0, 0]
        for line in loglines:
            entry = []
            try:
                if not line:   # empty lines can happen
                    raise()
                for index, component in enumerate(shlex.split(line)):
                    _, value = component.split('=')
                    columns_width[index] = max(len(value), columns_width[index])
                    entry.append(value)
                
            except:    # Some log entries (coming from commands running in the container) are not key-value pairs
                entry = ['????-??-?? ??:??:??', 'output', line]
            loglines_processed.append(entry)    
            
        for line in loglines_processed:
            print(termcolor.colored(f'{line[0]:<{columns_width[0]}}', 'grey', no_color=cls.no_color),
                  termcolor.colored(f'{line[1]:<{columns_width[1]}}', level_color.get(line[1], 'white'), no_color=cls.no_color),
                  termcolor.colored(line[2], level_color.get(line[1], 'white'), attrs=level_attributes.get(line[1], []), no_color=cls.no_color),
                  file=file
                 )

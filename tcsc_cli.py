#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-

"""
Contains classes to handle CLI handling.
"""

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
                print(f'[{status_text:^{max_len_status}}]    {name:<{max_len_name}}', file=file)
            else:
                print(f'{name:<{max_len_name}}    [{status_text:^{max_len_status}}]', file=file)
            
            if 'details' in item:
                indent = ' ' * (max_len_status + 9) if status_first else '    '
                for key, value in item['details'].items():
                    text = f'{indent}{key}: {value}'
                    print(termcolor.colored(text, 'grey', no_color=cls.no_color), file=file)
                print(file=file) 
        
    @classmethod
    def print_json(cls, json_object: dict, file: TextIO = sys.stdout) -> None:
        if cls.json:
            print(json.dumps(json_object), file=file)
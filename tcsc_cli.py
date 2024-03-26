#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-

"""
Contains classes to handle CLI handling.
"""

import json
import sys
import termcolor
from typing import TextIO


class CLI():
    """Provides methods to print colored messages on the terminal."""
    
    no_color = False
    ok = 0
    warn = 1
    error = 2
    colors = {error: 'red', warn: 'yellow', ok: 'green'}
    
    
    @classmethod
    def print_header(cls, text: str, file: TextIO = sys.stdout) -> None:
        print(termcolor.colored(text, 'blue', attrs=['bold', 'underline'], no_color=cls.no_color), file=file)
    
    @classmethod
    def print_info(cls, text: str, file: TextIO = sys.stdout) -> None:
        print(termcolor.colored(text, 'blue', no_color=cls.no_color), file=file)

    @classmethod
    def print_details(cls, text: str, file: TextIO = sys.stdout) -> None:
        print(termcolor.colored(text, 'grey', no_color=cls.no_color), file=file)
                
    @classmethod
    def print_fail(cls, text: str, file: TextIO = sys.stdout) -> None:
        print(termcolor.colored(text, 'red', no_color=cls.no_color), file=file)

    @classmethod
    def print_warn(cls, text: str, file: TextIO = sys.stdout) -> None:
        print(termcolor.colored(text, 'yellow', no_color=cls.no_color), file=file)

    @classmethod
    def print_ok(cls, text: str, file: TextIO = sys.stdout) -> None:
        print(termcolor.colored(text, 'green', no_color=cls.no_color), file=file)

    # @classmethod
    # def print_status(cls, text: str, status_text: str, status: int = 0, file: TextIO = sys.stdout) -> None:
    #     print(text + termcolor.colored(status_text, {2: 'red', 1: 'yellow', 0: 'green'}.get(status, 2), no_color=cls.no_color), file=file)

    # @classmethod
    # def print_status2(cls, status_text: str, text: str, status: int = 0, file: TextIO = sys.stdout) -> None:
    #     print(termcolor.colored(status_text + text, {2: 'red', 1: 'yellow', 0: 'green'}.get(status, 2), no_color=cls.no_color), file=file)
        
    @classmethod
    def print_status(cls, status_object: dict, file: TextIO = sys.stdout) -> None:
        """Prints status object on given file.
        
        The status object is a dictionary with the following keys:
            - header        str         Text used for the status header. None if no header is required.
            - status        int         The overall status. One of CLI.ok, CLI.warn, CLI.err.
            - status_text   str         The status text displayed at the end. None if no status text is required.
            - items         List(dict)  Separate components (see below for details).
            
        Each item is a dictionary with the following keys:

            - name          str     Name of the entry.
            - status        int     The entries status. One of CLI.ok, CLI.warn, CLI.err.
            - status_text   str     The text displayed in the status field.
            - details       dict    Dictionary with key value pairs with detailed information.
                         
        """
        
        if status_object['header']:
            cls.print_header(status_object['header'], file=file)
        
        max_len_name, max_len_status = 0, 0
        for item in status_object['items']:
            max_len_name = max(max_len_name, len(item['name']))
            max_len_status = max(max_len_status, len(item['status_text']))

        for item in status_object['items']:
            name = item['name']
            status_text = termcolor.colored(f'''{item['status_text']:^{max_len_status}}''', 
                                            cls.colors.get(item['status'], 2), 
                                            no_color=cls.no_color
                                           )
            #print(f'{name:<{max_len_name}}    [{status_text:^{max_len_status}}]', file=file)
            print(f'[{status_text:^{max_len_status}}]    {name:<{max_len_name}}', file=file)
            if 'details' in item:
                for key, value in item['details'].items():
                    text = f'\t{key}: {value}'
                    print(termcolor.colored(text, 'grey', no_color=cls.no_color), file=file)
        
        if status_object['status_text']:
            print(file=file)
            print(termcolor.colored(status_object['status_text'], 
                                    cls.colors.get(status_object['status'], 2), 
                                    no_color=cls.no_color
                                   ), file=file)
            
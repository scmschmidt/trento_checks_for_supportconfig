#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-

"""
Contains classes to handle CLI handling.
"""


import termcolor


class CLI():
    """Provides methods to print colored messages on the terminal."""
    
    @classmethod
    def print_info(cls, text: str) -> None:
        print(termcolor.colored(text, 'blue'))

    @classmethod
    def print_details(cls, text: str) -> None:
        print(termcolor.colored(text, 'grey'))
                
    @classmethod
    def print_fail(cls, text: str) -> None:
        print(termcolor.colored(text, 'red'))

    @classmethod
    def print_warn(cls, text: str) -> None:
        print(termcolor.colored(text, 'yellow'))

    @classmethod
    def print_ok(cls, text: str) -> None:
        print(termcolor.colored(text, 'green'))

    @classmethod
    def print_status(cls, text: str, status_text: str, status: int = 0) -> None:
        print(text + termcolor.colored(status_text, {2: 'red', 1: 'yellow', 0: 'green'}.get(status, 2)))
        

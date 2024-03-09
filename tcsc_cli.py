#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-

"""
Contains classes to handle CLI handling.
"""

import sys
import termcolor
from typing import TextIO


class CLI():
    """Provides methods to print colored messages on the terminal."""
    
    @classmethod
    def print_header(cls, text: str, file: TextIO = sys.stdout) -> None:
        print(termcolor.colored(text, 'blue', attrs=['bold', 'underline']), file=file)
    
    @classmethod
    def print_info(cls, text: str, file: TextIO = sys.stdout) -> None:
        print(termcolor.colored(text, 'blue'), file=file)

    @classmethod
    def print_details(cls, text: str, file: TextIO = sys.stdout) -> None:
        print(termcolor.colored(text, 'grey'), file=file)
                
    @classmethod
    def print_fail(cls, text: str, file: TextIO = sys.stdout) -> None:
        print(termcolor.colored(text, 'red'), file=file)

    @classmethod
    def print_warn(cls, text: str, file: TextIO = sys.stdout) -> None:
        print(termcolor.colored(text, 'yellow'), file=file)

    @classmethod
    def print_ok(cls, text: str, file: TextIO = sys.stdout) -> None:
        print(termcolor.colored(text, 'green'), file=file)

    @classmethod
    def print_status(cls, text: str, status_text: str, status: int = 0, file: TextIO = sys.stdout) -> None:
        print(text + termcolor.colored(status_text, {2: 'red', 1: 'yellow', 0: 'green'}.get(status, 2)), file=file)

    @classmethod
    def print_status2(cls, status_text: str, text: str, status: int = 0, file: TextIO = sys.stdout) -> None:
        print(termcolor.colored(status_text + text, {2: 'red', 1: 'yellow', 0: 'green'}.get(status, 2)), file=file)        
        

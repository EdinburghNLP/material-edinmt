#!/usr/bin/env python3.7
# -*- coding: utf-8 -*
"""
Implement a simple plugin architecture, by loading all submodule classes 
into the globals of this package. 
Plugins must iherit from `edinmt.scorers.Scorer`. 

Acknowledgements: https://julienharbulot.com/python-dynamical-import.html
"""
from inspect import isclass
from pkgutil import iter_modules
from pathlib import Path
from importlib import import_module

from .scorers import Scorer

SCORERS = {}

# iterate through the modules in the current package
package_dir = str(Path(__file__).resolve().parent)
for (_, module_name, _) in iter_modules([package_dir]):

    # import the module and iterate through its attributes
    module = import_module(f"{__name__}.{module_name}")
    for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)

            #gather just Scorers and add to importable globals (for *)
            if isclass(attribute) and issubclass(attribute, Scorer):
                globals()[attribute_name] = attribute

                #also add Scorers to plugin dict, so they can 
                #be easier to reference by name in edinmt.translate
                SCORERS[attribute.__name__] = attribute

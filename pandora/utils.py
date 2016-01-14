#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import glob
import codecs

import numpy as np

def load_annotated_data(directory, format='conll', nb_instances=1000):
    instances = []
    for filepath in glob.glob(directory+'/*'):
        insts = load_annotated_file(filepath=filepath,
                                    format=format,
                                    nb_instances=nb_instances)
        instances.extend(insts)
    return instances

def load_annotated_file(filepath, format, nb_instances):
    instances = []
    if format == 'conll':
        for line in codecs.open(filepath, 'r', 'utf8'):
            line = line.strip()
            if line:
                try:
                    idx, tok, _, lem, _, pos, morph = \
                        line.split()[:7]
                    instances.append([tok, lem, pos, morph])
                except ValueError:
                    pass
            if len(instances) >= nb_instances:
                break
    return instances

def load_raw_file(filepath, nb_instances=1000):
    instances = []
    for line in codecs.open(filepath, 'r', 'utf8'):
        line = line.strip()
        if line:
            instances.append(line)
        nb_instances -= 1
        if nb_instances <= 0:
            break
    return instances
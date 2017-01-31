#!usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import pandora.utils
from pandora.tagger import Tagger

import os
import codecs
import re
import argparse

tokenize = re.compile("\s")


def tag_dir(model, input_dir, output_dir, string=None, **kwargs):
    """ Tag a directory of texts

    :param model: Path to a model file
    :param input_dir: Path to a directory containing text files
    :param output_dir: Path to output tagged text files
    """
    print('::: started :::')

    tagger = Tagger(load=True, model_dir=model, overwrite=kwargs)
    print('Tagger loaded, now annotating...')

    orig_path = input_dir
    new_path = output_dir

    for filename in os.listdir(orig_path):
        if not filename.endswith('.txt'):
            continue

        print('\t +', filename)
        unseen_tokens = pandora.utils.load_unannotated_file(
            orig_path + filename,
            nb_instances=None,
            tokenized_input=False
        )

        annotations = tagger.annotate(unseen_tokens)
        with codecs.open(new_path + filename, 'w', 'utf8') as f:
            for t, l, p in \
                    zip(annotations['tokens'], annotations['postcorrect_lemmas'], annotations['postcorrect_pos']):
                f.write('\t'.join((t, l, p))+'\n')
    
    print('::: ended :::')


def tag_string(model, input_dir, output_dir=None, string=None, **kwargs):
    """ Tag a directory of texts

    :param model: Path to a model file
    :param input_dir: Untokenized string to tag
    """

    print('::: started :::')

    tagger = Tagger(load=True, model_dir=model, overwrite=kwargs)

    print('Tagger loaded, now annotating...')

    unseen_tokens = tokenize.split(input_dir)
    print(unseen_tokens)

    annotations = tagger.annotate(unseen_tokens)

    keys = list(annotations.keys())
    print("--------------------")
    print('\t'.join(keys))
    print("--------------------")
    for x in zip(*tuple([annotations[k] for k in keys])):
        print('\t'.join(list(x)))

    print('::: ended :::')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Training interface of Pandora")
    parser.add_argument("model", help="Path to model")
    parser.add_argument(
        "--string",
        action="store_true", default=False,
        help="Tag a string instead of a directory [Shell Mode]"
    )
    parser.add_argument("--input", dest="input_dir", help="Path of the input folder")
    parser.add_argument("--output", dest="output_dir", help="Path of the output folder")
    parser.add_argument(
        "--disable-post-correction",
        dest="postcorrect",
        help="Disable post correction",
        action="store_false",
        default=True
    )

    args = parser.parse_args()
    if args.string:
        tag_string(**vars(args))
    else:
        tag_dir(**vars(args))

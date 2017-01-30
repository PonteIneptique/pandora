#!usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import argparse
import pandora.utils
from pandora.tagger import Tagger


def main(config, train='data/wilhelmus/all_train', dev='data/wilhelmus/all_dev', **kwargs):
    print('::: started :::')
    params = pandora.utils.get_param_dict(config)
    params['config_path'] = config
    params.update({k: v for k,v in kwargs.items() if v is not None})
    print("::: Loaded Config :::")
    for k, v in params.items():
        print("\t{} : {}".format(k, v))

    train_data = pandora.utils.load_annotated_dir(
        train,
        format='tab',
        extension='.tab',
        include_pos=params['include_pos'],
        include_lemma=params['include_lemma'],
        include_morph=params['include_morph'],
        nb_instances=None
    )

    dev_data = pandora.utils.load_annotated_dir(
        dev,
        format='tab',
        extension='.tab',
        include_pos=params['include_pos'],
        include_lemma=params['include_lemma'],
        include_morph=params['include_morph'],
        nb_instances=None
    )
    
    tagger = Tagger(**params)
    tagger.setup_to_train(
        train_data=train_data,
        dev_data=dev_data
    )
    
    for i in range(int(params['nb_epochs'])):
        tagger.epoch()
        tagger.save()

    tagger.save()
    print('::: ended :::')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Training interface of Pandora")
    parser.add_argument("config", help="Path to retrieve configuration file")
    parser.add_argument("--dev", help="Path to directory containing dev files")
    parser.add_argument("--train", help="Path to directory containing train files")
    parser.add_argument("--nb_epochs", help="Number of epoch", type=int)
    main(**vars(parser.parse_args()))


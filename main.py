#!usr/bin/env python
# -*- coding: utf-8 -*-

import pandora.utils
import pandora.evaluation
from pandora.tagger import Tagger

def main():
    print('::: started :::')
    train_insts = pandora.utils.load_annotated_file('data/malaga/malaga_train.conll',
                                            format='conll',
                                            nb_instances=250000)
    dev_insts = pandora.utils.load_annotated_file('data/malaga/malaga_dev.conll',
                                            format='conll',
                                            nb_instances=10000)

    unseen_tokens = pandora.utils.load_raw_file('data/malaga/meld_test.txt',
                                            nb_instances=10000)
    
    tagger = Tagger()
    tagger.setup_for_fit(train_instances=train_insts,
               dev_instances=dev_insts,
               unseen_tokens=unseen_tokens)

    for i in range(100):
        tagger.epoch()
    
    print('::: ended :::')

if __name__ == '__main__':
    main()
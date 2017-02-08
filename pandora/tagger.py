#!usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import pickle
import os
import codecs
import shutil
from operator import itemgetter

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from gensim.models import Word2Vec
from sklearn.cluster import AgglomerativeClustering
from sklearn.manifold import TSNE

import keras.backend as K
from keras.utils import np_utils
from keras.models import model_from_json
from keras import backend as K

import editdistance

import pandora.utils as utils
import pandora.evaluation as evaluation
from pandora.model import build_model
from pandora.preprocessing import Preprocessor
from pandora.pretraining import Pretrainer


class Tagger():
    def __init__(self,
                 config_path=None,
                 nb_encoding_layers = 1,
                 nb_dense_dims = 30,
                 batch_size = 100,
                 nb_left_tokens = 2,
                 nb_right_tokens = 2,
                 nb_embedding_dims = 150,
                 model_dir = 'new_model',
                 postcorrect = True,
                 include_token = True,
                 include_context = True,
                 include_lemma = True,
                 include_pos = True,
                 include_morph = True,
                 include_dev = True,
                 include_test = True,
                 nb_filters = 100,
                 filter_length = 3,
                 focus_repr = 'recurrent',
                 dropout_level = .1,
                 load = False,
                 nb_epochs = 15,
                 min_token_freq_emb = 5,
                 halve_lr_at = 10,
                 max_token_len = None,
                 min_lem_cnt = 1,
                 overwrite=None
                 ):
        
        if load:
            if model_dir:
                self.config_path = os.sep.join((model_dir, 'config.txt'))
            else:
                raise ValueError('To load a tagger you, must specify model_name!')
        else:
            self.config_path = config_path

        if not config_path and not load:
            self.nb_encoding_layers = int(nb_encoding_layers)
            self.nb_dense_dims = int(nb_dense_dims)
            self.batch_size = int(batch_size)
            self.nb_left_tokens = int(nb_left_tokens)
            self.nb_right_tokens = int(nb_right_tokens)
            self.nb_context_tokens = self.nb_left_tokens + self.nb_right_tokens
            self.nb_embedding_dims = int(nb_embedding_dims)
            self.model_dir = model_dir
            self.postcorrect = bool(postcorrect)
            self.nb_filters = int(nb_filters)
            self.filter_length = int(filter_length)
            self.focus_repr = focus_repr
            self.dropout_level = float(dropout_level)
            self.include_token = include_token
            self.include_context = include_context
            self.include_lemma = include_lemma
            self.include_pos = include_pos
            self.include_morph = include_morph
            self.include_dev = include_dev
            self.include_test = include_test
            self.min_token_freq_emb = min_token_freq_emb
            self.nb_epochs = int(nb_epochs)
            self.halve_lr_at = int(halve_lr_at)
            self.max_token_len = int(max_token_len)
            self.min_lem_cnt = int(min_lem_cnt)

        else:
            param_dict = utils.get_param_dict(self.config_path)
            print('Using params from config file: ', param_dict)
            self.nb_encoding_layers = int(param_dict['nb_encoding_layers'])
            self.nb_epochs = int(param_dict['nb_epochs'])
            self.nb_dense_dims = int(param_dict['nb_dense_dims'])
            self.batch_size = int(param_dict['batch_size'])
            self.nb_left_tokens = int(param_dict['nb_left_tokens'])
            self.nb_right_tokens = int(param_dict['nb_right_tokens'])
            self.nb_context_tokens = self.nb_left_tokens + self.nb_right_tokens
            self.nb_embedding_dims = int(param_dict['nb_embedding_dims'])
            self.model_dir = param_dict['model_dir']
            self.postcorrect = bool(param_dict['postcorrect'])
            self.nb_filters = int(param_dict['nb_filters'])
            self.filter_length = int(param_dict['filter_length'])
            self.focus_repr = param_dict['focus_repr']
            self.dropout_level = float(param_dict['dropout_level'])
            self.include_token = param_dict['include_token']
            self.include_context = param_dict['include_context']
            self.include_lemma = param_dict['include_lemma']
            self.include_pos = param_dict['include_pos']
            self.include_morph = param_dict['include_morph']
            self.include_dev = param_dict['include_dev']
            self.include_test = param_dict['include_test']
            self.min_token_freq_emb = int(param_dict['min_token_freq_emb'])
            self.halve_lr_at = int(param_dict['halve_lr_at'])
            self.max_token_len = int(param_dict['max_token_len'])
            self.min_lem_cnt = int(param_dict['min_lem_cnt'])

        if overwrite is not None:
            # Overwrite should be a dict of attributes to change value of the trainer
            for key, value in overwrite.items():
                self.__setattr__(key, value)
        
        # create a models directory if it isn't there already:
        if not os.path.isdir(self.model_dir):
            os.mkdir(model_dir)

        # initialize:
        self.setup = False
        self.curr_nb_epochs = 0

        self.train_tokens, self.dev_tokens, self.test_tokens = None, None, None
        self.train_lemmas, self.dev_lemmas, self.test_lemmas = None, None, None
        self.train_pos, self.dev_pos, self.test_pos = None, None, None
        self.train_morph, self.dev_morph, self.test_morph = None, None, None

        if load:
            self.load()

    def load(self):
        print('Re-loading preprocessor...')
        self.preprocessor = pickle.load(open(os.sep.join((self.model_dir, \
                                    'preprocessor.p')), 'rb'))
        print('Re-loading pretrainer...')
        self.pretrainer = pickle.load(open(os.sep.join((self.model_dir, \
                                    'pretrainer.p')), 'rb'))
        print('Re-building model...')
        self.model = model_from_json(open(os.sep.join((self.model_dir, 'model_architecture.json'))).read())
        self.model.load_weights(os.sep.join((self.model_dir, 'model_weights.hdf5')))

        loss_dict = {}
        idx_cnt = 0
        if self.include_lemma:
            loss_dict['lemma_out'] = 'categorical_crossentropy'
            self.lemma_out_idx = idx_cnt
            idx_cnt += 1
            print('Loading known lemmas...')
            self.known_lemmas = pickle.load(open(os.sep.join((self.model_dir, \
                                    'known_lemmas.p')), 'rb'))

        if self.include_pos:
            loss_dict['pos_out'] = 'categorical_crossentropy'
            self.pos_out_idx = idx_cnt
            idx_cnt += 1
        if self.include_morph:
            self.morph_out_idx = idx_cnt
            idx_cnt += 1
            if self.include_morph == 'label':
              loss_dict['morph_out'] = 'categorical_crossentropy'
            elif self.include_morph == 'multilabel':
              loss_dict['morph_out'] = 'binary_crossentropy'

        self.model.compile(optimizer='adadelta', loss=loss_dict)

    def setup_to_train(self, train_data=None, dev_data=None, test_data=None):
        # create a model directory:
        if os.path.isdir(self.model_dir):
            shutil.rmtree(self.model_dir)
        os.mkdir(self.model_dir)

        self.train_tokens = train_data['token']
        if self.include_test:
            self.test_tokens = test_data['token']
        if self.include_dev:
            self.dev_tokens = dev_data['token']

        idx_cnt = 0
        if self.include_lemma:
            self.lemma_out_idx = idx_cnt
            idx_cnt += 1
            self.train_lemmas = train_data['lemma']
            self.known_lemmas = set(self.train_lemmas)
            if self.include_dev:
                self.dev_lemmas = dev_data['lemma']            
            if self.include_test:
                self.test_lemmas = test_data['lemma']
        if self.include_pos:
            self.pos_out_idx = idx_cnt
            idx_cnt += 1
            self.train_pos = train_data['pos']
            if self.include_dev:
                self.dev_pos = dev_data['pos']
            if self.include_test:
                self.test_pos = test_data['pos']
        if self.include_morph:
            self.morph_out_idx = idx_cnt
            self.train_morph = train_data['morph']
            if self.include_dev:
                self.dev_morph = dev_data['morph']
            if self.include_test:
                self.test_morph = test_data['morph']

        self.preprocessor = Preprocessor().fit(tokens=self.train_tokens,
                                               lemmas=self.train_lemmas,
                                               pos=self.train_pos,
                                               morph=self.train_morph,
                                               include_lemma=self.include_lemma,
                                               include_morph=self.include_morph,
                                               max_token_len=self.max_token_len,
                                               focus_repr=self.focus_repr,
                                               min_lem_cnt=self.min_lem_cnt,
                                               )
        self.pretrainer = Pretrainer(nb_left_tokens=self.nb_left_tokens,
                                     nb_right_tokens=self.nb_right_tokens,
                                     size=self.nb_embedding_dims,
                                     minimum_count=self.min_token_freq_emb)
        self.pretrainer.fit(tokens=self.train_tokens)

        train_transformed = self.preprocessor.transform(tokens=self.train_tokens,
                                               lemmas=self.train_lemmas,
                                               pos=self.train_pos,
                                               morph=self.train_morph)
        if self.include_dev:
            dev_transformed = self.preprocessor.transform(tokens=self.dev_tokens,
                                        lemmas=self.dev_lemmas,
                                        pos=self.dev_pos,
                                        morph=self.dev_morph)
        if self.include_test:
            test_transformed = self.preprocessor.transform(tokens=self.test_tokens,
                                        lemmas=self.test_lemmas,
                                        pos=self.test_pos,
                                        morph=self.test_morph)

        self.train_X_focus = train_transformed['X_focus']
        if self.include_dev:
            self.dev_X_focus = dev_transformed['X_focus']
        if self.include_test:
            self.test_X_focus = test_transformed['X_focus']

        if self.include_lemma:
            self.train_X_lemma = train_transformed['X_lemma']
            if self.include_dev:
                self.dev_X_lemma = dev_transformed['X_lemma']
            if self.include_test:
                self.test_X_lemma = test_transformed['X_lemma']

        if self.include_pos:
            self.train_X_pos = train_transformed['X_pos']
            if self.include_dev:
                self.dev_X_pos = dev_transformed['X_pos']
            if self.include_test:
                self.test_X_pos = test_transformed['X_pos']

        if self.include_morph:
            self.train_X_morph = train_transformed['X_morph']
            if self.include_dev:
                self.dev_X_morph = dev_transformed['X_morph']
            if self.include_test:
                self.test_X_morph = test_transformed['X_morph']

        self.train_contexts = self.pretrainer.transform(tokens=self.train_tokens)
        if self.include_dev:
            self.dev_contexts = self.pretrainer.transform(tokens=self.dev_tokens)
        if self.include_test:
            self.test_contexts = self.pretrainer.transform(tokens=self.test_tokens)
        
        print('Building model...')
        nb_tags = None
        try:
            nb_tags = len(self.preprocessor.pos_encoder.classes_)
        except AttributeError:
            pass
        nb_morph_cats = None
        try:
            nb_morph_cats = self.preprocessor.nb_morph_cats
        except AttributeError:
            pass
        max_token_len, token_char_dict = None, None
        try:
            max_token_len = self.preprocessor.max_token_len
            token_char_dict = self.preprocessor.token_char_dict
        except AttributeError:
            pass
        max_lemma_len, lemma_char_dict = None, None
        try:
            max_lemma_len = self.preprocessor.max_lemma_len
            lemma_char_dict = self.preprocessor.lemma_char_dict
        except AttributeError:
            pass
        nb_lemmas = None
        try:
            nb_lemmas = len(self.preprocessor.lemma_encoder.classes_)
        except AttributeError:
            pass
        self.model = build_model(token_len=max_token_len,
                             token_char_vector_dict=token_char_dict,
                             lemma_len=max_lemma_len,
                             nb_tags=nb_tags,
                             nb_morph_cats=nb_morph_cats,
                             lemma_char_vector_dict=lemma_char_dict,
                             nb_encoding_layers=self.nb_encoding_layers,
                             nb_dense_dims=self.nb_dense_dims,
                             nb_embedding_dims=self.nb_embedding_dims,
                             nb_train_tokens=len(self.pretrainer.train_token_vocab),
                             nb_context_tokens=self.nb_context_tokens,
                             pretrained_embeddings=self.pretrainer.pretrained_embeddings,
                             include_token=self.include_token,
                             include_context=self.include_context,
                             include_lemma=self.include_lemma,
                             include_pos=self.include_pos,
                             include_morph=self.include_morph,
                             nb_filters = self.nb_filters,
                             filter_length = self.filter_length,
                             focus_repr = self.focus_repr,
                             dropout_level = self.dropout_level,
                             nb_lemmas = nb_lemmas,
                            )
        self.save()
        self.setup = True

    def train(self, nb_epochs=None):
        if nb_epochs:
            self.nb_epochs = nb_epochs
        for i in range(self.nb_epochs):
            scores = self.epoch()
        return scores

    def print_stats(self):
        print('Train stats:')
        utils.stats(tokens=self.train_tokens, lemmas=self.train_lemmas, known=self.preprocessor.known_tokens)
        print('Test stats:')
        utils.stats(tokens=self.test_tokens, lemmas=self.test_lemmas, known=self.preprocessor.known_tokens)

    def test(self, multilabel_threshold=0.5):
        if not self.include_test:
            raise ValueError('Please do not call .test() if no test data is available.')

        score_dict = {}

        # get test predictions:
        test_in = {}
        if self.include_token:
            test_in['focus_in'] = self.test_X_focus
        if self.include_context:
            test_in['context_in'] = self.test_contexts

        test_preds = self.model.predict(test_in,
                                batch_size=self.batch_size)

        if isinstance(test_preds, np.ndarray):
            test_preds = [test_preds]

        if self.include_lemma:
            print('::: Test scores (lemmas) :::')
            
            pred_lemmas = self.preprocessor.inverse_transform_lemmas(predictions=test_preds[self.lemma_out_idx])
            if self.postcorrect:
                for i in range(len(pred_lemmas)):
                    if pred_lemmas[i] not in self.known_lemmas:
                        pred_lemmas[i] = min(self.known_lemmas,
                                        key=lambda x: editdistance.eval(x, pred_lemmas[i]))
            score_dict['test_lemma'] = evaluation.single_label_accuracies(gold=self.test_lemmas,
                                                 silver=pred_lemmas,
                                                 test_tokens=self.test_tokens,
                                                 known_tokens=self.preprocessor.known_tokens)

        if self.include_pos:
            print('::: Test scores (pos) :::')
            pred_pos = self.preprocessor.inverse_transform_pos(predictions=test_preds[self.pos_out_idx])
            score_dict['test_pos'] = evaluation.single_label_accuracies(gold=self.test_pos,
                                                 silver=pred_pos,
                                                 test_tokens=self.test_tokens,
                                                 known_tokens=self.preprocessor.known_tokens)
        
        if self.include_morph:     
            print('::: Test scores (morph) :::')
            pred_morph = self.preprocessor.inverse_transform_morph(predictions=test_preds[self.morph_out_idx],
                                                                   threshold=multilabel_threshold)
            if self.include_morph == 'label':
                score_dict['test_morph'] = evaluation.single_label_accuracies(gold=self.test_morph,
                                                 silver=pred_morph,
                                                 test_tokens=self.test_tokens,
                                                 known_tokens=self.preprocessor.known_tokens)                
            elif self.include_morph == 'multilabel':
                score_dict['test_morph'] = evaluation.multilabel_accuracies(gold=self.test_morph,
                                                 silver=pred_morph,
                                                 test_tokens=self.test_tokens,
                                                 known_tokens=self.preprocessor.known_tokens)
        return score_dict

    def save(self):
        # save architecture:
        json_string = self.model.to_json()
        with open(os.sep.join((self.model_dir, 'model_architecture.json')), 'wb') as f:
            f.write(json_string.encode())
        # save weights:
        self.model.save_weights(os.sep.join((self.model_dir, 'model_weights.hdf5')), overwrite=True)
        # save preprocessor:
        with open(os.sep.join((self.model_dir, 'preprocessor.p')), 'wb') as f:
            pickle.dump(self.preprocessor, f)
        # save pretrainer:
        with open(os.sep.join((self.model_dir, 'pretrainer.p')), 'wb') as f:
            pickle.dump(self.pretrainer, f)
        if self.include_lemma:
            # save known lemmas:
            with open(os.sep.join((self.model_dir, 'known_lemmas.p')), 'wb') as f:
                pickle.dump(self.known_lemmas, f)
        # save config file:
        if self.config_path:
            # make sure that we can reproduce parametrization when reloading:
            if not self.config_path == os.sep.join((self.model_dir, 'config.txt')):
                shutil.copy(self.config_path, os.sep.join((self.model_dir, 'config.txt')))
        else:
            with open(os.sep.join((self.model_dir, 'config.txt')), 'w') as F:
                F.write('# Parameter file\n\n[global]\n')
                F.write('nb_encoding_layers = '+str(self.nb_encoding_layers)+'\n')
                F.write('nb_dense_dims = '+str(self.nb_dense_dims)+'\n')
                F.write('batch_size = '+str(self.batch_size)+'\n')
                F.write('nb_left_tokens = '+str(self.nb_left_tokens)+'\n')
                F.write('nb_right_tokens = '+str(self.nb_right_tokens)+'\n')
                F.write('nb_embedding_dims = '+str(self.nb_embedding_dims)+'\n')
                F.write('model_dir = '+str(self.model_dir)+'\n')
                F.write('postcorrect = '+str(self.postcorrect)+'\n')
                F.write('nb_filters = '+str(self.nb_filters)+'\n')
                F.write('filter_length = '+str(self.filter_length)+'\n')
                F.write('focus_repr = '+str(self.focus_repr)+'\n')
                F.write('dropout_level = '+str(self.dropout_level)+'\n')
                F.write('include_token = '+str(self.include_context)+'\n')
                F.write('include_context = '+str(self.include_context)+'\n')
                F.write('include_lemma = '+str(self.include_lemma)+'\n')
                F.write('include_pos = '+str(self.include_pos)+'\n')
                F.write('include_morph = '+str(self.include_morph)+'\n')
                F.write('include_dev = '+str(self.include_dev)+'\n')
                F.write('include_test = '+str(self.include_test)+'\n')
                F.write('nb_epochs = '+str(self.nb_epochs)+'\n')
                F.write('halve_lr_at = '+str(self.halve_lr_at)+'\n')
                F.write('max_token_len = '+str(self.max_token_len)+'\n')
                F.write('min_token_freq_emb = '+str(self.min_token_freq_emb)+'\n')
                F.write('min_lem_cnt = '+str(self.min_lem_cnt)+'\n')
        
        # plot current embeddings:
        if self.include_context:
            layer_dict = dict([(layer.name, layer) for layer in self.model.layers])
            weights = layer_dict['context_embedding'].get_weights()[0]
            X = np.array([weights[self.pretrainer.train_token_vocab.index(w), :] \
                    for w in self.pretrainer.mfi \
                      if w in self.pretrainer.train_token_vocab], dtype='float32')
            # dimension reduction:
            tsne = TSNE(n_components=2)
            coor = tsne.fit_transform(X) # unsparsify
            plt.clf(); sns.set_style('dark')
            sns.plt.rcParams['axes.linewidth'] = 0.4
            fig, ax1 = sns.plt.subplots()  
            labels = self.pretrainer.mfi
            # first plot slices:
            x1, x2 = coor[:,0], coor[:,1]
            ax1.scatter(x1, x2, 100, edgecolors='none', facecolors='none')
            # clustering on top (add some colouring):
            clustering = AgglomerativeClustering(linkage='ward',
                            affinity='euclidean', n_clusters=8)
            clustering.fit(coor)
            # add names:
            for x, y, name, cluster_label in zip(x1, x2, labels, clustering.labels_):
                ax1.text(x, y, name, ha='center', va="center",
                         color=plt.cm.spectral(cluster_label / 10.),
                         fontdict={'family': 'Arial', 'size': 8})
            # control aesthetics:
            ax1.set_xlabel(''); ax1.set_ylabel('')
            ax1.set_xticklabels([]); ax1.set_xticks([])
            ax1.set_yticklabels([]); ax1.set_yticks([])
            sns.plt.savefig(os.sep.join((self.model_dir, 'embed_after.pdf')),
                            bbox_inches=0)

    def epoch(self, autosave=True):
        if not self.setup:
            raise ValueError('Not set up yet... Call Tagger.setup_() first.')

        # update nb of epochs ran so far:
        self.curr_nb_epochs += 1
        print("-> epoch ", self.curr_nb_epochs, "...")

        if self.curr_nb_epochs and self.halve_lr_at:
            # update learning rate at specific points:
            if self.curr_nb_epochs % self.halve_lr_at == 0:
                old_lr = K.get_value(self.model.optimizer.lr)
                new_lr = np.float32(old_lr * 0.5)
                K.set_value(self.model.optimizer.lr, new_lr)
                print('\t- Lowering learning rate > was:', old_lr, ', now:', new_lr)

        # get inputs and outputs straight:
        train_in, train_out = {}, {}
        if self.include_token:
            train_in['focus_in'] = self.train_X_focus
        if self.include_context:
            train_in['context_in'] = self.train_contexts

        if self.include_lemma:
            train_out['lemma_out'] = self.train_X_lemma
        if self.include_pos:
            train_out['pos_out'] = self.train_X_pos
        if self.include_morph:
            train_out['morph_out'] = self.train_X_morph
        
        self.model.fit(train_in, train_out,
              nb_epoch = 1,
              shuffle = True,
              batch_size = self.batch_size)

        # get train preds:
        train_preds = self.model.predict(train_in,
                                batch_size=self.batch_size)
        if isinstance(train_preds, np.ndarray):
            train_preds = [train_preds]

        if self.include_dev:
            dev_in = {}
            if self.include_token:
                dev_in['focus_in'] = self.dev_X_focus
            if self.include_context:
                dev_in['context_in'] = self.dev_contexts

            dev_preds = self.model.predict(dev_in,
                                    batch_size=self.batch_size)
            if isinstance(dev_preds, np.ndarray):
                dev_preds = [dev_preds]

        score_dict = {}
        if self.include_lemma:
            print('::: Train scores (lemmas) :::')
            pred_lemmas = self.preprocessor.inverse_transform_lemmas(predictions=train_preds[self.lemma_out_idx])
            score_dict['train_lemma'] = evaluation.single_label_accuracies(gold=self.train_lemmas,
                                                 silver=pred_lemmas,
                                                 test_tokens=self.train_tokens,
                                                 known_tokens=self.preprocessor.known_tokens)
            if self.include_dev:
                print('::: Dev scores (lemmas) :::')
                pred_lemmas = self.preprocessor.inverse_transform_lemmas(predictions=dev_preds[self.lemma_out_idx])
                score_dict['dev_lemma'] = evaluation.single_label_accuracies(gold=self.dev_lemmas,
                                                     silver=pred_lemmas,
                                                     test_tokens=self.dev_tokens,
                                                     known_tokens=self.preprocessor.known_tokens)
                
                if self.postcorrect:
                    print('::: Dev scores (lemmas) -> postcorrected :::')
                    for i in range(len(pred_lemmas)):
                        if pred_lemmas[i] not in self.known_lemmas:
                            pred_lemmas[i] = min(self.known_lemmas,
                                            key=lambda x: editdistance.eval(x, pred_lemmas[i]))
                    score_dict['dev_lemma_postcorrect'] = evaluation.single_label_accuracies(gold=self.dev_lemmas,
                                                     silver=pred_lemmas,
                                                     test_tokens=self.dev_tokens,
                                                     known_tokens=self.preprocessor.known_tokens)

        if self.include_pos:
            print('::: Train scores (pos) :::')
            pred_pos = self.preprocessor.inverse_transform_pos(predictions=train_preds[self.pos_out_idx])
            score_dict['train_pos'] = evaluation.single_label_accuracies(gold=self.train_pos,
                                                 silver=pred_pos,
                                                 test_tokens=self.train_tokens,
                                                 known_tokens=self.preprocessor.known_tokens)
            if self.include_dev:
                print('::: Dev scores (pos) :::')
                pred_pos = self.preprocessor.inverse_transform_pos(predictions=dev_preds[self.pos_out_idx])
                score_dict['dev_pos'] = evaluation.single_label_accuracies(gold=self.dev_pos,
                                                     silver=pred_pos,
                                                     test_tokens=self.dev_tokens,
                                                     known_tokens=self.preprocessor.known_tokens)
        
        if self.include_morph:
            print('::: Train scores (morph) :::')
            pred_morph = self.preprocessor.inverse_transform_morph(predictions=train_preds[self.morph_out_idx])
            if self.include_morph == 'label':
                score_dict['train_morph'] = evaluation.single_label_accuracies(gold=self.train_morph,
                                                 silver=pred_morph,
                                                 test_tokens=self.train_tokens,
                                                 known_tokens=self.preprocessor.known_tokens)
            elif self.include_morph == 'multilabel':
                score_dict['train_morph'] = evaluation.multilabel_accuracies(gold=self.train_morph,
                                                 silver=pred_morph,
                                                 test_tokens=self.train_tokens,
                                                 known_tokens=self.preprocessor.known_tokens)


            if self.include_dev:
                print('::: Dev scores (morph) :::')
                pred_morph = self.preprocessor.inverse_transform_morph(predictions=dev_preds[self.morph_out_idx])
                if self.include_morph == 'label':
                    score_dict['dev_morph'] = evaluation.single_label_accuracies(gold=self.train_morph,
                                                     silver=pred_morph,
                                                     test_tokens=self.dev_tokens,
                                                     known_tokens=self.preprocessor.known_tokens)
                elif self.include_morph == 'multilabel':
                    score_dict['dev_morph'] = evaluation.multilabel_accuracies(gold=self.train_morph,
                                                     silver=pred_morph,
                                                     test_tokens=self.dev_tokens,
                                                     known_tokens=self.preprocessor.known_tokens)

        if autosave:
            self.save()
        
        return score_dict

    def annotate(self, tokens):
        X_focus = self.preprocessor.transform(tokens=tokens)['X_focus']
        X_context = self.pretrainer.transform(tokens=tokens)
        
        # get predictions:
        new_in = {}
        if self.include_token:
            new_in['focus_in'] = X_focus
        if self.include_context:
            new_in['context_in'] = X_context
        preds = self.model.predict(new_in)

        if isinstance(preds, np.ndarray):
            preds = [preds]
        
        annotation_dict = {'tokens': tokens}
        if self.include_lemma:
            pred_lemmas = self.preprocessor.inverse_transform_lemmas(predictions=preds[self.lemma_out_idx])
            annotation_dict['lemmas'] = pred_lemmas
            if self.postcorrect:
                for i in range(len(pred_lemmas)):
                    if pred_lemmas[i] not in self.known_lemmas:
                        pred_lemmas[i] = min(self.known_lemmas,
                                            key=lambda x: editdistance.eval(x, pred_lemmas[i]))
                annotation_dict['postcorrect_lemmas'] = pred_lemmas

        if self.include_pos:
            pred_pos = self.preprocessor.inverse_transform_pos(predictions=preds[self.pos_out_idx])
            annotation_dict['pos'] = pred_pos
        
        if self.include_morph:
            pred_morph = self.preprocessor.inverse_transform_morph(predictions=preds[self.morph_out_idx])
            annotation_dict['morph'] = pred_morph

        return annotation_dict
        

        


                
    
        

        
        

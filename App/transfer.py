#!/usr/bin/env python
# coding: utf-8

import warnings
warnings.filterwarnings("ignore")

import copy
import os
import time

import crepe
import ddsp
import ddsp.training
import gin
import librosa
import matplotlib.pyplot as plt
import numpy as np
import pickle
import tensorflow.compat.v2 as tf
import tensorflow_datasets as tfds
import tensorflow_io as tfio
from IPython import display
import os
from IPython.display import Audio

def play(audio):
    return Audio(audio, rate=16000)

# Helper Functions
sample_rate = 16000


print('Done!')




class TimbreTransfer():
    def __init__(self,model_dir='clarinet',features='hbd.pkl'):
        
        self.model_dir = model_dir
        with open(features, 'rb') as f:
            self.audio_features = pickle.load(f)
        self.audio = self.audio_features['audio']
        self.model = None
        
    def fit(self):
        # Parse the gin config.
        gin_file = os.path.join(self.model_dir, 'operative_config-0.gin')
        with gin.unlock_config():
            gin.parse_config_file(gin_file, skip_unknown=True)

        # Assumes only one checkpoint in the folder, 'ckpt-[iter]`.
        ckpt_files = [f for f in tf.io.gfile.listdir(self.model_dir) if 'ckpt' in f]
        ckpt_name = ckpt_files[0].split('.')[0]
        ckpt = os.path.join(self.model_dir, ckpt_name)

        # Ensure dimensions and sampling rates are equal
        time_steps_train = gin.query_parameter('F0LoudnessPreprocessor.time_steps')
        n_samples_train = gin.query_parameter('Harmonic.n_samples')
        hop_size = int(n_samples_train / time_steps_train)

        time_steps = int(self.audio.shape[1] / hop_size)
        n_samples = time_steps * hop_size

        gin_params = [
            'Harmonic.n_samples = {}'.format(n_samples),
            'FilteredNoise.n_samples = {}'.format(n_samples),
            'F0LoudnessPreprocessor.time_steps = {}'.format(time_steps),
            'oscillator_bank.use_angular_cumsum = True',  # Avoids cumsum accumulation errors.
        ]

        with gin.unlock_config():
            gin.parse_config(gin_params)

        # Trim all input vectors to correct lengths 
        for key in ['f0_hz', 'f0_confidence', 'loudness_db']:
            self.audio_features[key] = self.audio_features[key][:time_steps]
        self.audio_features['audio'] = self.audio_features['audio'][:, :n_samples]


        # Set up the model just to predict audio given new conditioning
        self.model = ddsp.training.models.Autoencoder()
        self.model.restore(ckpt)

        # Build model by running a batch through it.
        start_time = time.time()
        _ = self.model(self.audio_features, training=False)
        print('Restoring model took %.1f seconds' % (time.time() - start_time))
        
    def resynth(self):
        # Resynthesize audio.
        outputs = self.model(self.audio_features, training=False)
        audio_gen = self.model.get_audio_from_outputs(outputs)
        return audio_gen
        

'''useage:
import IPython.display
import logging
tf.get_logger().setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

clarinet = TimbreTransfer('violin','jolene-2.pkl')
clarinet.fit()
IPython.display.display(
play(clarinet.audio))
IPython.display.display(
play(clarinet.resynth()))

'''
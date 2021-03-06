from collections import OrderedDict

import h5py
import numpy as np
import tensorflow as tf
import os
import sys


def fatal_error(message):
  tf.logging.log(tf.logging.ERROR, message)
  sys.exit(1)


def init_logging(verbosity):
  tf.logging.set_verbosity(verbosity)
  tf.logging.log(tf.logging.INFO, "Using Python version %s" % sys.version)
  tf.logging.log(tf.logging.INFO, "Using TensorFlow version %s" % tf.__version__)


def batch_str_decode(string_array, codec='utf-8'):
  string_array = np.array(string_array)
  return np.reshape(np.array(list(map(lambda p: p if not p or isinstance(p, str) else p.decode(codec),
                             np.reshape(string_array, [-1])))), string_array.shape)


def sequence_mask_np(lengths, maxlen=None):
  if not maxlen:
    maxlen = np.max(lengths)
  return np.arange(maxlen) < np.array(lengths)[:, None]


def get_immediate_subdirectories(a_dir):
  return [name for name in os.listdir(a_dir) if os.path.isdir(os.path.join(a_dir, name))]


def load_transitions(transition_statistics, num_classes, vocab_map):
  transition_statistics_np = np.zeros((num_classes, num_classes))
  # for t1 in vocab_map.keys():
  #   for t2 in vocab_map.keys():
  #     if t1 in ["L", "O"] and t2 in ["U", "B"]:
  #       transition_statistics_np[vocab_map[t1], vocab_map[t2]] +=1
  with open(transition_statistics, 'r') as f:
    for line in f:
      tag1, tag2, prob = line.split("\t")
      transition_statistics_np[vocab_map[tag1], vocab_map[tag2]] = float(prob)
      # print("debug <loaded matrix {}, {}>: ".format(vocab_map[tag1], vocab_map[tag2]), transition_statistics_np[vocab_map[tag1], vocab_map[tag2]])
  # transition_statistics_np[0, 0] = np.sum(transition_statistics_np[0, 1:])
  # print(transition_statistics_np[0, 0])
  print("zero_ind", np.where(np.sum(transition_statistics_np, axis=-1, keepdims=True) == 0))
  transition_statistics_np = transition_statistics_np / np.sum(transition_statistics_np, axis=-1, keepdims=True)
  transition_statistics_np = np.nan_to_num(transition_statistics_np)
  tf.logging.log(tf.logging.INFO, "Loaded pre-computed transition statistics: %s" % transition_statistics)
  return transition_statistics_np


def load_pretrained_embeddings(pretrained_fname):
  tf.logging.log(tf.logging.INFO, "Loading pre-trained embedding file: %s" % pretrained_fname)

  # TODO: np.loadtxt refuses to work for some reason
  # pretrained_embeddings = np.loadtxt(self.args.word_embedding_file, usecols=range(1, word_embedding_size+1))
  pretrained_embeddings = []
  with open(pretrained_fname, 'r', encoding="utf-8") as f:
    for line in f:
      split_line = line.split(' ')
      try:
        embedding = list(map(float, split_line[1:]))
      except Exception:
        print(split_line[1:])
      pretrained_embeddings.append(embedding)
  pretrained_embeddings = np.array(pretrained_embeddings)
  pretrained_embeddings /= np.std(pretrained_embeddings)
  return pretrained_embeddings

def load_cached_pretrained_embedding(pretrained_fname, cwr_type):
  table = []
  cnt = 0
  with h5py.File(pretrained_fname, 'r') as fin:
    for idx in range(len(fin)):
      sentence = fin[str(idx)]
    # for idx, sentence in fin.items():
    #   print(idx)
      assert str(idx) == str(cnt)
      if cwr_type == 'ELMo':
        token_table = np.concatenate([sentence[idx] for idx in range(3)], -1) #default with 3 layers#tf.reshape(sentence, [3, 2])#np.transpose(sentence, (1, 0, 2))
      elif cwr_type == 'BERT':
        token_table = sentence[()]
        # print(token_table)
      else:
        tf.logging.fatal("Unknown CWR type")
      # print(token_table)
      table.append(token_table)

      cnt+=1
  print(len(table))
  return np.concatenate(table, axis=0)


def get_token_take_mask(task, task_config, outputs, labels = None):
  ## Hard patch here!
  task_map = task_config[task]
  token_take_mask = None
  if "token_take_mask" in task_map and "layer" in task_map["token_take_mask"]:
    token_take_conf = task_map["token_take_mask"]
    token_take_mask = outputs["%s_%s" % (token_take_conf["layer"], token_take_conf["output"])]
  elif "token_take_mask" in task_map and "label" in task_map["token_take_mask"]:
    token_take_conf = task_map["token_take_mask"]
    assert labels is not None
    token_take_mask = labels[token_take_conf["label"]]
    # token_take_mask = tf.one_hot(token_take_mask, dtype = tf.int32, depth = token_take_mask.shape[-1])





  return token_take_mask


def load_transition_params(task_config, vocab, train_with_crf = False):
  transition_params = {}
  for layer, task_maps in task_config.items():
    for task, task_map in task_maps.items():
      task_crf = 'crf' in task_map and task_map['crf']
      task_viterbi_decode = task_crf or 'viterbi' in task_map and task_map['viterbi']
      if task_viterbi_decode:
        transition_params_file = task_map['transition_stats'] if 'transition_stats' in task_map else None
        # print("debug <loading transition file for {}>: ".format(task), transition_params_file)
        if not transition_params_file:
          fatal_error("Failed to load transition stats for task '%s' with crf=%r and viterbi=%r" %
                      (task, task_crf, task_viterbi_decode))
        if transition_params_file and task_viterbi_decode:
          # if not train_with_crf:
          transitions = load_transitions(transition_params_file, vocab.vocab_names_sizes[task],
                                              vocab.vocab_maps[task])
          # else:
          #   with tf.variable_scope("transition_mtx_for_{}".format(task)):
          #     transitions = tf.get_variable("transition_mtx", [vocab.vocab_names_sizes[task], vocab.vocab_names_sizes[task]])
          transition_params[task] = transitions
  return transition_params


def load_feat_label_idx_maps(data_config):
  feature_idx_map = {}
  label_idx_map = {}
  for i, f in enumerate([d for d in data_config.keys() if
                       ('feature' in data_config[d] and data_config[d]['feature']) or
                       ('label' in data_config[d] and data_config[d]['label'])]):
    if 'feature' in data_config[f] and data_config[f]['feature']:
      feature_idx_map[f] = i
    if 'label' in data_config[f] and data_config[f]['label']:
      if 'type' in data_config[f] and data_config[f]['type'] == 'range':
        idx = data_config[f]['conll_idx']
        j = i + idx[1] if idx[1] != -1 else -1
        label_idx_map[f] = (i, j)
      else:
        label_idx_map[f] = (i, i+1)
  return feature_idx_map, label_idx_map

def combine_attn_maps(layer_config, attention_config, task_config):
  if attention_config is None:
    attention_config = []
  layer_task_config = OrderedDict({})
  layer_attention_config = OrderedDict({})
  for task_or_attn_name, layer in layer_config.items():
    # print("debug <adding task config {} to {}>".format(task_or_attn_name, layer))
    if isinstance(layer, list):
      for l in layer:
        if task_or_attn_name in attention_config:
          layer_attention_config[l] = attention_config[task_or_attn_name]
        elif task_or_attn_name in task_config:
          fatal_error('list type of layer indicator should only appear in attention config')
        else:
          fatal_error('No task or attention config "%s"' % task_or_attn_name)
    elif isinstance(layer, int):
      if task_or_attn_name in attention_config :
        layer_attention_config[layer] = attention_config[task_or_attn_name]
      elif task_or_attn_name in task_config:
        if layer not in layer_task_config:
          layer_task_config[layer] = OrderedDict({})

        layer_task_config[layer][task_or_attn_name] = task_config[task_or_attn_name]
      else:
        fatal_error('No task or attention config "%s"' % task_or_attn_name)
    else:
      fatal_error('type of layer indicator is not expected')
  # if 'parsed_label'
  return layer_task_config, layer_attention_config

from collections import OrderedDict

import tensorflow as tf
import argparse
import train_utils
import tf_utils
import os
from vocab import Vocab
from model import LISAModel
import util

arg_parser = argparse.ArgumentParser(description='')
arg_parser.add_argument('--test_files',
                        help='Comma-separated list of test data files')
arg_parser.add_argument('--dev_files',
                        help='Comma-separated list of development data files')
arg_parser.add_argument('--save_dir', required=True,
                        help='Directory containing saved model')
# todo load this more generically, so that we can have diff stats per task
arg_parser.add_argument('--transition_stats',
                        help='Transition statistics between labels')
arg_parser.add_argument('--debug', dest='debug', action='store_true',
                        help='Whether to run in debug mode: a little faster and smaller')
arg_parser.add_argument('--data_config', required=True,
                        help='Path to data configuration json')
arg_parser.add_argument('--hparams', type=str,
                        help='Comma separated list of "name=value" hyperparameter settings.')
# todo: are these necessary?
arg_parser.add_argument('--model_configs', required=True,
                        help='Comma-separated list of paths to model configuration json.')
arg_parser.add_argument('--task_configs', required=True,
                        help='Comma-separated list of paths to task configuration json.')
arg_parser.add_argument('--layer_configs', required=True,
                        help='Comma-separated list of paths to layer configuration json.')
arg_parser.add_argument('--attention_configs',
                        help='Comma-separated list of paths to attention configuration json.')
arg_parser.add_argument('--combine_test_files', action='store_true',
                        help='Whether to combine list of test files into a single score.')

arg_parser.add_argument('--okazaki_discounting', dest='okazaki_discounting', action='store_true',
                        help='whether to use okazaki style of discounting method')
# arg_parser.add_argument('--output_attention_weight', dest='output_attention_weight', action='store_true',
#                         help='whether to print out attention weight')

arg_parser.add_argument('--output_attention_weight', dest='output_attention_weight', action='store_true',
                        help='whether to print out attention weight')
arg_parser.add_argument('--parser_dropout', dest='parser_dropout', action='store_true',
                        help='whether to add a dropout layer for parser aggregation')
arg_parser.add_argument('--aggregator_mlp_bn', dest='aggregator_mlp_bn', action='store_true',
                        help='whether to use batch normalization on aggregator mlp')
arg_parser.add_argument('--eval_with_transformation', dest='eval_with_transformation', action='store_true',
                        help='whether to evaluate with result transformation')


arg_parser.set_defaults(debug=False)
arg_parser.set_defaults(combine_test_files=False)


args, leftovers = arg_parser.parse_known_args()

util.init_logging(tf.logging.INFO)

if not os.path.isdir(args.save_dir):
  util.fatal_error("save_dir not found: %s" % args.save_dir)

# Load all the various configurations
# todo: validate json
data_config = train_utils.load_json_configs(args.data_config)
data_config = OrderedDict(sorted(data_config.items(), key=lambda x: x[1]['conll_idx'] if isinstance(x[1]['conll_idx'], int) else x[1]['conll_idx'][0]))
model_config = train_utils.load_json_configs(args.model_configs)
task_config = train_utils.load_json_configs(args.task_configs, args)
layer_config = train_utils.load_json_configs(args.layer_configs)
attention_config = train_utils.load_json_configs(args.attention_configs)

# attention_config = {}
# if args.attention_configs and args.attention_configs != '':
#   attention_config =

# Combine layer, task and layer, attention maps
# layer_task_config = {}
# layer_attention_config = {}
# for task_or_attn_name, layer in layer_config.items():
#   if task_or_attn_name in attention_config:
#     layer_attention_config[layer] = attention_config[task_or_attn_name]
#   elif task_or_attn_name in task_config:
#     if layer not in layer_task_config:
#       layer_task_config[layer] = {}
#     layer_task_config[layer][task_or_attn_name] = task_config[task_or_attn_name]
#   else:
#     util.fatal_error('No task or attention config "%s"' % task_or_attn_name)
layer_task_config, layer_attention_config = util.combine_attn_maps(layer_config, attention_config, task_config)

hparams = train_utils.load_hparams(args, model_config)

dev_filenames = args.dev_files.split(',')
test_filenames = args.test_files.split(',') if args.test_files else []

vocab = Vocab(data_config, args.save_dir)
vocab.update(test_filenames)

embedding_files = [embeddings_map['pretrained_embeddings'] for embeddings_map in model_config['embeddings'].values()
                   if 'pretrained_embeddings' in embeddings_map]

# Generate mappings from feature/label names to indices in the model_fn inputs
# feature_idx_map = {}
# label_idx_map = {}
# for i, f in enumerate([d for d in data_config.keys() if
#                        ('feature' in data_config[d] and data_config[d]['feature']) or
#                        ('label' in data_config[d] and data_config[d]['label'])]):
#   if 'feature' in data_config[f] and data_config[f]['feature']:
#     feature_idx_map[f] = i
#   if 'label' in data_config[f] and data_config[f]['label']:
#     if 'type' in data_config[f] and data_config[f]['type'] == 'range':
#       idx = data_config[f]['conll_idx']
#       j = i + idx[1] if idx[1] != -1 else -1
#       label_idx_map[f] = (i, j)
#     else:
#       label_idx_map[f] = (i, i+1)
feature_idx_map, label_idx_map = util.load_feat_label_idx_maps(data_config)

# Initialize the model
model = LISAModel(hparams, model_config, layer_task_config, layer_attention_config, feature_idx_map, label_idx_map,
                  vocab)
tf.logging.log(tf.logging.INFO, "Created model with %d trainable parameters" % tf_utils.get_num_trainable_parameters())


# Set up the Estimator
estimator = tf.estimator.Estimator(model_fn=model.model_fn, model_dir=args.save_dir)


def dev_input_fn():
  return train_utils.get_input_fn(vocab, data_config, dev_filenames, hparams.batch_size, num_epochs=1, shuffle=False,
                                  embedding_files=embedding_files, is_token_based_batching = hparams.is_token_based_batching)


tf.logging.log(tf.logging.INFO, "Evaluating on dev files: %s" % str(dev_filenames))
estimator.evaluate(input_fn=dev_input_fn)

if args.combine_test_files:
  def test_input_fn():
    return train_utils.get_input_fn(vocab, data_config, test_filenames, hparams.batch_size, num_epochs=1, shuffle=False,
                                    is_token_based_batching = hparams.is_token_based_batching, embedding_files=embedding_files)

  tf.logging.log(tf.logging.INFO, "Evaluating on test files: %s" % str(test_filenames))
  estimator.evaluate(input_fn=test_input_fn)

else:
  for test_file in test_filenames:
    def test_input_fn():
      return train_utils.get_input_fn(vocab, data_config, [test_file], hparams.batch_size, num_epochs=1, shuffle=False,
                                      is_token_based_batching = hparams.is_token_based_batching, embedding_files=embedding_files)


    tf.logging.log(tf.logging.INFO, "Evaluating on test file: %s" % str(test_file))
    estimator.evaluate(input_fn=test_input_fn)


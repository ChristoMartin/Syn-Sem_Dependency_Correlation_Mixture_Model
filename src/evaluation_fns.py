import tensorflow as tf
import evaluation_fns_np
import nn_utils

def create_metric_variable(name, shape, dtype):
  return tf.get_variable(name=name, shape=shape, dtype=dtype, trainable=False,
                         collections=[tf.GraphKeys.LOCAL_VARIABLES, tf.GraphKeys.METRIC_VARIABLES])


def accuracy_tf(predictions, targets, mask):
  with tf.name_scope('accuracy'):
    return tf.metrics.accuracy(labels=targets, predictions=predictions, weights=mask)

def precision_tf(predictions, targets, mask):
  with tf.name_scope('precision'):
    return tf.metrics.precision(labels=targets, predictions=predictions, weights=mask)

def recall_tf(predictions, targets, mask):
  with tf.name_scope('recall'):
    return tf.metrics.precision(labels=targets, predictions=predictions, weights=mask)

def f1_tf(predictions, targets, mask):
  with tf.name_scope('f-score'):
    prec, prec_op = precision_tf(predictions, targets, mask)
    recall, recall_op = recall_tf(predictions, targets, mask)
    return 2*prec*recall/(prec+recall), tf.group([prec_op, recall_op])


def conll_srl_eval_tf(predictions, targets, predicate_predictions, words, mask, predicate_targets, reverse_maps,
                      gold_srl_eval_file, pred_srl_eval_file, pos_predictions, pos_targets):

  with tf.name_scope('conll_srl_eval'):

    # create accumulator variables
    correct_count = create_metric_variable("correct_count", shape=[], dtype=tf.int64)
    excess_count = create_metric_variable("excess_count", shape=[], dtype=tf.int64)
    missed_count = create_metric_variable("missed_count", shape=[], dtype=tf.int64)

    # first, use reverse maps to convert ints to strings
    # predictions = tf.Print(predictions, [predictions], "srl_predictions")
    str_predictions = nn_utils.int_to_str_lookup_table(predictions, reverse_maps['srl'])
    str_words = nn_utils.int_to_str_lookup_table(words, reverse_maps['word'])
    str_targets = nn_utils.int_to_str_lookup_table(targets, reverse_maps['srl'])
    str_pos_predictions = nn_utils.int_to_str_lookup_table(pos_predictions, reverse_maps['gold_pos'])
    str_pos_targets = nn_utils.int_to_str_lookup_table(pos_targets, reverse_maps['gold_pos'])

    # need to pass through the stuff for pyfunc
    # pyfunc is necessary here since we need to write to disk
    py_eval_inputs = [str_predictions, predicate_predictions, str_words, mask, str_targets, predicate_targets,
                      pred_srl_eval_file, gold_srl_eval_file, str_pos_predictions, str_pos_targets]
    out_types = [tf.int64, tf.int64, tf.int64]
    correct, excess, missed = tf.py_func(evaluation_fns_np.conll_srl_eval, py_eval_inputs, out_types, stateful=False)

    update_correct_op = tf.assign_add(correct_count, correct)
    update_excess_op = tf.assign_add(excess_count, excess)
    update_missed_op = tf.assign_add(missed_count, missed)

    precision_update_op = update_correct_op / (update_correct_op + update_excess_op)
    recall_update_op = update_correct_op / (update_correct_op + update_missed_op)
    f1_update_op = 2 * precision_update_op * recall_update_op / (precision_update_op + recall_update_op)

    precision = correct_count / (correct_count + excess_count)
    recall = correct_count / (correct_count + missed_count)


    # precision = tf.Print(precision, [precision], "srl-precision")
    # recall = tf.Print(recall, [recall], "srl-recall")
    f1 = 2 * precision * recall / (precision + recall)
    return f1, f1_update_op

def conll_srl_eval_all_tf(predictions, targets, predicate_predictions, words, mask, predicate_targets, reverse_maps,
                      gold_srl_eval_file, pred_srl_eval_file, pos_predictions, pos_targets):

  with tf.name_scope('conll_srl_eval'):

    # create accumulator variables
    correct_count = create_metric_variable("correct_count", shape=[], dtype=tf.int64)
    excess_count = create_metric_variable("excess_count", shape=[], dtype=tf.int64)
    missed_count = create_metric_variable("missed_count", shape=[], dtype=tf.int64)

    # first, use reverse maps to convert ints to strings
    # predictions = tf.Print(predictions, [predictions], "srl_predictions")
    str_predictions = nn_utils.int_to_str_lookup_table(predictions, reverse_maps['srl'])
    str_words = nn_utils.int_to_str_lookup_table(words, reverse_maps['word'])
    str_targets = nn_utils.int_to_str_lookup_table(targets, reverse_maps['srl'])
    str_pos_predictions = nn_utils.int_to_str_lookup_table(pos_predictions, reverse_maps['gold_pos'])
    str_pos_targets = nn_utils.int_to_str_lookup_table(pos_targets, reverse_maps['gold_pos'])

    # need to pass through the stuff for pyfunc
    # pyfunc is necessary here since we need to write to disk
    py_eval_inputs = [str_predictions, predicate_predictions, str_words, mask, str_targets, predicate_targets,
                      pred_srl_eval_file, gold_srl_eval_file, str_pos_predictions, str_pos_targets]
    out_types = [tf.int64, tf.int64, tf.int64]
    correct, excess, missed = tf.py_func(evaluation_fns_np.conll_srl_eval, py_eval_inputs, out_types, stateful=False)

    update_correct_op = tf.assign_add(correct_count, correct)
    update_excess_op = tf.assign_add(excess_count, excess)
    update_missed_op = tf.assign_add(missed_count, missed)

    precision_update_op = update_correct_op / (update_correct_op + update_excess_op)
    recall_update_op = update_correct_op / (update_correct_op + update_missed_op)
    f1_update_op = 2 * precision_update_op * recall_update_op / (precision_update_op + recall_update_op)

    precision = correct_count / (correct_count + excess_count)
    recall = correct_count / (correct_count + missed_count)


    # precision = tf.Print(precision, [precision], "srl-precision")
    # recall = tf.Print(recall, [recall], "srl-recall")
    f1 = 2 * precision * recall / (precision + recall)
    return [precision, recall, f1], f1_update_op


def conll09_srl_eval_tf(predictions, targets, predicate_predictions, words, mask, predicate_targets, reverse_maps,
                      gold_srl_eval_file, pred_srl_eval_file, pos_predictions, pos_targets, parse_head_targets,
                        parse_head_predictions, parse_label_targets, parse_label_predictions, pred_sense, gold_sense):

  with tf.name_scope('conll_srl_eval'):

    # create accumulator variables
    with tf.variable_scope('conll_srl_eval_vars'):
      correct_count = create_metric_variable("correct_count", shape=[], dtype=tf.int64)
      excess_count = create_metric_variable("excess_count", shape=[], dtype=tf.int64)
      missed_count = create_metric_variable("missed_count", shape=[], dtype=tf.int64)

    # first, use reverse maps to convert ints to strings
    str_predictions = nn_utils.int_to_str_lookup_table(predictions, reverse_maps['srl'])
    str_words = nn_utils.int_to_str_lookup_table(words, reverse_maps['word'])
    str_srl_targets = nn_utils.int_to_str_lookup_table(targets, reverse_maps['srl'])
    str_parse_label_targets = nn_utils.int_to_str_lookup_table(parse_label_targets, reverse_maps['parse_label'])
    str_parse_label_predictions = nn_utils.int_to_str_lookup_table(parse_label_predictions, reverse_maps['parse_label'])
    str_pos_predictions = nn_utils.int_to_str_lookup_table(pos_predictions, reverse_maps['gold_pos'])
    str_pos_targets = nn_utils.int_to_str_lookup_table(pos_targets, reverse_maps['gold_pos'])
    str_predicate_predictions = nn_utils.int_to_str_lookup_table(predicate_predictions, reverse_maps['predicate'])
    str_predicate_targets = nn_utils.int_to_str_lookup_table(predicate_targets, reverse_maps['predicate'])

    # need to pass through the stuff for pyfunc
    # pyfunc is necessary here since we need to write to disk
    py_eval_inputs = [str_predictions, str_predicate_predictions, str_words, mask, str_srl_targets, str_predicate_targets,
                      str_parse_label_predictions, parse_head_predictions, str_parse_label_targets, parse_head_targets,
                      str_pos_targets, str_pos_predictions, pred_srl_eval_file, gold_srl_eval_file, pred_sense, gold_sense]
    out_types = [tf.int64, tf.int64, tf.int64]
    correct, excess, missed = tf.py_func(evaluation_fns_np.conll09_srl_eval, py_eval_inputs, out_types, stateful=False)

    update_correct_op = tf.assign_add(correct_count, correct)
    update_excess_op = tf.assign_add(excess_count, excess)
    update_missed_op = tf.assign_add(missed_count, missed)

    precision_update_op = update_correct_op / (update_correct_op + update_excess_op)
    recall_update_op = update_correct_op / (update_correct_op + update_missed_op)
    f1_update_op = 2 * precision_update_op * recall_update_op / (precision_update_op + recall_update_op)

    precision = correct_count / (correct_count + excess_count)
    recall = correct_count / (correct_count + missed_count)
    f1 = 2 * precision * recall / (precision + recall)

    return f1, f1_update_op
def conll09_srl_eval_srl_only_tf(predictions, targets, predicate_predictions, words, mask, predicate_targets, reverse_maps,
                      gold_srl_eval_file, pred_srl_eval_file, pos_predictions, pos_targets, parse_head_targets,
                        parse_head_predictions, parse_label_targets, parse_label_predictions, pred_sense, gold_sense):

  with tf.name_scope('conll_srl_eval'):

    # create accumulator variables
    correct_count = create_metric_variable("correct_count", shape=[], dtype=tf.int64)
    excess_count = create_metric_variable("excess_count", shape=[], dtype=tf.int64)
    missed_count = create_metric_variable("missed_count", shape=[], dtype=tf.int64)

    # first, use reverse maps to convert ints to strings
    str_predictions = nn_utils.int_to_str_lookup_table(predictions, reverse_maps['srl'])
    str_words = nn_utils.int_to_str_lookup_table(words, reverse_maps['word'])
    str_srl_targets = nn_utils.int_to_str_lookup_table(targets, reverse_maps['srl'])
    str_parse_label_targets = nn_utils.int_to_str_lookup_table(parse_label_targets, reverse_maps['parse_label'])
    str_parse_label_predictions = nn_utils.int_to_str_lookup_table(parse_label_predictions, reverse_maps['parse_label'])
    str_pos_predictions = nn_utils.int_to_str_lookup_table(pos_predictions, reverse_maps['gold_pos'])
    str_pos_targets = nn_utils.int_to_str_lookup_table(pos_targets, reverse_maps['gold_pos'])
    str_predicate_predictions = nn_utils.int_to_str_lookup_table(predicate_predictions, reverse_maps['predicate'])
    str_predicate_targets = nn_utils.int_to_str_lookup_table(predicate_targets, reverse_maps['predicate'])

    # need to pass through the stuff for pyfunc
    # pyfunc is necessary here since we need to write to disk
    py_eval_inputs = [str_predictions, str_predicate_predictions, str_words, mask, str_srl_targets, str_predicate_targets,
                      str_parse_label_predictions, parse_head_predictions, str_parse_label_targets, parse_head_targets,
                      str_pos_targets, str_pos_predictions, pred_srl_eval_file, gold_srl_eval_file, pred_sense, gold_sense]
    out_types = [tf.int64, tf.int64, tf.int64]
    correct, excess, missed = tf.py_func(evaluation_fns_np.conll09_srl_eval_srl_only, py_eval_inputs, out_types, stateful=False)

    update_correct_op = tf.assign_add(correct_count, correct)
    update_excess_op = tf.assign_add(excess_count, excess)
    update_missed_op = tf.assign_add(missed_count, missed)

    precision_update_op = update_correct_op / (update_correct_op + update_excess_op)
    recall_update_op = update_correct_op / (update_correct_op + update_missed_op)
    f1_update_op = 2 * precision_update_op * recall_update_op / (precision_update_op + recall_update_op)

    precision = correct_count / (correct_count + excess_count)
    recall = correct_count / (correct_count + missed_count)
    f1 = 2 * precision * recall / (precision + recall)

    return f1, f1_update_op

def conll09_srl_eval_all_tf(predictions, targets, predicate_predictions, words, mask, predicate_targets, reverse_maps,
                      gold_srl_eval_file, pred_srl_eval_file, pos_predictions, pos_targets, parse_head_targets,
                        parse_head_predictions, parse_label_targets, parse_label_predictions, pred_sense, gold_sense):

  with tf.name_scope('conll_srl_eval'):

    # create accumulator variables
    with tf.variable_scope('conll_srl_eval_all_vars'):
      correct_count = create_metric_variable("correct_count", shape=[], dtype=tf.int64)
      excess_count = create_metric_variable("excess_count", shape=[], dtype=tf.int64)
      missed_count = create_metric_variable("missed_count", shape=[], dtype=tf.int64)

    # first, use reverse maps to convert ints to strings
    str_predictions = nn_utils.int_to_str_lookup_table(predictions, reverse_maps['srl'])
    str_words = nn_utils.int_to_str_lookup_table(words, reverse_maps['word'])
    str_srl_targets = nn_utils.int_to_str_lookup_table(targets, reverse_maps['srl'])
    str_parse_label_targets = nn_utils.int_to_str_lookup_table(parse_label_targets, reverse_maps['parse_label'])
    str_parse_label_predictions = nn_utils.int_to_str_lookup_table(parse_label_predictions, reverse_maps['parse_label'])
    str_pos_predictions = nn_utils.int_to_str_lookup_table(pos_predictions, reverse_maps['gold_pos'])
    str_pos_targets = nn_utils.int_to_str_lookup_table(pos_targets, reverse_maps['gold_pos'])
    str_predicate_predictions = nn_utils.int_to_str_lookup_table(predicate_predictions, reverse_maps['predicate'])
    str_predicate_targets = nn_utils.int_to_str_lookup_table(predicate_targets, reverse_maps['predicate'])

    # need to pass through the stuff for pyfunc
    # pyfunc is necessary here since we need to write to disk
    py_eval_inputs = [str_predictions, str_predicate_predictions, str_words, mask, str_srl_targets, str_predicate_targets,
                      str_parse_label_predictions, parse_head_predictions, str_parse_label_targets, parse_head_targets,
                      str_pos_targets, str_pos_predictions, pred_srl_eval_file, gold_srl_eval_file, pred_sense, gold_sense]
    out_types = [tf.int64, tf.int64, tf.int64]
    correct, excess, missed = tf.py_func(evaluation_fns_np.conll09_srl_eval, py_eval_inputs, out_types, stateful=False)

    update_correct_op = tf.assign_add(correct_count, correct)
    update_excess_op = tf.assign_add(excess_count, excess)
    update_missed_op = tf.assign_add(missed_count, missed)

    precision_update_op = update_correct_op / (update_correct_op + update_excess_op)
    recall_update_op = update_correct_op / (update_correct_op + update_missed_op)
    f1_update_op = 2 * precision_update_op * recall_update_op / (precision_update_op + recall_update_op)

    precision = correct_count / (correct_count + excess_count)
    recall = correct_count / (correct_count + missed_count)
    f1 = 2 * precision * recall / (precision + recall)

    return [precision, recall, f1], f1_update_op
def conll09_srl_eval_all_srl_only_tf(predictions, targets, predicate_predictions, words, mask, predicate_targets, reverse_maps,
                      gold_srl_eval_file, pred_srl_eval_file, pos_predictions, pos_targets, parse_head_targets,
                        parse_head_predictions, parse_label_targets, parse_label_predictions, pred_sense, gold_sense):

  with tf.name_scope('conll_srl_eval'):

    # create accumulator variables
    correct_count = create_metric_variable("correct_count", shape=[], dtype=tf.int64)
    excess_count = create_metric_variable("excess_count", shape=[], dtype=tf.int64)
    missed_count = create_metric_variable("missed_count", shape=[], dtype=tf.int64)

    # first, use reverse maps to convert ints to strings
    str_predictions = nn_utils.int_to_str_lookup_table(predictions, reverse_maps['srl'])
    str_words = nn_utils.int_to_str_lookup_table(words, reverse_maps['word'])
    str_srl_targets = nn_utils.int_to_str_lookup_table(targets, reverse_maps['srl'])
    str_parse_label_targets = nn_utils.int_to_str_lookup_table(parse_label_targets, reverse_maps['parse_label'])
    str_parse_label_predictions = nn_utils.int_to_str_lookup_table(parse_label_predictions, reverse_maps['parse_label'])
    str_pos_predictions = nn_utils.int_to_str_lookup_table(pos_predictions, reverse_maps['gold_pos'])
    str_pos_targets = nn_utils.int_to_str_lookup_table(pos_targets, reverse_maps['gold_pos'])
    str_predicate_predictions = nn_utils.int_to_str_lookup_table(predicate_predictions, reverse_maps['predicate'])
    str_predicate_targets = nn_utils.int_to_str_lookup_table(predicate_targets, reverse_maps['predicate'])

    # need to pass through the stuff for pyfunc
    # pyfunc is necessary here since we need to write to disk
    py_eval_inputs = [str_predictions, str_predicate_predictions, str_words, mask, str_srl_targets, str_predicate_targets,
                      str_parse_label_predictions, parse_head_predictions, str_parse_label_targets, parse_head_targets,
                      str_pos_targets, str_pos_predictions, pred_srl_eval_file, gold_srl_eval_file, pred_sense, gold_sense]
    out_types = [tf.int64, tf.int64, tf.int64]
    correct, excess, missed = tf.py_func(evaluation_fns_np.conll09_srl_eval_srl_only, py_eval_inputs, out_types, stateful=False)

    update_correct_op = tf.assign_add(correct_count, correct)
    update_excess_op = tf.assign_add(excess_count, excess)
    update_missed_op = tf.assign_add(missed_count, missed)

    precision_update_op = update_correct_op / (update_correct_op + update_excess_op)
    recall_update_op = update_correct_op / (update_correct_op + update_missed_op)
    f1_update_op = 2 * precision_update_op * recall_update_op / (precision_update_op + recall_update_op)

    precision = correct_count / (correct_count + excess_count)
    recall = correct_count / (correct_count + missed_count)
    f1 = 2 * precision * recall / (precision + recall)

    return [precision, recall, f1], f1_update_op

# todo share computation with srl eval
def conll_parse_eval_tf(predictions, targets, parse_head_predictions, words, mask, parse_head_targets, reverse_maps,
                   gold_parse_eval_file, pred_parse_eval_file, pos_targets, has_root_token = False):

  with tf.name_scope('conll_parse_eval'):

    # create accumulator variables
    with tf.variable_scope('conll_parse_eval'):
      total_count = create_metric_variable("total_count", shape=[], dtype=tf.int64)
      correct_count = create_metric_variable("correct_count", shape=[3], dtype=tf.int64)

    str_words = nn_utils.int_to_str_lookup_table(words, reverse_maps['word'])
    str_predictions = nn_utils.int_to_str_lookup_table(predictions, reverse_maps['parse_label'])
    # targets = targets * tf.cast(mask, tf.int32)
    # targets = tf.Print(targets, [targets], "targets:", summarize=60)
    # mask = tf.Print(mask, [mask], "mask:", summarize=60)
    str_targets = nn_utils.int_to_str_lookup_table(targets, reverse_maps['parse_label'])
    str_pos_targets = nn_utils.int_to_str_lookup_table(pos_targets, reverse_maps['gold_pos'])


    # str_words = tf.Print(str_words, [str_words])
    # tf.cond(tf.equal(str_words[0, 0] , 'ROOT'), )
    if has_root_token:
      str_words_final = str_words[:, 1:]
      str_predictions_final = str_predictions[:, 1:]
      str_targets_final = str_targets[:, 1:]
      str_pos_targets_final = str_pos_targets[:, 1:]
    else:
      str_words_final = str_words
      str_predictions_final = str_predictions
      str_targets_final = str_targets
      str_pos_targets_final = str_pos_targets

    # str_words_final = tf.Print(str_words_final, [str_words_final])
    # need to pass through the stuff for pyfunc
    # pyfunc is necessary here since we need to write to disk
    py_eval_inputs = [str_predictions_final, parse_head_predictions, str_words_final, mask, str_targets_final, parse_head_targets,
                      pred_parse_eval_file, gold_parse_eval_file, str_pos_targets_final]
    out_types = [tf.int64, tf.int64]
    total, corrects = tf.py_func(evaluation_fns_np.conll_parse_eval, py_eval_inputs, out_types, stateful=False)

    update_total_count_op = tf.assign_add(total_count, total)
    update_correct_op = tf.assign_add(correct_count, corrects)

    update_op = update_correct_op / update_total_count_op

    accuracies = correct_count / total_count

    return accuracies, update_op


dispatcher = {
  'accuracy': accuracy_tf,
  'precision': precision_tf,
  'recall': recall_tf,
  'fscore': f1_tf,
  'conll_srl_eval': conll_srl_eval_tf,
  'conll_srl_all_eval': conll_srl_eval_all_tf,
  'conll_parse_eval': conll_parse_eval_tf,
  'conll09_srl_eval': conll09_srl_eval_tf,
  'conll09_srl_eval_srl_only': conll09_srl_eval_srl_only_tf,

  'conll09_srl_eval_all': conll09_srl_eval_all_tf,
  'conll09_srl_eval_all_srl_only': conll09_srl_eval_all_srl_only_tf,
}


def dispatch(fn_name):
  try:
    return dispatcher[fn_name]
  except KeyError:
    print('Undefined evaluation function `%s' % fn_name)
    exit(1)


def get_params(task_outputs, task_map, train_outputs, features, labels, task_labels, reverse_maps, tokens_to_keep):

  # always pass through predictions, targets and mask
  params = {'predictions': task_outputs['predictions'], 'targets': task_labels, 'mask': tokens_to_keep}
  if 'params' in task_map:
    params_map = task_map['params']
    for param_name, param_values in params_map.items():
      if 'reverse_maps' in param_values:
        params[param_name] = {map_name: reverse_maps[map_name] for map_name in param_values['reverse_maps']}
      elif 'label' in param_values:
        params[param_name] = labels[param_values['label']]
      elif 'feature' in param_values:
        params[param_name] = features[param_values['feature']]
      elif 'layer' in param_values:
        outputs_layer = train_outputs[param_values['layer']]
        params[param_name] = outputs_layer[param_values['output']]
      else:
        params[param_name] = param_values['value']
  return params
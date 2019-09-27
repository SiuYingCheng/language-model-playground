# built-in modules
import os

# 3rd-party modules
import numpy as np
import pandas as pd
import torch
import torch.nn
import torch.utils.data
import torch.nn.utils.rnn
import torch.optim
import sklearn.metrics
from tqdm import tqdm

##############################################
# build model
##############################################

class BaseModel(torch.nn.Module):
    def __init__(self, config, tokenizer):
        super(BaseModel, self).__init__()

        # Embedding layer
        self.embedding_layer = torch.nn.Embedding(num_embeddings=tokenizer.vocab_size(),
                                                  embedding_dim=config.embedding_dim,
                                                  padding_idx=tokenizer.pad_token_id)

        # RNN layer
        self.rnn_layer = torch.nn.RNN(input_size=config.embedding_dim,
                                      hidden_size=config.hidden_dim,
                                      num_layers=config.num_rnn_layers,
                                      dropout=config.dropout,
                                      batch_first=True)

        # Linear layer
        self.linear = []

        for _ in range(config.num_linear_layers):
            self.linear.append(torch.nn.Linear(config.hidden_dim, config.hidden_dim))
            self.linear.append(torch.nn.ReLU())
            self.linear.append(torch.nn.Dropout(config.dropout))

        self.linear.append(torch.nn.Linear(config.hidden_dim, config.embedding_dim))
        self.sequential = torch.nn.Sequential(*self.linear)

    def forward(self, batch_x):
        ######################################################################
        # 維度: (batch_Size, sequence_length)
        #
        # 維度: (batch_size, sequence_length, embedding_dimension)
        ######################################################################
        batch_x = self.embedding_layer(batch_x)

        ######################################################################
        # 維度: (batch_size, sequence_length, hidden_dimension)
        ######################################################################
        ht, _ = self.rnn_layer(batch_x)

        ######################################################################
        # 維度: (batch_size, sequence_length, vocabulary_size)
        ######################################################################
        ht = self.sequential(ht)
        yt = ht.matmul(self.embedding_layer.weight.transpose(0, 1))
        return yt

    def generator(self,
                  tokenizer=None,
                  begin_of_sentence='',
                  beam_width=4,
                  max_len=200):
        if begin_of_sentence is None or len(begin_of_sentence) == 0:
            raise ValueError('`begin_of_sentence` should be list type object.')

        generate_result = []

        with torch.no_grad():
            all_ids = tokenizer.convert_sentences_to_ids([begin_of_sentence])
            all_ids_prob = [0]

            while True:
                active_ids = []
                active_ids_prob = []

                # 決定當前還有哪些句子需要進行生成
                for i in range(len(all_ids)):
                    if all_ids[i][-1] != tokenizer.eos_token_id and len(all_ids[i]) < max_len:
                        active_ids.append(all_ids[i])
                        active_ids_prob.append(all_ids_prob[i])
                    elif len(generate_result) < beam_width:
                        generate_result.append(all_ids[i])

                # 如果沒有需要生成的句子就結束迴圈
                if not active_ids or len(generate_result) >= beam_width:
                    break

                batch_x = [torch.LongTensor(ids) for ids in active_ids]
                batch_x = torch.nn.utils.rnn.pad_sequence(batch_x,
                                                          batch_first=True,
                                                          padding_value=tokenizer.pad_token_id)

                batch_pred_y = self(batch_x)

                # 從各個句子中的 beam 挑出前 beam_width 個最大值
                top_value = {}
                for beam_id in range(len(active_ids)):
                    current_beam_vocab_pred = batch_pred_y[beam_id][len(active_ids[beam_id]) - 1]
                    current_beam_vocab_pred = torch.nn.functional.softmax(current_beam_vocab_pred, dim=0)

                    current_beam_top_value = [{
                        'vocab_id': tokenizer.eos_token_id,
                        'value': 0
                    } for i in range(beam_width)]

                    for vocab_id in range(tokenizer.vocab_size()):
                        if current_beam_vocab_pred[vocab_id] < current_beam_top_value[0]['value']:
                            continue

                        for level in range(beam_width):
                            if current_beam_vocab_pred[vocab_id] < current_beam_top_value[level]['value']:
                                level -= 1
                                break

                        for tmp in range(level):
                            current_beam_top_value[tmp] = current_beam_top_value[tmp + 1]

                        current_beam_top_value[level] = {'vocab_id': vocab_id,
                                                         'value': current_beam_vocab_pred[vocab_id]}

                    top_value[beam_id] = current_beam_top_value

                # 從 beam_width ** 2 中挑出 beam_width 個最大值
                final_top_value = []

                for i in range(beam_width):
                    max_value_beam_id = 0
                    max_value_vocab_id = tokenizer.eos_token_id
                    min_value = 999999999

                    for beam_id in range(len(top_value)):
                        value = -torch.log(top_value[beam_id][-1]['value']) + active_ids_prob[beam_id]
                        if value < min_value:
                            max_value_beam_id = beam_id
                            min_value = value
                            max_value_vocab_id = top_value[beam_id][-1]['vocab_id']

                    final_top_value.append({
                        'beam_id': max_value_beam_id,
                        'vocab_id': max_value_vocab_id,
                        'value': min_value
                    })

                    top_value[max_value_beam_id].pop()

                # back to all_ids
                all_ids = []
                all_ids_prob = []
                for obj in final_top_value:
                    all_ids.append(active_ids[obj['beam_id']] + [obj['vocab_id']])
                    all_ids_prob.append(obj['value'])

        for ids in generate_result:
            if ids[-1] == tokenizer.eos_token_id:
                ids.pop()
        return tokenizer.convert_ids_to_sentences(generate_result)

class LSTMModel(BaseModel):
    def __init__(self, config, tokenizer):
        super(LSTMModel, self).__init__(config, tokenizer)

        # overload RNN layer
        self.rnn_layer = torch.nn.LSTM(input_size=config.embedding_dim,
                                       hidden_size=config.hidden_dim,
                                       num_layers=config.num_rnn_layers,
                                       dropout=config.dropout,
                                       batch_first=True)

class GRUModel(BaseModel):
    def __init__(self, config, tokenizer):
        super(GRUModel, self).__init__(config, tokenizer)

        # overload RNN layer
        self.rnn_layer = torch.nn.GRU(input_size=config.embedding_dim,
                                      hidden_size=config.hidden_dim,
                                      num_layers=config.num_rnn_layers,
                                      dropout=config.dropout,
                                      batch_first=True)

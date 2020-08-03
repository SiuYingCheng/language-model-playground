r"""Language model with residual RNN blocks.

Usage:
    from torch.utils.data import DataLoader
    import lmp

    model = lmp.model.BaseResidualRNNModel(...)
    tokenizer = lmp.tokenizer.CharDictTokenizer(...)
    dataset = lmp.dataset.BaseDataset(...)
    dataloader = DataLoader(
        dataset=dataset,
        collate_fn=dataset.create_collate_fn(tokenizer)
    )
    for x, y in dataloader:
        pred = model(x)
"""

# built-in modules

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

# 3rd-party modules

import torch
import torch.nn

import lmp.model


class BaseResidualRNNModel(torch.nn.Module):
    r"""Language model with residual RNN blocks.

    Each input token will first be embedded into vectors, then sequentially
    feed into residual RNN blocks. Output vectors of blocks then go through
    fully-connected layer and project back to embedding dimension in order to
    perform vocabulary prediction.

    In the comment below, we use following symbols to denote the size of
    each tensors:
        B: batch size
        S: sequence length
        E: embedding dimension
        V: vocabulary size
        H: hidden dimension

    Args:
        d_emb:
            Embedding matrix vector dimension.
        d_hid:
            RNN layers hidden dimension.
        dropout:
            Dropout probability on all layers out (except output layer).
        num_rnn_layers:
            Number of RNN layers to use.
        num_linear_layers:
            Number of Linear layers to use.
        pad_token_id:
            Padding token's id. Embedding layers will initialize padding
            token's vector with zeros.
        vocab_size:
            Embedding matrix vocabulary dimension.
    """

    def __init__(
            self,
            d_emb: int,
            d_hid: int,
            dropout: float,
            num_rnn_layers: int,
            num_linear_layers: int,
            pad_token_id: int,
            vocab_size: int
    ):
        super().__init__()

        # Embedding layer
        # Dimension: (V, E)
        self.embedding_layer = torch.nn.Embedding(
            num_embeddings=vocab_size,
            embedding_dim=d_emb,
            padding_idx=pad_token_id
        )

        self.linear_layer_tran = torch.nn.Linear(
            in_features=d_emb,
            out_features=d_hid
        )

        # Sequential RNN blocks
        # Dimension: (E, E)
        rnn_blocks = []
        for _ in range(num_rnn_layers):
            rnn_blocks.append(
                lmp.model.BaseResRNNBlock(
                    d_in=d_hid,
                    d_out=d_hid,
                    dropout=dropout
                )
            )

        self.rnn_blocks = torch.nn.Sequential(*rnn_blocks)

        # Sequential linear layer
        # Dimension: (H, E)
        linear_layers = []
        for _ in range(num_linear_layers):
            linear_layers.append(
                torch.nn.Linear(
                    in_features=d_hid,
                    out_features=d_hid
                )
            )
            linear_layers.append(
                torch.nn.ReLU()
            )
            linear_layers.append(
                torch.nn.Dropout(dropout)
            )

        linear_layers.append(
            torch.nn.Linear(
                in_features=d_hid,
                out_features=d_emb
            )
        )

        self.linear_layers = torch.nn.Sequential(*linear_layers)

    def forward(
            self,
            batch_sequences: torch.Tensor
    ) -> torch.Tensor:
        r"""Perform forward pass.

        Args:
            batch_sequences:
                Batch of sequences which have been encoded by
                `lmp.tokenizer.BaseTokenizer` with numeric type `torch.int64`.

        Returns:
            Logits for each token in sequences with numeric type `torch.float32`.
        """
        # 將 batch_sequences 中的所有 token_id 經過 embedding matrix
        # 轉換成 embedding vectors (共有 (B, S) 個維度為 E 的向量)
        # embedding 前的 batch_sequences 維度: (B, S)
        # embedding 後的 batch_sequences 維度: (B, S, E)
        batch_sequences = self.embedding_layer(batch_sequences)

        # 將每個 embedding vectors 經由 linear 轉換 得到輸出 hidden vectors
        # ht 維度: (B, S, H)
        ht = self.linear_layer_tran(batch_sequences)

        # 將每個 embedding vectors 依序經由 RNN 輸入 得到輸出 hidden vectors
        # ht 維度: (B, S, H)
        ht = self.rnn_blocks(ht)

        # 將每個 hidden vectors 轉換維度至 embedding dimension
        # ht 維度: (B, S, E)
        ht = self.linear_layers(ht)

        # 與轉置後的 embedding matrix 進行矩陣乘法取得預測文字
        # 重複使用 embedding matrix 的目的為節省參數數量
        # yt 維度: (B, S, V)
        yt = ht.matmul(self.embedding_layer.weight.transpose(0, 1))

        return yt

    def predict(
            self,
            batch_sequences: torch.Tensor
    ) -> torch.Tensor:
        r"""Convert model output logits into prediction.

        Args:
            batch_sequences:
                Batch of sequences which have been encoded by
                `lmp.tokenizer.BaseTokenizer` with numeric type `torch.int64`.

        Returns:
            Predicition using softmax on model output logits with numeric type `torch.float32`.
        """
        return torch.nn.functional.softmax(self(batch_sequences), dim=-1)

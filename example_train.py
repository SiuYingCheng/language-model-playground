r"""Train the text-generation model.
Usage:
    python example_train.py --experiment_no 1 --is_uncased True

--experiment_no is a required argument.
Run 'python example_train.py --help' for help
"""

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
import argparse
import torch.utils.tensorboard

# self-made modules
import lmp


def train_model(args):
    experiment_no = args.experiment_no

    data_path = os.path.abspath('./data')
    # set saved path
    save_path = f'{data_path}/{experiment_no}'
    if not os.path.exists(save_path):
        os.mkdir(save_path)

    config_save_path = f'{save_path}/config.pickle'
    tokenizer_save_path = f'{save_path}/tokenizer.pickle'
    model_save_path = f'{save_path}/model.ckpt'

    keep_training = True if args.checkpoint_num > 0 else False

    ##############################################
    # Load data.
    ##############################################
    df = pd.read_csv(f'{data_path}/news_collection.csv')

    ##############################################
    # Hyperparameters setup
    ##############################################
    if keep_training == True:
        config = lmp.config.BaseConfig.load_from_file(f'{save_path}/config.pickle')
    else:
        config = lmp.config.BaseConfig(batch_size=args.batch_size,
                                    checkpoint_size=args.checkpoint_size,
                                    dropout=args.dropout,
                                    embedding_dim=args.embedding_dim,
                                    epoch=args.epoch,
                                    hidden_dim=args.hidden_dim,
                                    is_uncased=args.is_uncased,
                                    learning_rate=args.learning_rate,
                                    max_norm=args.max_norm,
                                    min_count=args.min_count,
                                    model_type=args.model_type,
                                    num_rnn_layers=args.num_rnn_layers,
                                    num_linear_layers=args.num_linear_layers,
                                    seed=args.seed,
                                    tokenizer_type=args.tokenizer_type
                                    )


    ##############################################
    # Initialize random seed.
    ##############################################
    device = torch.device('cpu')
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)

    if torch.cuda.is_available():
        device = torch.device('cuda:0')
        torch.cuda.manual_seed(config.seed)
        torch.cuda.manual_seed_all(config.seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    ##############################################
    # Construct tokenizer and perform tokenization.
    ##############################################
    if keep_training:
        tokenizer = lmp.util.load_tokenizer(save_path , config.tokenizer_type)
    else:
        tokenizer = lmp.util.load_blank_tokenizer(config.tokenizer_type)
        tokenizer.build_dict(df['title'], config.min_count, config.is_uncased)

    dataset = lmp.dataset.BaseDataset(text_list=df['title'])

    collate_fn = lmp.dataset.BaseDataset.creat_collate_fn(tokenizer=tokenizer,
                                                            max_seq_len=args.max_seq_len)
    data_loader = torch.utils.data.DataLoader(dataset,
                                              batch_size=config.batch_size,
                                              shuffle=True,
                                              collate_fn=collate_fn)

    ##############################################
    # Construct RNN model, choose loss function and optimizer.
    ##############################################
    model = lmp.util.load_blank_model(config, tokenizer, config.model_type)
    model = model.to(device)

    criterion = torch.nn.CrossEntropyLoss()

    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)

    start_step, start_epoch = 0, 0
    if keep_training:
        state_path = f'{save_path}/checkpoint{args.checkpoint_num}.pth'
        checkpoint_state = torch.load(state_path)

        model.load_state_dict(checkpoint_state['model'])

        optimizer.load_state_dict(checkpoint_state['optimizer'])

        start_epoch = checkpoint_state['epoch'] + 1
        start_step = checkpoint_state['step'] + 1


    ##############################################
    # train
    ##############################################
    if keep_training==False:
        config.save_to_file(config_save_path)
        tokenizer.save_to_file(tokenizer_save_path)


    model.train()

    best_loss = None
    step = start_step

    writer = torch.utils.tensorboard.SummaryWriter( f'{save_path}/text-generation-log')

    for epoch in range(start_epoch , config.epoch):

        print(f'epoch {epoch}')
        total_loss = 0

        mini_batch_iterator = tqdm(data_loader)

        for x, y in mini_batch_iterator:
            x = x.to(device)
            y = y.view(-1).to(device)  # shape: (batch_size * sequence_length)

            optimizer.zero_grad()

            pred_y = model(x)
            # shape: (batch_size * sequence_length, vocabulary_size)
            pred_y = pred_y.view(-1, tokenizer.vocab_size())
            loss = criterion(pred_y, y)
            total_loss += loss.item() / len(dataset)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_norm)

            optimizer.step()
            step += 1
            if step % config.checkpoint_size == 0:
                # torch.save(model.state_dict(),
                #            f'{save_path}/model{step/config.checkpoint_size}.ckpt')
                state_para = {'model':model.state_dict(), 'optimizer':optimizer.state_dict(), 'epoch':epoch, 'step':step}
                torch.save(state_para, f'{save_path}/checkpoint{int(step/config.checkpoint_size)}.pth')

            writer.add_scalar('text-generation/dataset/Loss',
                loss.item(),
                step
                )

            mini_batch_iterator.set_description(
                f'epoch: {epoch}, loss: {total_loss:.6f} training:'
            )


        if (best_loss is None) or (total_loss < best_loss):
            torch.save(model.state_dict(), model_save_path)
            best_loss = total_loss

    print(f'experiment {experiment_no}')
    print(f'best loss: {best_loss:.10f}')


def keep_training(args):
    experiment_no = args.experiment_no
    data_path = os.path.abspath('./data')
    model_path = f'{data_path}/{experiment_no}'

    config = lmp.config.BaseConfig.load_from_file(
        f'{model_path}/config.pickle')

    ##############################################
    # Initialize random seed.
    ##############################################
    device = torch.device('cpu')
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)

    if torch.cuda.is_available():
        device = torch.device('cuda:0')
        torch.cuda.manual_seed(config.seed)
        torch.cuda.manual_seed_all(config.seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    ##############################################
    # Load data.
    ##############################################
    data_path = os.path.abspath('./data')

    df = pd.read_csv(f'{data_path}/news_collection.csv')

    ##############################################
    # Construct tokenizer and perform tokenization.
    ##############################################
    tokenizer = lmp.util.load_tokenizer(model_path , config.tokenizer_type)



    dataset = lmp.dataset.BaseDataset(config=config,
                                    text_list=df['title'])


    collate_fn = lmp.dataset.BaseDataset.creat_collate_fn(tokenizer=tokenizer,
                                                            max_seq_len=args.max_seq_len)
    data_loader = torch.utils.data.DataLoader(dataset,
                                              batch_size=config.batch_size,
                                              shuffle=True,
                                              collate_fn=collate_fn)


    ##############################################
    # Construct RNN model, choose loss function and optimizer.
    ##############################################

    state_path = f'{model_path}/checkpoint{args.checkpoint_num}.pth'
    checkpoint_state = torch.load(state_path)

    model = lmp.util.load_blank_model(config, tokenizer, config.model_type)
    model.load_state_dict(checkpoint_state['model'])
    model = model.to(device)

    criterion = torch.nn.CrossEntropyLoss()

    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    optimizer.load_state_dict(checkpoint_state['optimizer'])

    start_epoch = checkpoint_state['epoch'] + 1
    start_step = checkpoint_state['step'] + 1


    save_path = f'{data_path}/{experiment_no}'
    if not os.path.exists(save_path):
        os.mkdir(save_path)

    model_save_path = f'{save_path}/model.ckpt'

    model.train()

    best_loss = None


    step = start_step

    experiment_name = 'text-generation-log'

    writer = torch.utils.tensorboard.SummaryWriter( f'{model_path}/{experiment_name}')

    for epoch in range(config.epoch):
        epoch = start_epoch

        print(f'epoch {epoch}')
        total_loss = 0

        mini_batch_iterator = tqdm(data_loader)

        for x, y in mini_batch_iterator:
            x = x.to(device)
            y = y.view(-1).to(device)  # shape: (batch_size * sequence_length)

            optimizer.zero_grad()

            pred_y = model(x)
            # shape: (batch_size * sequence_length, vocabulary_size)
            pred_y = pred_y.view(-1, tokenizer.vocab_size())
            loss = criterion(pred_y, y)
            total_loss += loss.item() / len(dataset)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_norm)

            optimizer.step()
            step += 1
            if step % config.checkpoint_size == 0:
                # torch.save(model.state_dict(),
                #            f'{save_path}/model{step/config.checkpoint_size}.ckpt')
                state_para = {'model':model.state_dict(), 'optimizer':optimizer.state_dict(), 'epoch':epoch, 'step':step}
                torch.save(state_para, f'{save_path}/checkpoint{int(step/config.checkpoint_size)}.pth')


            mini_batch_iterator.set_description(
                f'epoch: {epoch}, loss: {total_loss:.6f} training:'
            )
            writer.add_scalar('text-generation/dataset/Loss',
                            total_loss,
                            step
                            )

        if (best_loss is None) or (total_loss < best_loss):
            torch.save(model.state_dict(), model_save_path)
            best_loss = total_loss

    print(f'experiment {experiment_no}')
    print(f'best loss: {best_loss:.10f}')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    # Required arguments.
    parser.add_argument("--experiment_no", type=int, default=1,
                        required=True, help="using which experiment_no data")

    # Optional arguments.
    parser.add_argument("--batch_size",         type=int,
                        default=32,     help="Training batch size.")
    parser.add_argument("--checkpoint_num",     type=int,
                        default=-1, help="Decide use which checkpoint model to keep training")
    parser.add_argument("--checkpoint_size",         type=int,
                        default=500,    help="save model state each checkpoint size")
    parser.add_argument("--dropout",            type=float,
                        default=0,      help="Dropout rate.")
    parser.add_argument("--embedding_dim",      type=int,
                        default=100,    help="Embedding dimension.")
    parser.add_argument("--epoch",              type=int,
                        default=10,     help="Number of training epochs.")
    parser.add_argument("--hidden_dim",         type=int,
                        default=300,    help="Hidden dimension.")
    parser.add_argument("--is_uncased",         action="store_true",
                        help="convert all upper case into lower case.")
    parser.add_argument("--learning_rate",      type=float,
                        default=5e-5,   help="Optimizer's parameter `lr`.")
    parser.add_argument("--max_norm",           type=float, default=1,
                        help="Max norm of gradient.Used when cliping gradient norm.")
    parser.add_argument("--max_seq_len",        type=int, default=-1,
                        help="Indicate max sequence length for each data.")
    parser.add_argument("--min_count",          type=int,
                        default=0,      help="Minimum of token'sfrequence.")
    parser.add_argument("--model_type",         type=str,
                        default='lstm', help="Decide use which model, GRU or LSTM")
    parser.add_argument("--num_rnn_layers",     type=int,
                        default=1,      help="Number of rnn layers.")
    parser.add_argument("--num_linear_layers",  type=int,
                        default=2,      help="Number of Linear layers.")
    parser.add_argument("--seed",               type=int,
                        default=7,      help="Control random seed.")
    parser.add_argument("--tokenizer_type",     type=str,
                        default='list', help="Decide use which tokenizer, List or Dict")


    args = parser.parse_args()


    train_model(args)


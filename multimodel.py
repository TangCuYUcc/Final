from keras.preprocessing import text

import jieba as jb
import re
import pandas as pd
from keras.models import load_model
from keras.preprocessing.sequence import pad_sequences



def text_predict(s):
    # 定义删除除字母,数字，汉字以外的所有符号的函数
    def remove_punctuation(line):
        line = str(line)
        if line.strip() == '':
            return ''
        rule = re.compile(u"[^a-zA-Z0-9\u4E00-\u9FA5]")
        line = rule.sub('', line)
        return line

    def stopwordslist(filepath):
        stopwords = [line.strip() for line in open(filepath, 'r', encoding='utf-8').readlines()]
        return stopwords

    def preprocess_text_data(df, max_nb_words=50000, max_sequence_length=80):
        """
        对文本数据进行预处理，并返回处理后的文本数据和词汇表

        Args:
        df: DataFrame，包含文本数据的数据集
        max_nb_words: int，最大词汇表大小，默认为50000
        max_sequence_length: int，每个文本序列的最大长度，默认为80

        Returns:
        padded_sequences: list，经过处理后的文本数据的整数序列列表
        word_index: dict，词汇表，将单词映射到整数索引的字典
        """
        # 创建 Tokenizer 对象
        tokenizer = text.Tokenizer(num_words=max_nb_words, lower=True)
        # 根据文本数据拟合 Tokenizer 对象
        tokenizer.fit_on_texts(df['Text'].values)
        # 获取词汇表
        word_index = tokenizer.word_index
        # 将文本数据转换为整数序列
        sequences = tokenizer.texts_to_sequences(df['Text'].values)
        # 对整数序列进行填充或截断，使其长度相同
        padded_sequences = pad_sequences(sequences, maxlen=max_sequence_length)

        return padded_sequences, word_index, tokenizer

    # 加载停用词
    stopwords = stopwordslist("ChineseStopWords.txt")
    df = pd.read_csv('train1.csv', encoding='utf-8')

    df[df.isnull().values == True]
    df = df[pd.notnull(df['label'])]

    d = {'label': df['label'].value_counts().index, 'count': df['label'].value_counts()}
    df_label = pd.DataFrame(data=d).reset_index(drop=True)

    df['label_id'] = df['label'].factorize()[0]
    label_id_df = df[['label', 'label_id']].drop_duplicates().sort_values('label_id').reset_index(drop=True)
    label_to_id = dict(label_id_df.values)
    id_to_label = dict(label_id_df[['label_id', 'label']].values)
    model = load_model('LSTM.h5')

    def predict(s):
        txt = remove_punctuation(s)
        txt = [" ".join([w for w in list(jb.cut(txt)) if w not in stopwords])]
        padded, word_index, tokenizer = preprocess_text_data(df)
        seq = tokenizer.texts_to_sequences(txt)
        padded = pad_sequences(seq, maxlen=80)
        pred = model.predict(padded)
        label_id = pred.argmax(axis=1)[0]
        print(label_id_df[label_id_df.label_id == label_id]['label'].values[0], pred, 5)
        return pred[0]


if __name__ == '__main__':
    # audio_path = r"D:\Desktop\2.wav"
    s = '我太喜欢吃麦当劳了'
    # img_paths = [r"D:\Desktop\3.jpg"]
    # print(multimodel(audio_path, text, img_paths))
    text_predict(s)



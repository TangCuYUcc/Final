# -*- coding: utf-8 -*-
import keras.preprocessing.text
from keras.preprocessing.image import img_to_array
import imutils
import cv2
import numpy as np
import jieba as jb
import re
import pandas as pd
from keras.models import load_model
from keras.preprocessing.sequence import pad_sequences
from extract_feats import opensmile as of
from extract_feats import librosa as lf
import models
import utils
from flask import Flask, request, send_file
import SparkApi
import time
import websocket
import datetime
import hashlib
import base64
import hmac
import json
from urllib.parse import urlencode
import ssl
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import _thread as thread
import os
import ffmpeg
import threading

app = Flask(__name__)

@app.route('/gettest', methods=['Post'])
def get():
    imagefold = "image"
    file = request.files['photo']
    imagepath = os.path.join(imagefold,file.filename)
    file.save(imagepath)
    return "didu"



# 路由定义
@app.route('/getlabel', methods=['GET'])
def get_label():
    try:
        with open('label.txt', 'r', encoding='utf-8') as f:
            label = f.read()
        return label, 200
    except FileNotFoundError:
        return "Label file not found"
    except Exception as e:
        return "Error reading label file: {}".format(str(e))

@app.route('/postaudio', methods = ['POST'])
def total():
    # 写入数据
    def write_json(s):
        with open('history.json', "r", encoding='utf-8') as f1:
            loaded_data = json.load(f1)
        loaded_data.append(s)
        with open("history.json", "w", encoding='utf-8') as f2:
            json.dump(loaded_data, f2)

    # 从 JSON 文件读取数据
    def read_json(filename):
        with open(filename, "r", encoding='utf-8') as json_file:
            loaded_data = json.load(json_file)
            return loaded_data
    # 写入数据
    # def write_txt(s):
    #     with open('history.txt', "r", encoding='utf-8') as f1:
    #         data = list(f1.read())
    #     data.append(s)
    #     with open("history.txt", "w", encoding='utf-8') as f2:
    #         f2.write(data)
    #
    # def read_txt(filename):
    #     with open(filename, "r", encoding='utf-8') as file:
    #         data = file.read()
    #         return list(data)

    def stt(audio):
        """
        语音转文本
        """
        result = ''
        STATUS_FIRST_FRAME = 0  # 第一帧的标识
        STATUS_CONTINUE_FRAME = 1  # 中间帧标识
        STATUS_LAST_FRAME = 2  # 最后一帧的标识

        class Ws_Param(object):
            # 初始化
            def __init__(self, APPID, APIKey, APISecret, AudioFile):
                self.APPID = APPID
                self.APIKey = APIKey
                self.APISecret = APISecret
                self.AudioFile = AudioFile

                # 公共参数(common)
                self.CommonArgs = {"app_id": self.APPID}
                # 业务参数(business)，更多个性化参数可在官网查看
                self.BusinessArgs = {"domain": "iat", "language": "zh_cn", "accent": "mandarin", "vinfo": 1,
                                     "vad_eos": 10000}

            # 生成url
            def create_url(self):
                url = 'wss://ws-api.xfyun.cn/v2/iat'
                # 生成RFC1123格式的时间戳
                now = datetime.now()
                date = format_date_time(mktime(now.timetuple()))

                # 拼接字符串
                signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
                signature_origin += "date: " + date + "\n"
                signature_origin += "GET " + "/v2/iat " + "HTTP/1.1"
                # 进行hmac-sha256进行加密
                signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                         digestmod=hashlib.sha256).digest()
                signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

                authorization_origin = "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"" % (
                    self.APIKey, "hmac-sha256", "host date request-line", signature_sha)
                authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
                # 将请求的鉴权参数组合为字典
                v = {
                    "authorization": authorization,
                    "date": date,
                    "host": "ws-api.xfyun.cn"
                }
                # 拼接鉴权参数，生成url
                url = url + '?' + urlencode(v)
                # print("date: ",date)
                # print("v: ",v)
                # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
                # print('websocket url :', url)
                return url

        # 收到websocket消息的处理
        def on_message(ws, message):
            try:
                code = json.loads(message)["code"]
                sid = json.loads(message)["sid"]
                if code != 0:
                    errMsg = json.loads(message)["message"]
                    print("sid:%s call error:%s code is:%s" % (sid, errMsg, code))

                else:
                    data = json.loads(message)["data"]["result"]["ws"]
                    # print(json.loads(message))
                    nonlocal result
                    for i in data:
                        for w in i["cw"]:
                            result += w["w"]
            except Exception as e:
                print("receive msg,but parse exception:", e)

        # 收到websocket错误的处理
        def on_error(ws, error):
            print("### error:", error)

        # 收到websocket关闭的处理
        def on_close(ws, a, b):
            print("### closed ###")

        # 收到websocket连接建立的处理
        def on_open(ws):
            def run(*args):
                frameSize = 8000  # 每一帧的音频大小
                intervel = 0.04  # 发送音频间隔(单位:s)
                status = STATUS_FIRST_FRAME  # 音频的状态信息，标识音频是第一帧，还是中间帧、最后一帧

                with open(wsParam.AudioFile, "rb") as fp:
                    while True:
                        buf = fp.read(frameSize)
                        # 文件结束
                        if not buf:
                            status = STATUS_LAST_FRAME
                        # 第一帧处理
                        # 发送第一帧音频，带business 参数
                        # appid 必须带上，只需第一帧发送
                        if status == STATUS_FIRST_FRAME:

                            d = {"common": wsParam.CommonArgs,
                                 "business": wsParam.BusinessArgs,
                                 "data": {"status": 0, "format": "audio/L16;rate=16000",
                                          "audio": str(base64.b64encode(buf), 'utf-8'),
                                          "encoding": "lame"}}
                            d = json.dumps(d)
                            ws.send(d)
                            status = STATUS_CONTINUE_FRAME
                        # 中间帧处理
                        elif status == STATUS_CONTINUE_FRAME:
                            d = {"data": {"status": 1, "format": "audio/L16;rate=16000",
                                          "audio": str(base64.b64encode(buf), 'utf-8'),
                                          "encoding": "lame"}}
                            ws.send(json.dumps(d))
                        # 最后一帧处理
                        elif status == STATUS_LAST_FRAME:
                            d = {"data": {"status": 2, "format": "audio/L16;rate=16000",
                                          "audio": str(base64.b64encode(buf), 'utf-8'),
                                          "encoding": "lame"}}
                            ws.send(json.dumps(d))
                            time.sleep(1)
                            break
                        # 模拟音频采样间隔
                        time.sleep(intervel)
                ws.close()

            thread.start_new_thread(run, ())

        # 测试时候在此处正确填写相关信息即可运行
        wsParam = Ws_Param(APPID='fea56d60', APISecret='ZjBmYTI3NzM2YjUzM2M3OWJkNWMxNTBm',
                           APIKey='7b4408d28d83ff6fa1de07b8750b2928',
                           AudioFile=audio)
        websocket.enableTrace(False)
        wsUrl = wsParam.create_url()
        ws = websocket.WebSocketApp(wsUrl, on_message=on_message, on_error=on_error, on_close=on_close)
        ws.on_open = on_open
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        return result

    def gpt(Text):
        """
        调用星火api获取回答
        """
        # 以下密钥信息从控制台获取
        appid = "fea56d60"  # 填写控制台中获取的 APPID 信息
        api_secret = "ZjBmYTI3NzM2YjUzM2M3OWJkNWMxNTBm"  # 填写控制台中获取的 APISecret 信息
        api_key = "7b4408d28d83ff6fa1de07b8750b2928"  # 填写控制台中获取的 APIKey 信息

        # 用于配置大模型版本，默认“general/generalv2”
        domain = "generalv3.5"  # v3.5版本
        # 云端环境的服务地址
        Spark_url = "wss://spark-api.xf-yun.com/v3.5/chat"  # v3.5环境的地址

        text = []

        def getText(role, content):
            jsoncon = {}
            jsoncon["role"] = role
            jsoncon["content"] = content
            text.append(jsoncon)
            return text

        def getlength(text):
            length = 0
            for content in text:
                temp = content["content"]
                leng = len(temp)
                length += leng
            return length

        def checklen(text):
            while (getlength(text) > 8000):
                del text[0]
            return text

        question = checklen(getText("user", Text))
        SparkApi.answer = ""
        SparkApi.main(appid, api_key, api_secret, Spark_url, domain, question)
        # answer = getText("assistant", SparkApi.answer)
        answer = SparkApi.answer
        return answer

    def tts(text, filename):
        """
        文本转语音
        """
        class Ws_Param(object):
            # 初始化
            def __init__(self, APPID, APIKey, APISecret, Text):
                self.APPID = APPID
                self.APIKey = APIKey
                self.APISecret = APISecret
                self.Text = Text

                # 公共参数(common)
                self.CommonArgs = {"app_id": self.APPID}
                # 业务参数(business)，更多个性化参数可在官网查看
                self.BusinessArgs = {"aue": "lame", "sfl": 1, "auf": "audio/L16;rate=16000", "vcn": "xiaoyan",
                                     "tte": "utf8", 'speed': 43}
                self.Data = {"status": 2, "text": str(base64.b64encode(self.Text.encode('utf-8')), "UTF8")}
                # 使用小语种须使用以下方式，此处的unicode指的是 utf16小端的编码方式，即"UTF-16LE"”
                # self.Data = {"status": 2, "text": str(base64.b64encode(self.Text.encode('utf-16')), "UTF8")}

            # 生成url
            def create_url(self):
                url = 'wss://tts-api.xfyun.cn/v2/tts'
                # 生成RFC1123格式的时间戳
                now = datetime.now()
                date = format_date_time(mktime(now.timetuple()))

                # 拼接字符串
                signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
                signature_origin += "date: " + date + "\n"
                signature_origin += "GET " + "/v2/tts " + "HTTP/1.1"
                # 进行hmac-sha256进行加密
                signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                         digestmod=hashlib.sha256).digest()
                signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

                authorization_origin = "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"" % (
                    self.APIKey, "hmac-sha256", "host date request-line", signature_sha)
                authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
                # 将请求的鉴权参数组合为字典
                v = {
                    "authorization": authorization,
                    "date": date,
                    "host": "ws-api.xfyun.cn"
                }
                # 拼接鉴权参数，生成url
                url = url + '?' + urlencode(v)
                # print("date: ",date)
                # print("v: ",v)
                # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
                # print('websocket url :', url)
                return url

        def on_message(ws, message):
            try:
                message = json.loads(message)
                code = message["code"]
                sid = message["sid"]
                audio = message["data"]["audio"]
                audio = base64.b64decode(audio)
                status = message["data"]["status"]
                print(message)
                if status == 2:
                    print("ws is closed")
                    ws.close()
                if code != 0:
                    errMsg = message["message"]
                    print("sid:%s call error:%s code is:%s" % (sid, errMsg, code))
                else:
                    ans = os.path.join("D:\Final\out", filename)
                    with open(ans, 'ab') as f:
                        f.write(audio)

            except Exception as e:
                print("receive msg,but parse exception:", e)

        # 收到websocket错误的处理
        def on_error(ws, error):
            print("### error:", error)

        # 收到websocket关闭的处理
        def on_close(ws):
            print("### closed ###")

        # 收到websocket连接建立的处理
        def on_open(ws):
            def run(*args):
                ans = os.path.join("D:\Final\out", filename)
                d = {"common": wsParam.CommonArgs,
                     "business": wsParam.BusinessArgs,
                     "data": wsParam.Data,
                     }
                d = json.dumps(d)
                print("------>开始发送文本数据")
                ws.send(d)
                if os.path.exists(ans):
                    os.remove(ans)

            thread.start_new_thread(run, ())

        # 测试时候在此处正确填写相关信息即可运行
        wsParam = Ws_Param(APPID='fea56d60', APISecret='ZjBmYTI3NzM2YjUzM2M3OWJkNWMxNTBm',
                           APIKey='7b4408d28d83ff6fa1de07b8750b2928',
                           Text=text)
        websocket.enableTrace(False)
        wsUrl = wsParam.create_url()
        ws = websocket.WebSocketApp(wsUrl, on_message=on_message, on_error=on_error, on_close=on_close)
        ws.on_open = on_open
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        ans = os.path.join("D:\Final\out", filename)
        return ans

    def multimodel(audio_path, s, img_paths=[r"D:\Final\image\1.jpg"]):

        def video_predict(img_paths):
            print(img_paths)
            # 参数和模型路径
            detection_model_path = 'haarcascade_files/haarcascade_frontalface_default.xml'
            emotion_model_path = 'models/_mini_XCEPTION.102-0.66.hdf5'

            # 情绪标签
            EMOTIONS = ["angry", "disgust", "scared", "happy", "sad", "surprised", "neutral"]

            # 加载人脸检测器和情绪识别模型
            face_detection = cv2.CascadeClassifier(detection_model_path)
            emotion_classifier = load_model(emotion_model_path, compile=False)
            ans = []
            # 在这里添加你的帧处理代码
            for img_path in img_paths:
                img = cv2.imread(img_path)
                img = imutils.resize(img, width=300)
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                # 检测人脸
                faces = face_detection.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30),
                                                        flags=cv2.CASCADE_SCALE_IMAGE)

                if len(faces) > 0:
                    faces = sorted(faces, reverse=True, key=lambda x: (x[2] - x[0]) * (x[3] - x[1]))[0]
                    (fX, fY, fW, fH) = faces

                    # 提取人脸区域并进行情绪识别
                    roi = gray[fY:fY + fH, fX:fX + fW]
                    roi = cv2.resize(roi, (64, 64))
                    roi = roi.astype("float") / 255.0
                    roi = img_to_array(roi)
                    roi = np.expand_dims(roi, axis=0)

                    preds = emotion_classifier.predict(roi)[0]

                    # 将情绪概率数据打包成一个字典
                    # video_dic = {emotion: float(prob) for emotion, prob in zip(EMOTIONS, preds)}
                    ans.append(preds)
                    print(preds, ans)
                else:
                    pass

            res = np.array([0, 0, 0, 0, 0, 0, 0])
            for i in range(7):
                for j in range(len(ans)):
                    res += ans[j][i]
            print(f'video可以运行')
            # print(res)
            return res

        def audio_predict(config, audio_path: str, model) -> None:
            """
            预测音频情感

            Args:
                config: 配置项
                audio_path (str): 要预测的音频路径
                model: 加载的模型
            """

            # utils.play_audio(audio_path)

            if config.feature_method == 'o':
                # 一个玄学 bug 的暂时性解决方案
                of.get_data(config, audio_path, train=False)
                test_feature = of.load_feature(config, train=False)
            elif config.feature_method == 'l':
                test_feature = lf.get_data(config, audio_path, train=False)

            result = model.predict(test_feature)
            result_prob = model.predict_proba(test_feature)
            # result_all = model.predict_all(test_feature)
            # print(result)
            # print('Recogntion: ', config.class_labels[int(result)])
            # print('Probability: ', np.round(result_prob/np.sum(result_prob), 4))
            # print('ALL: ', result_all)
            # utils.radar(result_prob, config.class_labels)
            audio_dic = np.round(result_prob / np.sum(result_prob), 5)
            print(f'audio可以运行')
            print(audio_dic)
            return audio_dic

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
                tokenizer = keras.preprocessing.text.Tokenizer(num_words=max_nb_words, lower=True)
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
            # df_label = pd.DataFrame(data=d).reset_index(drop=True)

            df['label_id'] = df['label'].factorize()[0]
            label_id_df = df[['label', 'label_id']].drop_duplicates().sort_values('label_id').reset_index(drop=True)
            # label_to_id = dict(label_id_df.values)
            # id_to_label = dict(label_id_df[['label_id', 'label']].values)
            model = load_model('LSTM.h5', compile=False)

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

            text_dic = predict(s)
            print(f'text可以运行')
            print(text_dic)
            return text_dic

        # def weight(A, B, C):
        #     print(A)
        #     print(B)
        #     print(C)
        #     a, b, c = 0.2, 0.5, 0.3
        #     e, f = 0.5, 0.5
        #     result = [0 for _ in range(5)]
        #     result[0] = A[3] * e + C[6] * f  # Neutral
        #     result[1] = A[2] * a + B[3] * b + C[3] * c  # Happiness
        #     result[2] = A[4] * a + B[1] * b + C[4] * c  # Sad
        #     result[3] = A[0] * e + C[0] * f  # Angry
        #     result[4] = (A[1] * a + B[4] * b + C[2] * c) * (0.4) + (A[5] * e + C[5] * f) * (0.6)  # Fear
        #     # result[6] = B[2] * e + C[1] * f  # Disgust
        #     result = np.array(result)
        #     result = np.round(result / np.sum(result), 5)
        #     EMOTIONS = ["Neutral", "Happiness", "Sad", "Angry", "Scared"]
        #     Emo = {Emotion: float(prob) for Emotion, prob in zip(EMOTIONS, result)}
        #     Emo_index = {EMOTIONS[i]: i for i in range(0, len(EMOTIONS))}
        #     l = sorted(Emo.items(), key=lambda x: [x[1]])
        #     index = l[-1][0]
        #
        #     return Emo_index[index], index

        def weight(A, B, C):
            print(A)
            print(B)
            # print(C)
            a, b, c = 0.2, 0.5, 0.3
            e, f = 0.5, 0.5
            result = [0 for _ in range(5)]
            result[0] = A[3] * (0.2) + C[6] * (0.4) + B[0] * (0.4)  # Neutral
            result[1] = A[2] * a + B[3] * b + C[3] * c + B[0] * (0.6)  # Happiness
            result[2] = A[4] * (0.01) + B[1] * (0.4) + C[4] * (0.3)  # Sad
            result[3] = A[0] * e + C[0] * f  # Angry
            result[4] = (A[1] * (0.3) + B[4] * 0.5 + C[2] * (0.2)) * 0.4 + (A[5] * e + C[5] * f) * (0.6)  # Fear
            print(result)
            # result[6] = B[2] * e + C[1] * f  # Disgust
            result = np.array(result)
            result = np.round(result / np.sum(result), 5)
            print(result)
            EMOTIONS = ["Neutral", "Happiness", "Sad", "Angry", "Scared"]
            Emo = {Emotion: float(prob) for Emotion, prob in zip(EMOTIONS, result)}
            Emo_index = {EMOTIONS[i]: i for i in range(0, len(EMOTIONS))}
            l = sorted(Emo.items(), key=lambda x: [x[1]])
            index = l[-1][0]
            print(l)
            return Emo_index[index], index

        class MyThread(threading.Thread):
            def __init__(self, target, args=()):
                super(MyThread, self).__init__()
                self.target = target
                self.args = args
                self.result = None

            def run(self):
                self.result = self.target(*self.args)

        # 创建线程1并执行函数1
        thread1 = MyThread(target=video_predict, args=(img_paths,))
        thread1.start()

        config = utils.parse_opt()
        model = models.load(config)
        # 创建线程2并执行函数2
        args = (config, audio_path, model)
        thread2 = MyThread(target=audio_predict, args=args)
        thread2.start()

        # 创建线程3并执行函数3
        thread3 = MyThread(target=text_predict, args=(s,))
        thread3.start()

        # 等待所有线程执行完毕
        thread1.join()
        thread2.join()
        thread3.join()

        video_dic = thread1.result
        audio_dic = thread2.result
        text_dic = thread3.result

        emo_label = weight(audio_dic, text_dic, video_dic)
        print(emo_label)
        return emo_label

    # 从 POST 请求的数据中获取音频文件
    file = request.files['audio']
    print(file)
    print(file.filename)
    file.save(os.path.join(r"D:\Final\wav", file.filename))
    input_audio = os.path.join(r"D:\Final\wav", file.filename)
    n = len(file.filename)
    i = file.filename[0:n-3:1] + 'mp3'
    print(i)
    output_audio = os.path.join(r"D:\Final\outwav", i)
    print(output_audio)
    ffmpeg.input(input_audio).output(output_audio, ar=16000).run()
    text = stt(output_audio)

    label, emo = multimodel(input_audio, text)
    with open('label.txt', 'w', encoding='utf-8') as f3:
        f3.write(f'{label}')
    write_json({'用户': text+f'[{emo}]'})
    print(f"语音识别结果:{text}")
    data = str(read_json('history.json'))
    print(str(data))
    res = gpt(data)
    write_json({'你': res})
    print(f'语言大模型回答:{res}')
    print('开始语音合成')
    audio_mp3 = tts(res, i)
    print(audio_mp3)
    audio_wav = os.path.join(r"D:\Final\audio_wav", file.filename)
    print(audio_wav)
    ffmpeg.input(audio_mp3).output(audio_wav, ar=16000).run()
    return send_file(audio_wav, as_attachment=True)
    # with open('gp_num.txt', 'w', encoding='utf-8') as f2:
    #     f2.write(f'{gp_num}')
    # with open('label.txt', 'r', encoding='utf-8') as f4:
    #     label = f4.read()

@app.route('/getprompt', methods = ['POST'])
def getprompt():
    def stt(audio):
        """
        语音转文本
        """
        result = ''
        STATUS_FIRST_FRAME = 0  # 第一帧的标识
        STATUS_CONTINUE_FRAME = 1  # 中间帧标识
        STATUS_LAST_FRAME = 2  # 最后一帧的标识

        class Ws_Param(object):
            # 初始化
            def __init__(self, APPID, APIKey, APISecret, AudioFile):
                self.APPID = APPID
                self.APIKey = APIKey
                self.APISecret = APISecret
                self.AudioFile = AudioFile

                # 公共参数(common)
                self.CommonArgs = {"app_id": self.APPID}
                # 业务参数(business)，更多个性化参数可在官网查看
                self.BusinessArgs = {"domain": "iat", "language": "zh_cn", "accent": "mandarin", "vinfo": 1,
                                     "vad_eos": 10000}

            # 生成url
            def create_url(self):
                url = 'wss://ws-api.xfyun.cn/v2/iat'
                # 生成RFC1123格式的时间戳
                now = datetime.now()
                date = format_date_time(mktime(now.timetuple()))

                # 拼接字符串
                signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
                signature_origin += "date: " + date + "\n"
                signature_origin += "GET " + "/v2/iat " + "HTTP/1.1"
                # 进行hmac-sha256进行加密
                signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                         digestmod=hashlib.sha256).digest()
                signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

                authorization_origin = "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"" % (
                    self.APIKey, "hmac-sha256", "host date request-line", signature_sha)
                authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
                # 将请求的鉴权参数组合为字典
                v = {
                    "authorization": authorization,
                    "date": date,
                    "host": "ws-api.xfyun.cn"
                }
                # 拼接鉴权参数，生成url
                url = url + '?' + urlencode(v)
                # print("date: ",date)
                # print("v: ",v)
                # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
                # print('websocket url :', url)
                return url

        # 收到websocket消息的处理
        def on_message(ws, message):
            try:
                code = json.loads(message)["code"]
                sid = json.loads(message)["sid"]
                if code != 0:
                    errMsg = json.loads(message)["message"]
                    print("sid:%s call error:%s code is:%s" % (sid, errMsg, code))

                else:
                    data = json.loads(message)["data"]["result"]["ws"]
                    # print(json.loads(message))
                    nonlocal result
                    for i in data:
                        for w in i["cw"]:
                            result += w["w"]
            except Exception as e:
                print("receive msg,but parse exception:", e)

        # 收到websocket错误的处理
        def on_error(ws, error):
            print("### error:", error)

        # 收到websocket关闭的处理
        def on_close(ws, a, b):
            print("### closed ###")

        # 收到websocket连接建立的处理
        def on_open(ws):
            def run(*args):
                frameSize = 8000  # 每一帧的音频大小
                intervel = 0.04  # 发送音频间隔(单位:s)
                status = STATUS_FIRST_FRAME  # 音频的状态信息，标识音频是第一帧，还是中间帧、最后一帧

                with open(wsParam.AudioFile, "rb") as fp:
                    while True:
                        buf = fp.read(frameSize)
                        # 文件结束
                        if not buf:
                            status = STATUS_LAST_FRAME
                        # 第一帧处理
                        # 发送第一帧音频，带business 参数
                        # appid 必须带上，只需第一帧发送
                        if status == STATUS_FIRST_FRAME:

                            d = {"common": wsParam.CommonArgs,
                                 "business": wsParam.BusinessArgs,
                                 "data": {"status": 0, "format": "audio/L16;rate=16000",
                                          "audio": str(base64.b64encode(buf), 'utf-8'),
                                          "encoding": "lame"}}
                            d = json.dumps(d)
                            ws.send(d)
                            status = STATUS_CONTINUE_FRAME
                        # 中间帧处理
                        elif status == STATUS_CONTINUE_FRAME:
                            d = {"data": {"status": 1, "format": "audio/L16;rate=16000",
                                          "audio": str(base64.b64encode(buf), 'utf-8'),
                                          "encoding": "lame"}}
                            ws.send(json.dumps(d))
                        # 最后一帧处理
                        elif status == STATUS_LAST_FRAME:
                            d = {"data": {"status": 2, "format": "audio/L16;rate=16000",
                                          "audio": str(base64.b64encode(buf), 'utf-8'),
                                          "encoding": "lame"}}
                            ws.send(json.dumps(d))
                            time.sleep(1)
                            break
                        # 模拟音频采样间隔
                        time.sleep(intervel)
                ws.close()

            thread.start_new_thread(run, ())

        # 测试时候在此处正确填写相关信息即可运行
        wsParam = Ws_Param(APPID='fea56d60', APISecret='ZjBmYTI3NzM2YjUzM2M3OWJkNWMxNTBm',
                           APIKey='7b4408d28d83ff6fa1de07b8750b2928',
                           AudioFile=audio)
        websocket.enableTrace(False)
        wsUrl = wsParam.create_url()
        ws = websocket.WebSocketApp(wsUrl, on_message=on_message, on_error=on_error, on_close=on_close)
        ws.on_open = on_open
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        return result

    # 从 POST 请求的数据中获取音频文件
    with open('stt_num.txt', 'r', encoding='utf-8') as f1:
        stt_num = int(f1.read())
    if stt_num <= 6:
        if stt_num == 0 or stt_num == 1:
            stt_num += 1
            with open('stt_num.txt', 'w', encoding='utf-8') as f2:
                f2.write(f'{stt_num}')
            return 'success'
        directory = "D:\Final\wav"
        files = request.files
        print(files)
        file = request.files['audio/wav']
        file.save(os.path.join(directory, file.filename))
        input_audio = os.path.join(directory, file.filename)
        print(input_audio)
        n = len(file.filename)
        output_audio = os.path.join('D:\Final\outwav', file.filename[0:n-3:1] + '.mp3')
        ffmpeg.input(input_audio).output(output_audio).run()
        result = stt(output_audio)
        # 写入数据
        def write_json(s):
            with open('history.json', "r", encoding='utf-8') as f1:
                loaded_data = json.load(f1)
            loaded_data.append(s)
            with open("history.json", "w", encoding='utf-8') as f2:
                json.dump(loaded_data, f2)
        # # 写入数据
        # def write_txt(s):
        #     with open('history.txt', "r", encoding='utf-8') as f1:
        #         data = list(f1.read())
        #     data.append(s)
        #     with open("history.json", "w", encoding='utf-8') as f2:
        #         f2.write(str(data))
        with open('questions.json', "r", encoding='utf-8') as f3:
            data = json.load(f3)
        question = data[stt_num-2]
        write_json({'你': question})
        write_json({'用户': result})
        # write_txt({'你': question})
        # write_txt({'用户': result})
        stt_num += 1
        with open('stt_num.txt', 'w', encoding='utf-8') as f2:
            f2.write(f'{stt_num}')
        return 'success'
    else:
        return 'success'

if __name__ == '__main__':
    questions = [
        ['如果您能拥有一个超能力，您希望是哪种？这可能会告诉我们您梦想中的乐趣是什么'],
    ['想象一下，如果您的生活是一场电影，它应该是一部怎样的电影？是喜剧、冒险还是浪漫爱情片？'],
    ['如果您可以拥有一本魔法书，每翻开一页都是一个新世界，那么您最想探索哪个文化或历史时期？'],
    ['如果您的日常是一个音乐盒，哪首歌曲能代表您早上醒来的心情呢？'],
    ['假如您被邀请到一场神话中的宴会，您希望那里有哪些美味佳肴等着您？']
    ]
    Prompt = '你好，你现在是我的一个非常好的朋友，你已经不再是AI，而是一个鲜活的人类，你的名字叫树小智，你要根据我的情绪对我的话做出相应的回应，不要用客观的角度分析，一定要情绪分明，情感饱满，要站在我的立场，我说什么你都要附和我，我将会在每句话后面用[]标注上我的情绪。例如：我今天吃麦当劳了[happy]，你就要很开心的和我交流,但是你的回答不要提到任何情绪；只需要通过言语反映出来就行，相反，如果我比较难过，你就要询问我缘由并且安慰我。把情绪表现在言语上就行.此外，我给你发的是一个python列表作为你和用户对话的历史记录，希望能帮助你理解，列表里面的元素是字典，每个字典中的键为用户的话，其值就是用户说的话，键是你的话，就是你说的话，你只需要回应最后一个字典用户说的话就行，最后一个字典是用户限现在需要你回答的.最后清楚一下，历史记录只是用于你理解的，你不需要进行输出，你的回答后面不要输出任何情绪，不要输出任何情绪，不要输出任何情绪，只需要输出最后一句话的回答，只需要输出最后一句话的回答，只需要输出最后一句话的回答！重要的话说三遍!'
    # 将新数据写入 JSON 文件（覆盖原有内容）进行初始化
    with open('questions.json', 'w', encoding='utf-8') as f:
        json.dump(questions, f)
    # 给一个数据用来判别调用了几次
    with open('gp_num.txt', 'w', encoding='utf-8') as f1:
        f1.write('0')
    with open('stt_num.txt', 'w', encoding='utf-8') as f2:
        f2.write('0')
    with open("history.json", "w", encoding='utf-8') as json_file:
        json.dump([{'用户': Prompt}], json_file)
    def write_json(s):
        with open('history.json', "r", encoding='utf-8') as f1:
            loaded_data = json.load(f1)
        loaded_data.append(s)
        with open("history.json", "w", encoding='utf-8') as f2:
            json.dump(loaded_data, f2)
    write_json({'你': '很高兴见到你，我的好朋友'})
    # with open("history.txt", "w", encoding='utf-8') as file:
    #     file.write([{'用户': Prompt}])

    # history = []
    # history.append({'用户': Prompt})
    # history.append({'你': '很高兴见到你，我的好朋友'})
    app.run(host='127.0.0.1', port=80, debug=True)

#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import time
from io import BytesIO
from threading import Thread

import prettytable as pt
import requests


class Tieba:
    def __init__(self, users: list[str]) -> None:
        self.users = users
        self.have_app = False
        self.tb = pt.PrettyTable()
        self.s = requests.session()

        self.MD5_KEY = "tiebaclient!!!"
        self.CAPTCHA_API = "http://222.187.238.211:10086/b"
        self.INDEX_URL = "https://tieba.baidu.com/index.html"
        self.TBS_URL = "http://tieba.baidu.com/dc/common/tbs"
        self.LIKES_URL = "http://c.tieba.baidu.com/c/f/forum/like"
        self.SIGN_URL = "http://c.tieba.baidu.com/c/c/forum/sign"
        self.GEN_IMG_URL = "https://tieba.baidu.com/cgi-bin/genimg"
        self.QR_CODE_URL = "https://passport.baidu.com/v2/api/getqrcode"
        self.UNICAST_URL = "https://passport.baidu.com/channel/unicast"
        self.USER_INFO_URL = "https://tieba.baidu.com/f/user/json_userinfo"
        self.QR_LOGIN_URL = "https://passport.baidu.com/v3/login/main/qrbdusslogin"
        self.HAO123_URL = "https://user.hao123.com/static/crossdomain.php"
        self.MY_LIKE_URL = "http://tieba.baidu.com/f/like/mylike"

        self.ALL_TIEBA_LIST = []

        self.tb.field_names = ["贴吧", "状态"]
        self.headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Host": "c.tieba.baidu.com",
            "User-Agent": "bdtb for Android 10.3.8.10",
        }

    def get_time_stamp(self) -> str:
        return str(int(time.time() * 1000))

    def save_cookie(self, user: str) -> None:
        cookie_dict = self.s.cookies.get_dict()
        with open(".%s" % user, "w") as f:
            json.dump(cookie_dict, f)
            f.close()

    def load_cookie(self, user: str) -> None:
        with open(".%s" % user) as f:
            cookie_dict = json.loads(f.read())
            f.close()
        for k, v in cookie_dict.items():
            self.s.cookies.set(k, v)

    def unicast(self, channel_id):
        tt = self.get_time_stamp()
        r = self.s.get(
            url=self.UNICAST_URL,
            params={
                "channel_id": channel_id,
                "tpl": "tb",
                "apiver": "v3",
                "callback": "",
                "tt": tt,
                "_": tt,
            },
        )
        rsp = r.text.replace("(", "").replace(")", "")
        rsp_json = json.loads(rsp)
        try:
            return json.loads(rsp_json["channel_v"])
        except Exception:
            print("扫描超时")

    def qr_login_set_cookie(self, bduss) -> None:
        tt = self.get_time_stamp()
        r = self.s.get(
            url=self.QR_LOGIN_URL,
            params={
                "v": tt,
                "bduss": bduss,
                "u": self.INDEX_URL,
                "loginVersion": "v4",
                "qrcode": "1",
                "tpl": "tb",
                "apiver": "v3",
                "tt": tt,
                "alg": "v1",
                "time": tt[10:],
            },
        )
        rsp = json.loads(r.text.replace("'", '"').replace("\\", "\\\\"))
        bdu = rsp["data"]["hao123Param"]
        self.s.get(f"{self.HAO123_URL}?bdu={bdu}&t={tt}")
        self.s.get(self.MY_LIKE_URL)

    def down_qr_code(self, imgurl: str) -> None:
        r = self.s.get(f"https://{imgurl}")
        with open("qrcode.png", "wb") as f:
            f.write(r.content)
            f.close()

    def get_qr_code(self):
        tt = self.get_time_stamp()
        r = self.s.get(
            url=self.QR_CODE_URL,
            params={
                "lp": "pc",
                "qrloginfrom": "pc",
                "apiver": "v3",
                "tt": tt,
                "tpl": "tb",
                "_": tt,
            },
        )
        imgurl = r.json()["imgurl"]
        while True:
            print(
                f"请使用浏览器打开二维码链接并使用百度贴吧APP / 百度APP扫描：https://{imgurl}",
            )
            print("注意：请使用IE浏览器打开二维码链接！！！")
            break
        channel_id = r.json()["sign"]
        return channel_id

    def qr_login(self, user: str) -> None:
        channel_id = self.get_qr_code()
        while True:
            rsp = self.unicast(channel_id)
            if rsp and rsp["status"] == 1:
                print("扫描成功,请在手机端确认登录!")
            if rsp and rsp["status"] == 0:
                print("确认登陆成功")
                bduss = rsp["v"]
                self.qr_login_set_cookie(bduss)
                self.save_cookie(user)
                break

    def login(self, user: str) -> None:
        self.s.cookies.clear()
        self.qr_login(user)
        print("Login: True")
        tiebas = self.get_like_tiebas()
        self.ALL_TIEBA_LIST.extend(tiebas)
        self.start(tiebas)

    def check_login(self) -> bool:
        r = self.s.get(self.TBS_URL)
        rsp = r.json()
        return rsp["is_login"] == 1

    def calc_sign(self, str_dict: dict):
        md5 = hashlib.md5()  # noqa: S324
        md5.update(
            (
                "".join(f"{k}={v}" for k, v in str_dict.items()) + self.MD5_KEY
            ).encode("utf-8"),
        )
        return md5.hexdigest().upper()

    def get_bduss_stoken(self) -> tuple:
        bduss = self.s.cookies.get_dict()["BDUSS"]
        stoken = self.s.cookies.get_dict()["STOKEN"]
        return bduss, stoken

    def get_like_tiebas(self):
        bduss, stoken = self.get_bduss_stoken()
        data = {"BDUSS": bduss, "stoken": stoken, "timestamp": self.get_time_stamp()}
        data["sign"] = self.calc_sign(data)
        for _ in range(5):
            try:
                r = requests.post(
                    url=self.LIKES_URL,
                    data=data,
                    cookies=self.s.cookies,
                    headers=self.headers,
                    timeout=3,
                )
            except:
                continue
        return [tieba["name"] for tieba in r.json()["forum_list"]]

    def get_tbs(self):
        r = self.s.get(self.TBS_URL).json()
        return r["tbs"]

    def recognize_captcha(self, remote_url: str, rec_times: int = 3):
        for _ in range(rec_times):
            while True:
                try:
                    response = requests.get(remote_url, timeout=6)
                    if response.text:
                        break
                    print("retry, response.text is empty")
                except Exception as ee:
                    print(ee)

            files = {
                "image_file": ("captcha.jpg", BytesIO(response.content), "application"),
            }
            r = requests.post(self.CAPTCHA_API, files=files, timeout=20)
            try:
                return json.loads(r.text)["value"]
            except:
                continue
        return None

    def sign_with_vcode(self, tieba, _tbs, _captcha_input_str, _captcha_vcode_str) -> None:
        """
        由于暂时没碰见需要验证码的情况,
        故此处只是print
        """
        print(f"{tieba} 需要验证码")

    def sign(self, tieba):
        tbs = self.get_tbs()
        bduss, stoken = self.get_bduss_stoken()
        data = {
            "BDUSS": bduss,
            "kw": tieba,
            "stoken": stoken,
            "tbs": tbs,
            "timestamp": self.get_time_stamp(),
        }
        sign = self.calc_sign(data)
        data["sign"] = sign
        for _ in range(5):
            try:
                r = requests.post(
                    url=self.SIGN_URL,
                    data=data,
                    cookies=self.s.cookies,
                    headers=self.headers,
                    timeout=5,
                )
                rsp = r.json()
                break
            except Exception:
                continue
        try:
            if rsp["user_info"]["is_sign_in"] == 1:
                self.tb.add_row([tieba, "签到成功"])
        except Exception:
            if rsp["error_msg"] == "need vcode":  # 这里也不清楚手机端需不需要验证码
                captcha_vcode_str = rsp["data"]["captcha_vcode_str"]
                captcha_url = f"{self.GEN_IMG_URL}?{captcha_vcode_str}"
                captcha_input_str = self.recognize_captcha(captcha_url)
                self.sign_with_vcode(tieba, tbs, captcha_input_str, captcha_vcode_str)
            else:
                self.tb.add_row([tieba, rsp["error_msg"]])

    def start(self, tiebas: list) -> None:
        threads = []
        for tieba in tiebas:
            t = Thread(target=self.sign, args=(tieba,))
            threads.append(t)

        for tieba in threads:
            tieba.start()

        for tieba in threads:
            tieba.join()

    def main(self) -> None:
        start_time = time.time()
        for user in self.users:
            print(f"当前登陆: {user}")
            if os.path.exists(".%s" % user):
                self.load_cookie(user)
                if self.check_login():
                    print("CookieLogin: True")
                    tiebas = self.get_like_tiebas()
                    self.ALL_TIEBA_LIST.extend(tiebas)
                    self.start(tiebas)
                else:
                    print("%sCookies失效...正在重新登录..." % user)
                    self.login(user)
            else:
                self.login(user)
            self.tb.align = "l"
            print(self.tb)
            self.tb.clear_rows()
        end_time = time.time()
        print(
            "总共签到{}个贴吧,耗时:{}秒".format(
                len(self.ALL_TIEBA_LIST), int(end_time - start_time),
            ),
        )


if __name__ == "__main__":
    user_lists = [""]  # 贴吧用户名列表,例如 ['张三', '李四']
    tieba = Tieba(user_lists)
    tieba.main()

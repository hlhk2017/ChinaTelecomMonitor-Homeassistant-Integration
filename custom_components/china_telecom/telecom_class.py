#!/usr/bin/env python3
# _*_ coding:utf-8 _*_

import re
import base64
import random
import requests
from datetime import datetime
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
import logging 
import ssl
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
import certifi

_LOGGER = logging.getLogger(__name__) 

class TelecomSSLAdapter(HTTPAdapter):
    """自定义适配器解决SSL证书问题"""
    def __init__(self):
        # 首先定义 ssl_context 属性
        self.ssl_context = None
        
        # 然后调用父类初始化
        super().__init__()
        
    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        # 延迟创建 SSL 上下文（第一次使用时创建）
        if self.ssl_context is None:
            # 创建 SSL 上下文
            self.ssl_context = create_urllib3_context()
            # 降低安全级别以兼容旧服务器
            self.ssl_context.set_ciphers('DEFAULT:@SECLEVEL=1')
            # 加载证书
            self.ssl_context.load_verify_locations(cafile=certifi.where())
        
        # 使用创建的 SSL 上下文
        pool_kwargs['ssl_context'] = self.ssl_context
        return super().init_poolmanager(connections, maxsize, block, **pool_kwargs)

class Telecom:
    def __init__(self):
        self.login_info = {}
        self.phonenum = None
        self.password = None
        self.token = None
        self.client_type = "#12.2.0#channel50#iPhone 14 Pro#"
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "user-agent": "P216010901",
        }
        
        # 创建会话并使用自定义适配器
        self.session = requests.Session()
        adapter = TelecomSSLAdapter()
        self.session.mount("https://", adapter)
        
        # 设置验证使用 certifi
        self.session.verify = certifi.where()

    def set_login_info(self, login_info):
        self.login_info = login_info
        self.phonenum = login_info.get("phonenum", None)
        self.password = login_info.get("password", None)
        self.token = login_info.get("token", None)

    def trans_number(self, phonenum, encode=True):
        result = ""
        caesar_size = 2 if encode else -2
        for char in phonenum:
            result += chr(ord(char) + caesar_size & 65535)
        return result

    def encrypt(self, str):
        public_key_pem = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDBkLT15ThVgz6/NOl6s8GNPofd
WzWbCkWnkaAm7O2LjkM1H7dMvzkiqdxU02jamGRHLX/ZNMCXHnPcW/sDhiFCBN18
qFvy8g6VYb9QtroI09e176s+ZCtiv7hbin2cCTj99iUpnEloZm19lwHyo69u5UMi
PMpq0/XKBO8lYhN/gwIDAQAB
-----END PUBLIC KEY-----"""
        public_key = RSA.import_key(public_key_pem.encode())
        cipher = PKCS1_v1_5.new(public_key)
        ciphertext = cipher.encrypt(str.encode())
        encoded_ciphertext = base64.b64encode(ciphertext).decode()
        return encoded_ciphertext

    def get_fee_flow_limit(self, fee_remain_flow):
        today = datetime.today()
        days_in_month = (
            datetime(today.year, today.month + 1, 1)
            - datetime(today.year, today.month, 1)
        ).days
        return int((fee_remain_flow / days_in_month))

    def do_login(self, phonenum, password):
        phonenum = phonenum or self.phonenum
        password = password or self.password
        uuid = str(random.randint(1000000000000000, 9999999999999999))
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        enc_str = f"iPhone 14 13.2.{uuid[:12]}{phonenum}{ts}{password}0$$$0."
        body = {
            "content": {
                "fieldData": {
                    "accountType": "",
                    "authentication": self.trans_number(password),
                    "deviceUid": uuid[:16],
                    "isChinatelecom": "",
                    "loginAuthCipherAsymmertric": self.encrypt(enc_str),
                    "loginType": "4",
                    "phoneNum": self.trans_number(phonenum),
                    "systemVersion": "13.2.3",
                },
                "attach": "test",
            },
            "headerInfos": {
                "code": "userLoginNormal",
                "clientType": self.client_type,
                "timestamp": ts,
                "shopId": "20002",
                "source": "110003",
                "sourcePassword": "Sid98s",
                "token": "",
                "userLoginName": self.trans_number(phonenum),
            },
        }
        try:
            response = self.session.post(
                "https://appgologin.189.cn:9031/login/client/userLoginNormal",
                headers=self.headers,
                json=body,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.SSLError as ssl_err:
            _LOGGER.error(f"SSL验证失败: {ssl_err}")
            _LOGGER.warning("尝试临时禁用SSL验证...")
            # 使用独立的会话临时禁用验证
            temp_session = requests.Session()
            response = temp_session.post(
                "https://appgologin.189.cn:9031/login/client/userLoginNormal",
                headers=self.headers,
                json=body,
                verify=False,
                timeout=30
            )
            return response.json()
        except requests.exceptions.RequestException as req_err:
            _LOGGER.error(f"请求失败: {req_err}")
            return {"error": str(req_err)}

    def qry_important_data(self, **kwargs):
        ts = datetime.now().strftime("%Y%m%d%H%M00")
        body = {
            "content": {
                "fieldData": {
                    "provinceCode": self.login_info["provinceCode"] or "600101",
                    "cityCode": self.login_info["cityCode"] or "8441900",
                    "shopId": "20002",
                    "isChinatelecom": "0",
                    "account": self.trans_number(self.phonenum),
                },
                "attach": "test",
            },
            "headerInfos": {
                "code": "userFluxPackage",
                "clientType": self.client_type,
                "timestamp": ts,
                "shopId": "20002",
                "source": "110003",
                "sourcePassword": "Sid98s",
                "userLoginName": self.trans_number(self.phonenum),
                "token": kwargs.get("token") or self.token,
            },
        }
        try:
            response = self.session.post(
                "https://appfuwu.189.cn:9021/query/qryImportantData",
                headers=self.headers,
                json=body,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _LOGGER.error(f"查询重要数据失败: {e}")
            return {}

    def user_flux_package(self, **kwargs):
        billing_cycle = kwargs.get("billing_cycle") or datetime.now().strftime("%Y%m")
        ts = datetime.now().strftime("%Y%m%d%H%M00")
        body = {
            "content": {
                "fieldData": {
                    "queryFlag": "0",
                    "accessAuth": "1",
                    "account": self.trans_number(self.phonenum),
                },
                "attach": "test",
            },
            "headerInfos": {
                "code": "userFluxPackage",
                "clientType": self.client_type,
                "timestamp": ts,
                "shopId": "20002",
                "source": "110003",
                "sourcePassword": "Sid98s",
                "userLoginName": self.trans_number(self.phonenum),
                "token": kwargs.get("token") or self.token,
            },
        }
        try:
            response = self.session.post(
                "https://appfuwu.189.cn:9021/query/userFluxPackage",
                headers=self.headers,
                json=body,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _LOGGER.error(f"查询流量包失败: {e}")
            return {}

    def qry_share_usage(self, **kwargs):
        billing_cycle = kwargs.get("billing_cycle") or datetime.now().strftime("%Y%m")
        ts = datetime.now().strftime("%Y%m%d%H%M00")
        body = {
            "content": {
                "attach": "test",
                "fieldData": {
                    "billingCycle": billing_cycle,
                    "account": self.trans_number(self.phonenum),
                },
            },
            "headerInfos": {
                "code": "qryShareUsage",
                "clientType": self.client_type,
                "timestamp": ts,
                "shopId": "20002",
                "source": "110003",
                "sourcePassword": "Sid98s",
                "userLoginName": self.trans_number(self.phonenum),
                "token": kwargs.get("token") or self.token,
            },
        }
        try:
            response = self.session.post(
                "https://appfuwu.189.cn:9021/query/qryShareUsage",
                headers=self.headers,
                json=body,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            # 返回的号码字段加密，需做解密转换
            if data.get("responseData") and data.get("responseData").get(
                "data", {}
            ).get("sharePhoneBeans", []):
                for item in data["responseData"]["data"]["sharePhoneBeans"]:
                    item["sharePhoneNum"] = self.trans_number(item["sharePhoneNum"], False)
                for share_type in data["responseData"]["data"]["shareTypeBeans"]:
                    for share_info in share_type["shareUsageInfos"]:
                        for share_amount in share_info["shareUsageAmounts"]:
                            share_amount["phoneNum"] = self.trans_number(
                                share_amount["phoneNum"], False
                            )
            return data
        except requests.exceptions.RequestException as e:
            _LOGGER.error(f"查询共享使用情况失败: {e}")
            return {}

    def to_summary(self, data, phonenum=""):
        if not data:
            return {}
        phonenum = phonenum or self.phonenum

        # Default to empty dicts if flowInfo or voiceInfo are None
        flow_info = data.get("flowInfo") or {}
        voice_info = data.get("voiceInfo") or {}
        integral_info = data.get("integralInfo") or {}

        # 总流量
        total_amount = flow_info.get("totalAmount") or {}
        flow_use = int(total_amount.get("used") or 0)
        flow_balance = int(total_amount.get("balance") or 0)
        flow_total = flow_use + flow_balance
        flow_over = int(total_amount.get("over") or 0)
        # 通用流量
        common_flow = flow_info.get("commonFlow") or {}
        common_use = int(common_flow.get("used") or 0)
        common_balance = int(common_flow.get("balance") or 0)
        common_total = common_use + common_balance
        common_over = int(common_flow.get("over") or 0)
        # 专用流量
        special_amount = flow_info.get("specialAmount") or {}
        special_use = int(special_amount.get("used") or 0)
        special_balance = int(special_amount.get("balance") or 0)
        special_total = special_use + special_balance

        # 语音通话
        voice_data_info = voice_info.get("voiceDataInfo") or {}
        voice_usage = int(voice_data_info.get("used") or 0)
        voice_balance = int(voice_data_info.get("balance") or 0)
        voice_total = int(voice_data_info.get("total") or 0)
        
        # 余额
        balance = int(
            float(data["balanceInfo"]["indexBalanceDataInfo"]["balance"] or 0) * 100
        )
        current_month_cost_str = data["balanceInfo"].get("phoneBillRegion", {}).get("subTitleHh", "0元").replace('元', '')
        try:
            current_month_cost = int(float(current_month_cost_str) * 100) # 转换为分
        except ValueError:
            current_month_cost = 0 # 转换失败则设为0
        
        # 积分
        points = int(integral_info.get("integral", 0) or 0)

        # ==========================
        # 流量包列表
        flowItems = []
        flow_lists = flow_info.get("flowList", [])
        for item in flow_lists:
            if "流量" not in item["title"]:
                continue
            # 常规流量
            if "已用" in item["leftTitle"] and "剩余" in item["rightTitle"]:
                item_use = self.convert_flow(item["leftTitleHh"], "KB")
                item_balance = self.convert_flow(item["rightTitleHh"], "KB")
                item_total = item_use + item_balance
            # 常规流量，超流量
            elif "超出" in item["leftTitle"] and "/" in item["rightTitleEnd"]:
                item_balance = -self.convert_flow(item["leftTitleHh"], "KB")
                item_use = (
                    self.convert_flow(item["rightTitleEnd"].split("/")[1], "KB")
                    - item_balance
                )
                item_total = item_use + item_balance
            # 无限流量，达量降速
            elif "已用" in item["leftTitle"] and "降速" in item["rightTitle"]:
                item_total = self.convert_flow(
                    re.search(r"(\d+[KMGT]B)", item["rightTitle"]).group(1), "KB"
                )
                item_use = self.convert_flow(item["leftTitleHh"], "KB")
                item_balance = item_total - item_use
            # 忽略其他不能识别的情形
            else:
                print(f"Ignore flow: {item}")
                continue
            flowItems.append(
                {
                    "name": item["title"],
                    "use": item_use,
                    "balance": item_balance,
                    "total": item_total,
                }
            )
        summary = {
            "phonenum": phonenum,
            "balance": balance,
            "currentMonthCost": current_month_cost, # 将本月消费添加到 summary
            "voiceUsage": voice_usage,
            "voiceBalance": voice_balance,
            "voiceTotal": voice_total,
            "flowUse": flow_use,
            "flowTotal": flow_total,
            "flowOver": flow_over,
            "commonUse": common_use,
            "commonTotal": common_total,
            "commonOver": common_over,
            "specialUse": special_use,
            "specialTotal": special_total,
            "points": points, 
            "createTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "flowItems": flowItems,
        }
        return summary

    def convert_flow(self, size_str, target_unit="KB", decimal=0):
        unit_dict = {"KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
        if not size_str:
            return 0
        if isinstance(size_str, str):
            size, unit = float(size_str[:-2]), size_str[-2:]
        elif isinstance(size_str, (int, float)):
            size, unit = size_str, "KB"
        if unit in unit_dict or target_unit in unit_dict:
            return (
                int(size * unit_dict[unit] / unit_dict[target_unit])
                if decimal == 0
                else round(size * unit_dict[unit] / unit_dict[target_unit], decimal)
            )
        else:
            raise ValueError("Invalid unit")
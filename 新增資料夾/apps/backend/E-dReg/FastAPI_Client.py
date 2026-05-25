import requests
import datetime
import logging
import os
import sys

# ==========================================
# 1. 設定 Log
# ==========================================
LOG_DIR = "/home/vboxuser/Downloads/fastAPIlog"
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("EdRegClient")
logger.setLevel(logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(LOG_DIR, f"edreg_client_{now_str}.log")

    file_handler = logging.FileHandler(log_filename, encoding="utf-8", mode="a")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

# ==========================================
# 2. 設定平台 API
# ==========================================
# 這裡要改成台電實際給你的 API URL
TPC_REPORT_URL = "https://YOUR_TPC_API_URL_HERE"

QSE_ID = 12345678
GROUP_ID = 1

def get_tpc_timestamp():
    tz = datetime.timezone(datetime.timedelta(hours=8))
    return datetime.datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S+08:00")

def build_payload(event_type: str):
    event = {}
    if event_type == "genStart":
        event["genStart"] = 1
    elif event_type == "genStop":
        event["genStop"] = 1
    else:
        raise ValueError(f"不支援的事件類型: {event_type}")

    return {
        "qseId": QSE_ID,
        "groupId": GROUP_ID,
        "timestamp": get_tpc_timestamp(),
        "event": event
    }

def report_event(event_type: str):
    payload = build_payload(event_type)

    logger.info(f"準備回報事件: {event_type}")
    logger.info(f"POST URL: {TPC_REPORT_URL}")
    logger.info(f"Payload: {payload}")

    try:
        response = requests.post(TPC_REPORT_URL, json=payload, timeout=10)
        response.raise_for_status()

        try:
            result = response.json()
        except Exception:
            result = response.text

        logger.info(f"回報成功，平台回應: {result}")
        return True, result

    except requests.exceptions.ConnectionError:
        logger.error("無法連線到台電平台 API")
        return False, "ConnectionError"
    except requests.exceptions.Timeout:
        logger.error("台電平台 API 回應逾時")
        return False, "Timeout"
    except requests.exceptions.RequestException as e:
        logger.error(f"回報失敗: {e}")
        return False, str(e)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python3 FastAPI_Client.py genStart")
        print("或:   python3 FastAPI_Client.py genStop")
        sys.exit(1)

    event_type = sys.argv[1]
    ok, result = report_event(event_type)
    print("success =", ok)
    print("result =", result)
import requests
import time
import datetime
import logging
import os

# ==========================================
# 1. 自定義日誌處理器：實現跨天自動換檔且檔名含日期
# ==========================================
class DailyFileHandler(logging.FileHandler):
    def __init__(self, directory, prefix):
        self.directory = directory
        self.prefix = prefix
        self.current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        log_path = os.path.join(self.directory, f"{self.prefix}_{self.current_date}.log")
        super().__init__(log_path, encoding="utf-8", mode="a")

    def emit(self, record):
        new_date = datetime.datetime.now().strftime("%Y-%m-%d")
        if new_date != self.current_date:
            self.current_date = new_date
            self.close()
            self.baseFilename = os.path.abspath(os.path.join(self.directory, f"{self.prefix}_{self.current_date}.log"))
            self._open()
        super().emit(record)

log_dir = "/home/vboxuser/Downloads/fastAPIlog"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logger = logging.getLogger("EdRegClient")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt="%Y-%m-%d %H:%M:%S")

file_handler = DailyFileHandler(log_dir, "edreg_client")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ==========================================
# 2. TPC 規格工具函數
# ==========================================
SERVER_URL = "http://127.0.0.1:8000/api/v1/edreg/callback"

def get_tpc_timestamp():
    # 生成對齊台電規格的 +08:00 ISO 格式時間
    tz = datetime.timezone(datetime.timedelta(hours=8))
    return datetime.datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S+08:00")

# ==========================================
# 3. 核心通訊循環 (含遞增重試邏輯)
# ==========================================
def send_request_loop():
    logger.info("Client 啟動，進入 E-dReg 規格通訊穩定性測試...")
    
    retry_delay = 2  # 初始重試等待秒數
    max_delay = 10   # 最大重試等待秒數

    while True:
        # 台電規格 Payload
        payload = {
            "qseId": 12345678,
            "groupId": 1,
            "timestamp": get_tpc_timestamp(),
            "event": {
                "genStart": 1 
            }
        }

        try:
            # 發送 POST 請求
            response = requests.post(SERVER_URL, json=payload, timeout=3)
            response.raise_for_status() 
            
            # 通訊成功：記錄成功訊息並恢復初始等待秒數
            logger.info(f"【成功】已回報。Server 回應: {response.json()}")
            retry_delay = 2  
            
            # 成功時的正常間隔時間 (例如每 2 秒發一次)
            time.sleep(2)

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            # 通訊失敗：記錄錯誤並執行遞增重試
            logger.error(f"【失敗】通訊異常: {type(e).__name__}。將於 {retry_delay} 秒後重試。")
            
            # 執行等待
            time.sleep(retry_delay)
            
            # 遞增等待時間: 2 -> 4 -> 6 -> 8 -> 10 (上限 10)
            retry_delay = min(retry_delay + 2, max_delay)
            
        except Exception as e:
            logger.error(f"【失敗】發生非預期錯誤: {e}")
            time.sleep(5) # 嚴重錯誤時固定等待 5 秒

if __name__ == "__main__":
    send_request_loop()
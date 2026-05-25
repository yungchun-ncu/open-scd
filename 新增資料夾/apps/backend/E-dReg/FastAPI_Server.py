from fastapi import FastAPI, Request
import datetime
import logging
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("EdRegServer")
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
    log_filename = os.path.join(LOG_DIR, f"edreg_server_{now_str}.log")

    file_handler = logging.FileHandler(log_filename, encoding="utf-8", mode="a")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

app = FastAPI(title="Local E-dREG API", version="1.0.0")


def get_tpc_timestamp():
    tz = datetime.timezone(datetime.timedelta(hours=8))
    return datetime.datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S+08:00")


@app.get("/")
def read_root():
    return {"message": "TPC E-dReg Server running"}


# 台電實際打進來的正式路徑
@app.post("/action/charge/ere")
async def receive_ere_charge(request: Request):
    body = await request.json()

    logger.info("========================================")
    logger.info("收到台電 ERE 充放電指令")
    logger.info("PATH: /action/charge/ere")
    logger.info(f"BODY: {body}")
    logger.info("========================================")

    return {
        "status": 0,
        "timestamp": get_tpc_timestamp()
    }


# 保留原本測試路徑
@app.post("/api/v1/edreg/callback")
async def receive_edreg_callback(request: Request):
    body = await request.json()

    logger.info("========================================")
    logger.info("收到台電 callback（測試路徑）")
    logger.info("PATH: /api/v1/edreg/callback")
    logger.info(f"BODY: {body}")
    logger.info("========================================")

    return {
        "status": 0,
        "timestamp": get_tpc_timestamp()
    }


# 根路徑 POST
@app.post("/")
async def receive_root_callback(request: Request):
    raw = await request.body()

    logger.info("========================================")
    logger.info("收到台電 callback（根路徑 /）")
    logger.info("PATH: /")
    logger.info(f"BODY: {raw.decode('utf-8', errors='ignore')}")
    logger.info("========================================")

    return {
        "status": 0,
        "timestamp": get_tpc_timestamp()
    }


# 除錯用：接所有未知路徑
@app.post("/{full_path:path}")
async def catch_all_post(full_path: str, request: Request):
    raw = await request.body()

    logger.info("========================================")
    logger.info("收到未知路徑 callback")
    logger.info(f"PATH: /{full_path}")
    logger.info(f"BODY: {raw.decode('utf-8', errors='ignore')}")
    logger.info("========================================")

    return {
        "status": 0,
        "timestamp": get_tpc_timestamp(),
        "path": f"/{full_path}"
    }
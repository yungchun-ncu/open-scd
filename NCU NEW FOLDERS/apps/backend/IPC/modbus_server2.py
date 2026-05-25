import time
import threading
import logging

from pyModbusTCP.server import ModbusServer, DataBank

# =========================================================
# Logging 設定
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# =========================================================
# 基本設定
# =========================================================
MODBUS_HOST = "0.0.0.0"
MODBUS_PORT = 1502

# 建立一個 DataBank 實例
db = DataBank()

# =========================================================
# 與 client 對應的 table 位址
# =========================================================
SERVICE = {
    "report_ts": 40150,      # 40150(H), 40151(L)
    "event_status": 40152,
    "sched_power": 40153,    # 40153(H), 40154(L)
    "sbspm": 40155,
    "inst_power": 40156,     # 40156(H), 40157(L)
    "freq": 40158,
    "update_ts": 40159,      # 40159(H), 40160(L)
}

EMERGENCY = {
    "start_ts": 40180,       # 40180(H), 40181(L)
    "power": 40182,          # 40182(H), 40183(L)
    "duration_min": 40184,
    "end_ts": 40186,         # 40186(H), 40187(L)
    "update_ts": 40188,      # 40188(H), 40189(L)
    "status_p": 40199,
    "status_q": 40200,
}

EVEN_BID = {
    "timestamp": 42000,      # 42000(H), 42001(L)
    "first_bid": 42002,      # 單筆 16-bit，連續 96 筆
    "count": 96,
}

EVEN_SCHEDULE = {
    "timestamp": 42200,      # 42200(H), 42201(L)
    "first_power": 42202,    # 每筆 int32，連續 96 筆，每筆佔 2 reg
    "count": 96,
}

hr_lock = threading.Lock()

# =========================================================
# 工具函數
# =========================================================
def split_u32(value: int):
    value &= 0xFFFFFFFF
    return (value >> 16) & 0xFFFF, value & 0xFFFF


def split_i32(value: int):
    value &= 0xFFFFFFFF
    return (value >> 16) & 0xFFFF, value & 0xFFFF


def merge_u32(high: int, low: int) -> int:
    return ((high & 0xFFFF) << 16) | (low & 0xFFFF)


def merge_i32(high: int, low: int) -> int:
    unsigned_value = ((high & 0xFFFF) << 16) | (low & 0xFFFF)
    if unsigned_value & 0x80000000:
        return unsigned_value - 0x100000000
    return unsigned_value


def set_u16(addr: int, value: int):
    # 直接寫單一 holding register
    ok = db.set_holding_registers(addr, [value & 0xFFFF])
    if not ok:
        raise RuntimeError(f"set_u16 失敗, addr={addr}, value={value}")


def get_u16(addr: int) -> int:
    vals = db.get_holding_registers(addr, 1)
    if not vals:
        return 0
    return vals[0]


def set_u32(addr: int, value: int):
    hi, lo = split_u32(value)
    ok = db.set_holding_registers(addr, [hi, lo])
    if not ok:
        raise RuntimeError(f"set_u32 失敗, addr={addr}, value={value}")


def get_u32(addr: int) -> int:
    vals = db.get_holding_registers(addr, 2)
    if not vals or len(vals) != 2:
        return 0
    return merge_u32(vals[0], vals[1])


def set_i32(addr: int, value: int):
    hi, lo = split_i32(value)
    ok = db.set_holding_registers(addr, [hi, lo])
    if not ok:
        raise RuntimeError(f"set_i32 失敗, addr={addr}, value={value}")


def get_i32(addr: int) -> int:
    vals = db.get_holding_registers(addr, 2)
    if not vals or len(vals) != 2:
        return 0
    return merge_i32(vals[0], vals[1])


def now_unix() -> int:
    return int(time.time())


# =========================================================
# 初始化 table
# =========================================================
def init_table_values():
    with hr_lock:
        ts = now_unix()

        # 服務計算
        set_u32(SERVICE["report_ts"], ts)
        set_u16(SERVICE["event_status"], 0)
        set_i32(SERVICE["sched_power"], 1000)
        set_u16(SERVICE["sbspm"], 9500)      # 95.00%
        set_i32(SERVICE["inst_power"], 980)
        set_u16(SERVICE["freq"], 6000)       # 60.00Hz
        set_u32(SERVICE["update_ts"], ts)

        # 緊急調度
        start_ts = ts
        duration = 5
        set_u32(EMERGENCY["start_ts"], start_ts)
        set_i32(EMERGENCY["power"], 1000)    # 1.000 MW(raw)
        set_u16(EMERGENCY["duration_min"], duration)
        set_u32(EMERGENCY["end_ts"], start_ts + duration * 60)
        set_u32(EMERGENCY["update_ts"], start_ts)
        set_u16(EMERGENCY["status_p"], 0)
        set_u16(EMERGENCY["status_q"], 0)

        # 偶數日得標資訊
        set_u32(EVEN_BID["timestamp"], ts)
        for i in range(EVEN_BID["count"]):
            set_u16(EVEN_BID["first_bid"] + i, 10000 + i)

        # 偶數日排程功率資訊
        set_u32(EVEN_SCHEDULE["timestamp"], ts)
        for i in range(EVEN_SCHEDULE["count"]):
            set_i32(EVEN_SCHEDULE["first_power"] + i * 2, 1000 + i)

    logger.info("Modbus table initialized.")


# =========================================================
# 背景更新執行緒
# =========================================================
def update_dynamic_values():
    iteration = 0
    while True:
        iteration += 1

        with hr_lock:
            ts = now_unix()

            # 服務計算區
            set_u32(SERVICE["report_ts"], ts)
            set_u16(SERVICE["event_status"], iteration % 6)
            set_i32(SERVICE["sched_power"], 1000 + iteration)
            set_u16(SERVICE["sbspm"], 9500 + (iteration % 200))
            set_i32(SERVICE["inst_power"], 990 + iteration)
            set_u16(SERVICE["freq"], 6000 + (iteration % 20))
            set_u32(SERVICE["update_ts"], ts)

            # 緊急調度區
            start_ts = ts
            duration = 5 + (iteration % 10)
            set_u32(EMERGENCY["start_ts"], start_ts)
            set_i32(EMERGENCY["power"], 1000 + iteration)
            set_u16(EMERGENCY["duration_min"], duration)
            set_u32(EMERGENCY["end_ts"], start_ts + duration * 60)
            set_u32(EMERGENCY["update_ts"], start_ts)
            set_u16(EMERGENCY["status_p"], iteration % 10)
            set_u16(EMERGENCY["status_q"], iteration % 10)

            # 偶數日得標資訊
            set_u32(EVEN_BID["timestamp"], ts)
            for i in range(EVEN_BID["count"]):
                set_u16(EVEN_BID["first_bid"] + i, 10000 + iteration + i)

            # 偶數日排程功率資訊
            set_u32(EVEN_SCHEDULE["timestamp"], ts)
            for i in range(EVEN_SCHEDULE["count"]):
                set_i32(EVEN_SCHEDULE["first_power"] + i * 2, 1000 + iteration + i)

        logger.info(
            "Dynamic values updated | service_ts=%d event=%d freq=%.2fHz emg_power=%.3fMW",
            get_u32(SERVICE["report_ts"]),
            get_u16(SERVICE["event_status"]),
            get_u16(SERVICE["freq"]) / 100.0,
            get_i32(EMERGENCY["power"]) / 1000.0,
        )

        time.sleep(2)


def heartbeat_log():
    while True:
        with hr_lock:
            logger.info(
                "Heartbeat | report_ts=%d status=%d sched=%dW bid00=%d sch00=%d",
                get_u32(SERVICE["report_ts"]),
                get_u16(SERVICE["event_status"]),
                get_i32(SERVICE["sched_power"]),
                get_u16(EVEN_BID["first_bid"]),
                get_i32(EVEN_SCHEDULE["first_power"]),
            )
        time.sleep(10)


def start_background_threads():
    for target, name in [
        (update_dynamic_values, "UpdateDynamicValues"),
        (heartbeat_log, "HeartbeatLog"),
    ]:
        t = threading.Thread(target=target, name=name, daemon=True)
        t.start()
        logger.info("Thread '%s' started.", name)


# =========================================================
# 主程式
# =========================================================
def main():
    logger.info("Starting Modbus TCP Server on %s:%d", MODBUS_HOST, MODBUS_PORT)

    init_table_values()
    start_background_threads()

    server = ModbusServer(
        host=MODBUS_HOST,
        port=MODBUS_PORT,
        no_block=False,
        data_bank=db,
    )
    server.start()


if __name__ == "__main__":
    main()
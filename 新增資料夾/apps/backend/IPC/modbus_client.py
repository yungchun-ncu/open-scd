from pyModbusTCP.client import ModbusClient
import time
import datetime
import json
import requests
import asyncio
import websockets


# =========================================================
# 基本設定
# =========================================================
HOST = "127.0.0.1"
PORT = 1502
UNIT_ID = 1

DEVICE_ID = "IPC001"

# VM 位址請改成你的 VM IP
VM_IP = "192.168.0.161"

# 傳輸模式: "http" 或 "ws"
TRANSPORT_MODE = "http"

API_URL = f"http://{VM_IP}:8000/upload"
WS_URL = f"ws://{VM_IP}:8000/ws"

ADDRESS_BIAS = 0


def reg(dec_addr: int) -> int:
    return dec_addr + ADDRESS_BIAS


# =========================================================
# Modbus Client
# =========================================================
c = ModbusClient(
    host=HOST,
    port=PORT,
    unit_id=UNIT_ID,
    auto_open=True,
    auto_close=False,
    timeout=3,
)


# =========================================================
# 工具函數
# =========================================================
def split_u32(value: int):
    value &= 0xFFFFFFFF
    return (value >> 16) & 0xFFFF, value & 0xFFFF


def merge_u32(high: int, low: int) -> int:
    return ((high & 0xFFFF) << 16) | (low & 0xFFFF)


def split_i32(value: int):
    value &= 0xFFFFFFFF
    return (value >> 16) & 0xFFFF, value & 0xFFFF


def merge_i32(high: int, low: int) -> int:
    unsigned_value = ((high & 0xFFFF) << 16) | (low & 0xFFFF)
    if unsigned_value & 0x80000000:
        return unsigned_value - 0x100000000
    return unsigned_value


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat()


def safe_open():
    if not c.is_open:
        return c.open()
    return True


# =========================================================
# 讀取工具
# =========================================================
def read_u16(addr_dec: int):
    data = c.read_holding_registers(reg(addr_dec), 1)
    if not data:
        return None
    return data[0]


def read_u32(addr_high_dec: int):
    data = c.read_holding_registers(reg(addr_high_dec), 2)
    if not data or len(data) != 2:
        return None
    return merge_u32(data[0], data[1])


def read_i32(addr_high_dec: int):
    data = c.read_holding_registers(reg(addr_high_dec), 2)
    if not data or len(data) != 2:
        return None
    return merge_i32(data[0], data[1])


# =========================================================
# Table 對應地址
# =========================================================
SERVICE = {
    "report_ts": 40150,
    "event_status": 40152,
    "sched_power": 40153,
    "sbspm": 40155,
    "inst_power": 40156,
    "freq": 40158,
    "update_ts": 40159,
}

EMERGENCY = {
    "start_ts": 40180,
    "power": 40182,
    "duration_min": 40184,
    "end_ts": 40186,
    "update_ts": 40188,
    "status_p": 40199,
    "status_q": 40200,
}

EVEN_BID = {
    "timestamp": 42000,
    "first_bid": 42002,
    "count": 96,
}

EVEN_SCHEDULE = {
    "timestamp": 42200,
    "first_power": 42202,
    "count": 96,
}


# =========================================================
# 資料整理
# =========================================================
def get_service_dict():
    report_ts = read_u32(SERVICE["report_ts"])
    event_status = read_u16(SERVICE["event_status"])
    sched_power = read_i32(SERVICE["sched_power"])
    inst_power = read_i32(SERVICE["inst_power"])
    freq_raw = read_u16(SERVICE["freq"])
    sbspm = read_u16(SERVICE["sbspm"])
    update_ts = read_u32(SERVICE["update_ts"])

    return {
        "report_ts": report_ts,
        "update_ts": update_ts,
        "event_status": event_status,
        "sched_power_w": sched_power,
        "inst_power_w": inst_power,
        "freq_hz": None if freq_raw is None else freq_raw / 100.0,
        "execution_rate": None if sbspm is None else sbspm / 100.0
    }


def get_emergency_dict():
    start_ts = read_u32(EMERGENCY["start_ts"])
    end_ts = read_u32(EMERGENCY["end_ts"])
    update_ts = read_u32(EMERGENCY["update_ts"])
    power_raw = read_i32(EMERGENCY["power"])
    duration = read_u16(EMERGENCY["duration_min"])
    status_p = read_u16(EMERGENCY["status_p"])
    status_q = read_u16(EMERGENCY["status_q"])

    return {
        "start_ts": start_ts,
        "end_ts": end_ts,
        "update_ts": update_ts,
        "power_mw": None if power_raw is None else power_raw / 1000.0,
        "duration_min": duration,
        "status_p": status_p,
        "status_q": status_q
    }


def get_even_bid_list(points: int = 8):
    result = []
    bid_ts = read_u32(EVEN_BID["timestamp"])

    for i in range(points):
        addr = EVEN_BID["first_bid"] + i
        value = read_u16(addr)
        result.append({
            "index": i,
            "timestamp": bid_ts,
            "bid_value_raw": value,
            "bid_value_mw": None if value is None else value / 100.0
        })
    return result


def get_even_schedule_list(points: int = 8):
    result = []
    sched_ts = read_u32(EVEN_SCHEDULE["timestamp"])

    for i in range(points):
        addr = EVEN_SCHEDULE["first_power"] + i * 2
        value = read_i32(addr)
        result.append({
            "index": i,
            "timestamp": sched_ts,
            "power_raw": value,
            "power_mw": None if value is None else value / 1000.0
        })
    return result


def build_payload():
    return {
        "device_id": DEVICE_ID,
        "timestamp": now_iso(),
        "service": get_service_dict(),
        "emergency": get_emergency_dict(),
        "bid_schedule": get_even_bid_list(points=8),
        "power_schedule": get_even_schedule_list(points=8),
    }


# =========================================================
# 傳送
# =========================================================
def send_to_api(payload):
    try:
        response = requests.post(API_URL, json=payload, timeout=5)
        print(f"[HTTP] status_code={response.status_code}, response={response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"[HTTP] 傳送失敗: {e}")
        return False


async def send_to_ws_once(payload):
    try:
        async with websockets.connect(WS_URL) as ws:
            msg = json.dumps(payload, ensure_ascii=False)
            await ws.send(msg)
            reply = await ws.recv()
            print(f"[WS] server reply: {reply}")
            return True
    except Exception as e:
        print(f"[WS] 傳送失敗: {e}")
        return False


def send_payload(payload):
    if TRANSPORT_MODE == "http":
        return send_to_api(payload)
    elif TRANSPORT_MODE == "ws":
        return asyncio.run(send_to_ws_once(payload))
    else:
        print(f"[錯誤] 不支援的傳輸模式: {TRANSPORT_MODE}")
        return False


# =========================================================
# 主循環
# =========================================================
def main():
    print("=== Modbus 資料讀取與傳輸開始 ===")
    print(f"Host={HOST}, Port={PORT}, AddressBias={ADDRESS_BIAS}")
    print(f"TRANSPORT_MODE={TRANSPORT_MODE}")
    print(f"API_URL={API_URL}")
    print(f"WS_URL={WS_URL}")
    print("按 Ctrl+C 可停止測試\n")

    retry_delay = 2
    max_retry_delay = 10
    iteration = 0

    try:
        while True:
            iteration += 1
            print(f"\n######## 第 {iteration} 輪 ########")

            if not safe_open():
                print(f"[{iteration}] Modbus 連線失敗，{retry_delay} 秒後重試...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay + 2, max_retry_delay)
                continue

            try:
                payload = build_payload()
                print("\n=== Payload(JSON) ===")
                print(json.dumps(payload, indent=2, ensure_ascii=False))

                send_ok = send_payload(payload)

                if send_ok:
                    print("[成功] 已送出資料")
                else:
                    print("[失敗] 資料傳送失敗")

                retry_delay = 2
                time.sleep(2)

            except Exception as e:
                print(f"[{iteration}] 執行過程發生錯誤: {e}")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay + 2, max_retry_delay)

    except KeyboardInterrupt:
        print("\n使用者手動停止測試。")

    finally:
        c.close()
        print("連線已關閉，測試結束。")


if __name__ == "__main__":
    main()
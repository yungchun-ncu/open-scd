from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import datetime
import json

app = FastAPI(title="Unified Receiver")

SAVE_FILE = "received_data.jsonl"


def now_iso():
    return datetime.datetime.now().astimezone().isoformat()


def save_record(protocol: str, data):
    record = {
        "received_at": now_iso(),
        "protocol": protocol,
        "data": data
    }

    print("\n========== 收到資料 ==========")
    print(json.dumps(record, indent=2, ensure_ascii=False))
    print("================================\n")

    with open(SAVE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Unified Receiver is running",
        "timestamp": now_iso()
    }


@app.post("/upload")
async def upload(request: Request):
    try:
        data = await request.json()
        save_record("http", data)

        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "message": "HTTP data received",
                "timestamp": now_iso()
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": now_iso()
            }
        )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket client 已連線")
    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            save_record("websocket", data)
            await websocket.send_text("ok")
    except WebSocketDisconnect:
        print("WebSocket client 已斷線")
    except Exception as e:
        print(f"WebSocket 錯誤: {e}")
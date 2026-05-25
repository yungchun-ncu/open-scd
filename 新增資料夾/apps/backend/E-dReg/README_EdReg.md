# 台電 E-dReg 測試平台 API 串接說明

本專案用於串接 **台電 E-dReg 測試平台 API**，目前主要功能是建立我方 Callback Server，讓台電平台可以主動發送 ERE 充放電指令到我方系統，同時我方也可以主動呼叫台電 API 回報 DI 狀態與查詢充放電排程。

目前已確認完成核心雙向通訊流程：

```text
台電平台 → 我方 FastAPI Server
我方系統 → 台電平台 API
```

---

## 1. 目前系統狀態

### 已完成項目

目前已完成以下功能：

1. Callback Server 已架設完成
2. 使用 FastAPI 建立 API Server
3. Server 部署於數位通 VM 的 Docker Container（iec61850_ssh_container_test_1）
4. Docker port mapping 已修正為 8086:8086
5. FastAPI 已改成使用 port 8086 啟動
6. Callback URL 已成功註冊至台電平台
7. 台電平台可成功發送 ERE 指令到我方 Server
8. 我方 Server 可成功接收 `/action/charge/ere` callback
9. DI 狀態回報 API 測試成功
10. 充放電排程查詢 API 測試成功

---

## 2. 系統環境資訊

| 項目 | 目前設定 |
|---|---|
| Server Framework | FastAPI |
| 部署環境 |數位通 VM 的 Docker Container（iec61850_ssh_container_test_1） |
| VM VPN IP | `172.18.6.170` |
| 對外服務 Port | `8086` |
| Callback URL | `http://172.18.6.170:8086` |
| FastAPI App 檔案 | `FastAPI_Server_Test2.py` |
| Uvicorn 啟動 Port | `8086` |

---

## 3. Docker Port Mapping

目前 Docker port mapping 設定如下：

```yaml
ports:
  - "8086:8086"
```

目前台電 Callback URL 使用：

```text
http://172.18.6.170:8086
```

因此 container 內的 FastAPI 服務與 VM 對外 port 都需要對應到 `8086`。

---

## 4. 啟動 FastAPI Server

在 Docker container 內，使用以下指令啟動 Server：

```bash
python3 -m uvicorn FastAPI_Server_Test2:app --host 0.0.0.0 --port 8086
```

參數說明：

| 參數 | 說明 |
|---|---|
| `FastAPI_Server_Test2:app` | 指定 FastAPI app 物件所在檔案與變數名稱 |
| `--host 0.0.0.0` | 允許外部主機連線進來 |
| `--port 8086` | 使用 8086 port 對外提供服務 |

啟動成功後，可以先在 VM 或 container 內測試：

```bash
curl http://127.0.0.1:8086
```

若服務正常，會回傳類似：

```json
{
  "message": "TPC E-dReg Server running"
}
```

也可以從可連到 VPN 的環境測試：

```bash
curl http://172.18.6.170:8086
```

---

## 5. 我方 FastAPI Server API 路徑

### 5.1 根路徑測試

```http
GET /
```

用途：確認 Server 是否有正常啟動。

回傳範例：

```json
{
  "message": "TPC E-dReg Server running"
}
```

---

### 5.2 台電正式 ERE 充放電指令 Callback 路徑

```http
POST /action/charge/ere
```

這是目前台電平台實際會打進來的正式路徑。

Server 端程式目前已新增：

```python
@app.post("/action/charge/ere")
async def receive_ere_charge(request: Request):
    body = await request.json()
    return {
        "status": 0,
        "timestamp": get_tpc_timestamp()
    }
```

台電平台發送 ERE 指令時，我方 Server 已確認可收到以下內容：

```json
{
  "qseId": 83181512,
  "groupId": 90004,
  "genValue": 2.6,
  "holdTime": 5
}
```

我方 Server 回傳格式：

```json
{
  "status": 0,
  "timestamp": "2026-04-29T23:45:00+08:00"
}
```

欄位說明：

| 欄位 | 說明 |
|---|---|
| `status` | 回傳狀態，`0` 表示成功 |
| `timestamp` | 我方 Server 回傳時間，格式為 `YYYY-MM-DDTHH:mm:ss+08:00` |

---

### 5.3 原本保留的測試 Callback 路徑

```http
POST /api/v1/edreg/callback
```

用途：保留給本地測試或 curl 測試使用。

測試範例：

```bash
curl -X POST http://127.0.0.1:8086/api/v1/edreg/callback \
  -H "Content-Type: application/json" \
  -d '{
    "qseId": 83181512,
    "groupId": 90004,
    "test": "callback test"
  }'
```

---

### 5.4 根路徑 POST

```http
POST /
```

用途：若外部系統誤打到根路徑 `/`，Server 仍會記錄 request body 並回傳成功。

---

### 5.5 未知路徑 Catch-all

```http
POST /{full_path:path}
```

用途：除錯用。

若台電平台或其他系統打到非預期路徑，Server 會把實際收到的 path 與 body 記錄到 log，方便確認對方到底打到哪一個 API 路徑。

---

## 6. Callback 註冊狀態

Callback 已成功註冊到台電測試平台。

### 註冊 API

```text
/as/api/callback/register/ere
```

### 註冊資訊

| 欄位 | 值 |
|---|---|
| `qseId` | `83181512` |
| `groupId` | `90004` |
| Callback URL | `http://172.18.6.170:8086` |

### 台電回傳結果

```json
{
  "msg": "success",
  "status": 0
}
```

代表台電平台已接受並儲存我方 Callback URL。

---

## 7. 台電平台發送 ERE 指令測試

目前已確認：

```text
台電平台可以成功打到我方 FastAPI Server
```

Server 收到的路徑為：

```http
POST /action/charge/ere
```

收到的內容範例：

```json
{
  "qseId": 83181512,
  "groupId": 90004,
  "genValue": 2.6,
  "holdTime": 5
}
```

欄位說明：

| 欄位 | 說明 |
|---|---|
| `qseId` | 聚合商或業者識別代碼 |
| `groupId` | 資源群組代碼 |
| `genValue` | 台電要求的充放電功率值 |
| `holdTime` | 指令維持時間 |

目前測試結果：

```text
台電平台 → 我方 Server 的 Callback 流程成功
```

---

## 8. DI 狀態回報 API

我方系統可主動呼叫台電 API，回報 ERE 狀態。

### API URL

```text
http://10.21.77.39/as/api/reply/ere
```

### 用途

主動回報給台電目前的 DI 狀態，例如：

```json
{
  "event": {
    "genStart": 1
  }
}
```

或：

```json
{
  "event": {
    "genStop": 1
  }
}
```

### Payload 範例：genStart

```json
{
  "qseId": 83181512,
  "groupId": 90004,
  "timestamp": "2026-04-29T23:45:00+08:00",
  "event": {
    "genStart": 1
  }
}
```

### Payload 範例：genStop

```json
{
  "qseId": 83181512,
  "groupId": 90004,
  "timestamp": "2026-04-29T23:50:00+08:00",
  "event": {
    "genStop": 1
  }
}
```

目前測試結果：

```text
台電 API 回傳 success，且平台查得到回報紀錄
```

---

## 9. 充放電排程查詢 API

我方系統可主動呼叫台電 API，查詢當日 ERE 充放電排程。

### API URL

```text
http://10.21.77.39/as/api/charge/current/ere
```

### Payload

```json
{
  "qseId": 83181512,
  "groupId": 90004
}
```

目前台電會回傳大量排程資料，內容包含：

| 欄位 | 說明 |
|---|---|
| `timestamp` | 排程時間 |
| `genValue` | 該時間點的充放電功率值 |
| `soc` | 電池或資源目前 SOC 狀態 |

目前測試結果：

```text
充放電排程查詢 API 測試成功
```

---

## 10. 目前已確認流程

目前整體流程如下：

```text
1. 台電平台發送 ERE 指令
        ↓
2. 我方 FastAPI Server 接收 Callback
        ↓
3. 我方系統依照指令執行或模擬充放電狀態
        ↓
4. 我方系統主動回報 genStart / genStop 給台電
        ↓
5. 我方系統主動查詢當日充放電排程
```

目前已成功完成：

- E-dReg API 串接
- Callback 接收
- DI 狀態回報
- ERE 指令流程驗證
- 排程查詢 API 測試

---

## 11. Log 紀錄

Server 會自動建立 `logs/` 資料夾，並將收到的 callback 內容寫入 log 檔案。

Log 檔案命名格式：

```text
logs/edreg_server_YYYYMMDD_HHMMSS.log
```

例如：

```text
logs/edreg_server_20260429_234500.log
```

若台電有發送 ERE 指令，log 中會看到類似內容：

```text
========================================
收到台電 ERE 充放電指令
PATH: /action/charge/ere
BODY: {'qseId': 83181512, 'groupId': 90004, 'genValue': 2.6, 'holdTime': 5}
========================================
```

若要在 container 內即時查看 log，可使用：

```bash
tail -f logs/edreg_server_*.log
```

---

## 12. curl 測試方式

### 測試根路徑

```bash
curl http://172.18.6.170:8086
```

### 測試正式 ERE Callback 路徑

```bash
curl -X POST http://172.18.6.170:8086/action/charge/ere \
  -H "Content-Type: application/json" \
  -d '{
    "qseId": 83181512,
    "groupId": 90004,
    "genValue": 2.6,
    "holdTime": 5
  }'
```

### 測試原本保留的 callback 路徑

```bash
curl -X POST http://172.18.6.170:8086/api/v1/edreg/callback \
  -H "Content-Type: application/json" \
  -d '{
    "qseId": 83181512,
    "groupId": 90004,
    "test": "callback test"
  }'
```

---

## 13. 注意事項

1. 目前不是所有台電平台按鈕都會打到我方 Server。
2. 目前已確認會 callback 到我方 Server 的功能是：

```text
API 平台發送指令測試
```

3. AO / DO、排程查詢等功能，多半是台電平台內部操作，或需要我方主動呼叫台電 API。
4. 因此，按下某些平台按鈕後，若我方 Server 沒有收到 callback，不一定代表 Server 有問題。
5. 若要確認台電是否真的有打進來，應優先查看 FastAPI terminal log 或 `logs/` 內的紀錄。
6. 如果更換 port，Docker port mapping、FastAPI 啟動 port、Callback 註冊 URL 三者都要同步修改。

---

## 14. 目前進度總結

目前專案狀態可以整理為：

```text
台電 E-dReg API 雙向通訊核心流程已成功
```

也就是：

```text
台電 → 我方 FastAPI Server：成功
我方 → 台電平台 API：成功
```

目前已完成的重點包含：

- Callback Server 架設完成
- Callback URL 註冊成功
- 台電 ERE 指令可成功打到我方 `/action/charge/ere`
- 我方可成功回傳 `status: 0` 與 timestamp
- 我方可主動回報 `genStart` / `genStop`
- 我方可主動查詢當日 ERE 充放電排程


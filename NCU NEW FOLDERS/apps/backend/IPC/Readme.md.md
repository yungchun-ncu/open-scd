# IPC → VM → MongoDB → Node-RED 操作指令整理

## 0. 系統目的

本文件整理目前測試平台的主要操作指令，供後續部署、測試與展示使用。

目前完整流程：

```text
IPC Modbus Server
    ↓ Modbus TCP
IPC Modbus Client
    ↓ HTTP POST /upload
VM FastAPI Receiver Container
    ↓ Store JSON Document
VM MongoDB Container
    ↓ Query / Read Data
Node-RED Container
    ↓ WebSocket / Dashboard Node
Web Dashboard GUI

---

# 一、VM 端 Docker Compose 操作

## 1. 進入 VM 專案資料夾

```bash
cd ~/ipc_vm_receiver
```

---

## 2. 查看專案結構

```bash
tree
```

或：

```bash
find . -maxdepth 3
```

目前資料夾結構：

```text
ipc_vm_receiver/
├── docker-compose.yml
├── .env
├── receiver/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── unified_receiver.py
├── logs/
│   └── receiver/
├── data/
│   └── mongodb/
└── nodered/
    └── data/
```

---

## 3. 啟動所有 container

```bash
docker-compose up -d --build
```

目前會啟動三個 container：

```text
ipc_receiver   # FastAPI Receiver
ipc_mongodb    # MongoDB
ipc_nodered    # Node-RED
```

---

## 4. 查看 container 狀態

```bash
docker ps
```

正常應看到：

```text
ipc_receiver
ipc_mongodb
ipc_nodered
```

---

## 5. 停止所有 container

```bash
docker-compose down
```

---

## 6. 重新啟動所有 container

```bash
docker-compose up -d
```

如果有修改程式或 Dockerfile：

```bash
docker-compose up -d --build
```

---

## 7. 只重啟 receiver

```bash
docker restart ipc_receiver
```

---

## 8. 查看 receiver log

```bash
docker logs -f ipc_receiver
```

離開 log 畫面：

```text
Ctrl + C
```

---

## 9. 查看 MongoDB log

```bash
docker logs -f ipc_mongodb
```

---

## 10. 查看 Node-RED log

```bash
docker logs -f ipc_nodered
```

---

# 二、Receiver 測試指令

## 1. 測試 Receiver 是否啟動

```bash
curl http://localhost:8000/
```

正常回應範例：

```json
{
  "status": "ok",
  "message": "Unified Receiver is running",
  "mongodb": "enabled",
  "timestamp": "..."
}
```

---

## 2. 手動送測試資料到 receiver

```bash
curl -X POST http://localhost:8000/upload -H "Content-Type: application/json" -d '{"device_id":"IPC001","test":"write to mongodb"}'
```

正常回應範例：

```json
{
  "status": "ok",
  "message": "HTTP data received",
  "mongodb_inserted_id": "...",
  "timestamp": "..."
}
```

若有 `mongodb_inserted_id`，代表資料已成功寫入 MongoDB。

---

## 3. 查看 receiver 外部 jsonl log

```bash
cat logs/receiver/received_data.jsonl
```

查看最後幾筆：

```bash
tail -n 5 logs/receiver/received_data.jsonl
```

---

# 三、MongoDB 操作指令

## 1. 進入 MongoDB shell(進入正在執行中的 MongoDB container)

```bash
docker exec -it ipc_mongodb mongosh -u admin -p 123456
```

---

## 2. 切換到資料庫

```javascript
use ipc_data
```

---

## 3. 查看 collections

```javascript
show collections
```

正常應看到：

```text
receiver_logs
```

---

## 4. 查詢最新一筆資料

```javascript
db.receiver_logs.find().sort({_id:-1}).limit(1).pretty()
```

---

## 5. 查詢最新三筆資料

```javascript
db.receiver_logs.find().sort({_id:-1}).limit(3).pretty()
```

---

## 6. 確認資料欄位

資料中應包含：

```text
received_at
protocol
data.device_id
data.service
data.emergency
data.bid_schedule
data.power_schedule
```

---

## 7. 離開 MongoDB shell

```javascript
exit
```

或：

```text
Ctrl + D
```

---

# 四、IPC 端操作指令

## 1. SSH 進入 IPC

```bash
ssh nculab@192.168.0.247 -p 2222
```

---

## 2. 查看 IPC 端檔案

```bash
ls
```

目前主要檔案：

```text
modbus_server2.py
modbus_client3.py
```

---

## 3. 啟動 Modbus Server

在 IPC terminal 執行：

```bash
python3 modbus_server2.py
```

正常會看到：

```text
Dynamic values updated
Heartbeat
```

代表 Modbus server 持續更新 register 資料。

---

## 4. 啟動 Modbus Client

另開一個 IPC terminal，再次 SSH 進 IPC：

```bash
ssh nculab@192.168.0.247 -p 2222
```

執行：

```bash
python3 modbus_client3.py
```

正常會看到：

```text
[HTTP] status_code=200
[成功] 已送出資料
```

若 response 中包含：

```text
mongodb_inserted_id
```

代表資料已成功送到 VM receiver 並寫入 MongoDB。

---

## 5. 離開 IPC

```bash
exit
```

---

# 五、IPC 連線到 VM 測試

若 IPC 沒有 curl，可用 Python 測試 VM receiver 是否可連線。

將 `192.168.0.161` 改成實際 VM IP：

```bash
python3 -c "import urllib.request; print(urllib.request.urlopen('http://192.168.0.161:8000/').read().decode())"
```

若成功，會看到 receiver 回應：

```json
{"status":"ok","message":"Unified Receiver is running",...}
```

---

# 六、Node-RED 操作

## 1. 開啟 Node-RED 編輯頁

在 VM 瀏覽器開啟：

```text
http://localhost:1880
```

若從其他電腦開啟：

```text
http://VM_IP:1880
```

---

## 2. 開啟 Dashboard 頁面

```text
http://localhost:1880/dashboard/page1
```

若從其他電腦開啟：

```text
http://VM_IP:1880/dashboard/page1
```

---

## 3. Node-RED 目前流程

```text
timestamp
    ↓
Set MongoDB query
    ↓
Read receiver logs
    ↓
Extract latest data
    ↓
各 Dashboard 元件
```

---

## 4. MongoDB Node 連線設定

```text
Host: mongodb
Port: 27017
Database: ipc_data
Username: admin
Password: 123456
Collection: receiver_logs
Operation: find
```

若認證失敗，可在 connect options 加上：

```text
authSource=admin
```

---

## 5. Dashboard 目前顯示內容

```text
Latest Status:
顯示 device_id 與最新資料時間

Frequency:
顯示 service.freq_hz，單位 Hz

Emergency Power:
顯示 emergency.power_mw，單位 MW

Instant Power Trend:
顯示 service.inst_power_w 的趨勢圖，單位 W

System Status:
顯示 service.event_status、emergency.status_p、emergency.status_q

Schedule Status:
顯示 bid_schedule 與 power_schedule 筆數
```

---

# 七、常見問題處理

## 1. docker-compose 出現 ContainerConfig 錯誤

若出現：

```text
KeyError: 'ContainerConfig'
```

可刪除舊 container 後重新建立：

```bash
docker stop ipc_receiver
docker rm ipc_receiver
docker-compose up -d --build
```

若仍失敗：

```bash
docker-compose down
docker-compose up -d --build
```

---

## 2. Docker 指令跑到遠端 IPC

若 Docker context 指到遠端：

```bash
docker context ls
```

切回本機：

```bash
docker context use default
unset DOCKER_HOST
```

---

## 3. Docker Hub DNS 解析錯誤

若出現：

```text
lookup registry-1.docker.io on 127.0.0.53:53: server misbehaving
```

修改 DNS：

```bash
sudo nano /etc/systemd/resolved.conf
```

設定：

```ini
[Resolve]
DNS=8.8.8.8 1.1.1.1
FallbackDNS=8.8.4.4 1.0.0.1
DNSStubListener=yes
```

重啟：

```bash
sudo systemctl restart systemd-resolved
sudo systemctl restart docker
```

測試：

```bash
ping registry-1.docker.io
```

---

## 4. IPC 沒有 nano / vi

若 IPC container 裡沒有 nano 或 vi，可用 `sed` 直接修改。

例如修改 `inst_power` 循環變化：

```bash
sed -i 's/set_i32(SERVICE\["inst_power"\], 990 + iteration)/set_i32(SERVICE["inst_power"], 1100 + (iteration % 50))/g' modbus_server2.py
```

檢查：

```bash
grep -n 'set_i32(SERVICE\["inst_power"\]' modbus_server2.py
```

例如修改 emergency power 成上下波動：

```bash
sed -i 's/set_i32(EMERGENCY\["power"\], 1000 + (iteration % 500))/set_i32(EMERGENCY["power"], 1200 + abs((iteration % 20) - 10) * 10)/g' modbus_server2.py
```

檢查：

```bash
grep -n 'set_i32(EMERGENCY\["power"\]' modbus_server2.py
```

---

# 八、完整驗證流程

## 1. VM 啟動服務

```bash
cd ~/ipc_vm_receiver
docker-compose up -d --build
docker ps
```

確認有：

```text
ipc_receiver
ipc_mongodb
ipc_nodered
```

---

## 2. IPC 啟動 Modbus Server

```bash
ssh nculab@192.168.0.247 -p 2222
python3 modbus_server2.py
```

---

## 3. IPC 啟動 Modbus Client

另開 IPC terminal：

```bash
ssh nculab@192.168.0.247 -p 2222
python3 modbus_client3.py
```

確認：

```text
[HTTP] status_code=200
[成功] 已送出資料
```

---

## 4. VM 查看 receiver log

```bash
docker logs -f ipc_receiver
```

應看到：

```text
POST /upload HTTP/1.1 200 OK
========== 收到資料 ==========
```

---

## 5. VM 查 MongoDB

```bash
docker exec -it ipc_mongodb mongosh -u admin -p 123456
```

```javascript
use ipc_data
db.receiver_logs.find().sort({_id:-1}).limit(1).pretty()
```

應看到：

```text
device_id: IPC001
service
emergency
bid_schedule
power_schedule
```

---

## 6. 開啟 Node-RED Dashboard

```text
http://localhost:1880/dashboard/page1
```

確認 Dashboard 顯示：

```text
Frequency
Emergency Power
Instant Power Trend
Latest Status
System Status
Schedule Status
```

---

# 九、一鍵啟動說明

目前 VM 端已可透過以下指令一鍵啟動：

```bash
docker-compose up -d --build
```

此指令會啟動：

```text
ipc_receiver
ipc_mongodb
ipc_nodered
```

IPC 端目前仍需手動啟動：

```bash
python3 modbus_server2.py
python3 modbus_client3.py
```

後續若要達成完整平台一鍵啟動，可再將 Modbus server/client 也整理成 Docker service。

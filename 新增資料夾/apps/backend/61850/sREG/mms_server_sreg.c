#include "iec61850_server.h"
#include "iec61850_model.h"
#include "hal_thread.h"
#include "hal_time.h"
#include "mms_value.h"
#include "static_model.h"

#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>

static int running = 1;

static void
sigint_handler(int signalId)
{
    running = 0;
}

/* 透過 IEC 61850 object reference 找資料點 */
static DataAttribute*
lookupDataAttribute(const char* ref)
{
    ModelNode* node = IedModel_getModelNodeByObjectReference(&iedModel, ref);

    if (node == NULL) {
        printf("[WARN] DataAttribute not found: %s\n", ref);
        return NULL;
    }

    return (DataAttribute*) node;
}

/* 更新 INT32 欄位 */
static void
updateInt32(IedServer server, const char* ref, int32_t value)
{
    DataAttribute* da = lookupDataAttribute(ref);

    if (da != NULL) {
        IedServer_updateInt32AttributeValue(server, da, value);
    }
}

/* 有些 LN instance 可能是 01，有些工具顯示成 1，所以這裡做兩種名稱嘗試 */
static void
updateInt32Try2(IedServer server, const char* ref1, const char* ref2, int32_t value)
{
    ModelNode* node = IedModel_getModelNodeByObjectReference(&iedModel, ref1);

    if (node == NULL)
        node = IedModel_getModelNodeByObjectReference(&iedModel, ref2);

    if (node == NULL) {
        printf("[WARN] DataAttribute not found: %s or %s\n", ref1, ref2);
        return;
    }

    IedServer_updateInt32AttributeValue(server, (DataAttribute*) node, value);
}

/* 更新 INT64 欄位 */
static void
updateInt64(IedServer server, const char* ref, int64_t value)
{
    DataAttribute* da = lookupDataAttribute(ref);

    if (da != NULL) {
        IedServer_updateInt64AttributeValue(server, da, value);
    }
}

/* 更新 BOOLEAN 欄位 */
static void
updateBoolean(IedServer server, const char* ref, bool value)
{
    DataAttribute* da = lookupDataAttribute(ref);

    if (da != NULL) {
        IedServer_updateBooleanAttributeValue(server, da, value);
    }
}

/* 更新時間戳記 */
static void
updateTimestamp(IedServer server, const char* ref)
{
    DataAttribute* da = lookupDataAttribute(ref);

    if (da != NULL) {
        IedServer_updateUTCTimeAttributeValue(server, da, Hal_getTimeInMs());
    }
}

/* 控制命令 callback：台電平台下 AO / DO control 時會進到這裡 */
static ControlHandlerResult
controlHandler(ControlAction action, void* parameter, MmsValue* value, bool test)
{
    const char* pointName = (const char*) parameter;

    printf("[CONTROL] point = %s, test = %s\n",
           pointName,
           test ? "true" : "false");

    if (value == NULL) {
        printf("[CONTROL] value is NULL\n");
        return CONTROL_RESULT_FAILED;
    }

    if (MmsValue_getType(value) == MMS_BOOLEAN) {
        bool ctlVal = MmsValue_getBoolean(value);
        printf("[CONTROL] boolean ctlVal = %s\n", ctlVal ? "true" : "false");
    }
    else if (MmsValue_getType(value) == MMS_INTEGER) {
        int32_t ctlVal = MmsValue_toInt32(value);
        printf("[CONTROL] integer ctlVal = %d\n", ctlVal);
    }
    else if (MmsValue_getType(value) == MMS_STRUCTURE) {
        printf("[CONTROL] structured value received\n");

        int elementCount = MmsValue_getArraySize(value);

        for (int i = 0; i < elementCount; i++) {
            MmsValue* element = MmsValue_getElement(value, i);

            if (element == NULL)
                continue;

            if (MmsValue_getType(element) == MMS_INTEGER) {
                int32_t ctlVal = MmsValue_toInt32(element);
                printf("[CONTROL] structure element[%d] integer = %d\n", i, ctlVal);
            }
            else if (MmsValue_getType(element) == MMS_BOOLEAN) {
                bool ctlVal = MmsValue_getBoolean(element);
                printf("[CONTROL] structure element[%d] boolean = %s\n",
                       i,
                       ctlVal ? "true" : "false");
            }
            else {
                printf("[CONTROL] structure element[%d] type = %d\n",
                       i,
                       MmsValue_getType(element));
            }
        }
    }
    else {
        printf("[CONTROL] unsupported control value type = %d\n", MmsValue_getType(value));
    }

    return CONTROL_RESULT_OK;
}

/* 設定 control handler */
static void
setupControlHandler(IedServer server, const char* objectRef, const char* pointName)
{
    ModelNode* node = IedModel_getModelNodeByObjectReference(&iedModel, objectRef);

    if (node == NULL) {
        printf("[WARN] Control object not found: %s\n", objectRef);
        return;
    }

    IedServer_setControlHandler(
        server,
        (DataObject*) node,
        controlHandler,
        (void*) pointName
    );

    printf("[INFO] Control handler registered: %s\n", objectRef);
}

/* 更新交易資源 ASR00001 的 sReg 資料點 */
static void
updateResourceData(IedServer server)
{
    /*
     * sReg Resource 資料：
     * ASR00001/SREMMXUxx
     * ASR00001/SREDBATxx
     * ASR00001/SREGGIOxx
     *
     * 數值倍率先依測試用途放模擬值。
     * 文件中常用 0.01 單位，所以例如 59.99 Hz 可用 5999 表示。
     */

    for (int i = 1; i <= 10; i++) {
        char ref1[128];
        char ref2[128];

        int32_t freqHz_x100 = 5999;              /* 59.99 Hz */
        int32_t totalPower_001kW = 2566 + i;     /* 25.66 kW */
        int32_t voltage_001kV = 1131 + i;        /* 11.31 kV */
        int32_t current_001A = 1131 + i;         /* 11.31 A */
        int32_t soc_001kWh = 2500 + i;           /* 25.00 kWh */

        int64_t nowSec = (int64_t) Hal_getTimeInMs() / 1000;
        int32_t tsHigh = (int32_t) ((uint64_t) nowSec >> 32);
        int32_t tsLow  = (int32_t) ((uint64_t) nowSec & 0xffffffff);

        /* SREMMXUxx.Hz.mag.i */
        snprintf(ref1, sizeof(ref1), "ASR00001/SREMMXU%02d.Hz.mag.i", i);
        snprintf(ref2, sizeof(ref2), "ASR00001/SREMMXU%d.Hz.mag.i", i);
        updateInt32Try2(server, ref1, ref2, freqHz_x100);

        /* SREMMXUxx.TotW.mag.i */
        snprintf(ref1, sizeof(ref1), "ASR00001/SREMMXU%02d.TotW.mag.i", i);
        snprintf(ref2, sizeof(ref2), "ASR00001/SREMMXU%d.TotW.mag.i", i);
        updateInt32Try2(server, ref1, ref2, totalPower_001kW);

        /* 三相電壓 PhV.phsA/B/C.cVal.mag.i */
        snprintf(ref1, sizeof(ref1), "ASR00001/SREMMXU%02d.PhV.phsA.cVal.mag.i", i);
        snprintf(ref2, sizeof(ref2), "ASR00001/SREMMXU%d.PhV.phsA.cVal.mag.i", i);
        updateInt32Try2(server, ref1, ref2, voltage_001kV);

        snprintf(ref1, sizeof(ref1), "ASR00001/SREMMXU%02d.PhV.phsB.cVal.mag.i", i);
        snprintf(ref2, sizeof(ref2), "ASR00001/SREMMXU%d.PhV.phsB.cVal.mag.i", i);
        updateInt32Try2(server, ref1, ref2, voltage_001kV + 1);

        snprintf(ref1, sizeof(ref1), "ASR00001/SREMMXU%02d.PhV.phsC.cVal.mag.i", i);
        snprintf(ref2, sizeof(ref2), "ASR00001/SREMMXU%d.PhV.phsC.cVal.mag.i", i);
        updateInt32Try2(server, ref1, ref2, voltage_001kV + 2);

        /* 三相電流 A.phsA/B/C.cVal.mag.i */
        snprintf(ref1, sizeof(ref1), "ASR00001/SREMMXU%02d.A.phsA.cVal.mag.i", i);
        snprintf(ref2, sizeof(ref2), "ASR00001/SREMMXU%d.A.phsA.cVal.mag.i", i);
        updateInt32Try2(server, ref1, ref2, current_001A);

        snprintf(ref1, sizeof(ref1), "ASR00001/SREMMXU%02d.A.phsB.cVal.mag.i", i);
        snprintf(ref2, sizeof(ref2), "ASR00001/SREMMXU%d.A.phsB.cVal.mag.i", i);
        updateInt32Try2(server, ref1, ref2, current_001A + 1);

        snprintf(ref1, sizeof(ref1), "ASR00001/SREMMXU%02d.A.phsC.cVal.mag.i", i);
        snprintf(ref2, sizeof(ref2), "ASR00001/SREMMXU%d.A.phsC.cVal.mag.i", i);
        updateInt32Try2(server, ref1, ref2, current_001A + 2);

        /* SREDBATxx.InBatV.mag.i */
        snprintf(ref1, sizeof(ref1), "ASR00001/SREDBAT%02d.InBatV.mag.i", i);
        snprintf(ref2, sizeof(ref2), "ASR00001/SREDBAT%d.InBatV.mag.i", i);
        updateInt32Try2(server, ref1, ref2, soc_001kWh);

        /* SREDBATxx.BatSt.stVal：false 表示無異常 */
        snprintf(ref1, sizeof(ref1), "ASR00001/SREDBAT%02d.BatSt.stVal", i);
        snprintf(ref2, sizeof(ref2), "ASR00001/SREDBAT%d.BatSt.stVal", i);

        ModelNode* batNode = IedModel_getModelNodeByObjectReference(&iedModel, ref1);
        if (batNode == NULL)
            batNode = IedModel_getModelNodeByObjectReference(&iedModel, ref2);

        if (batNode != NULL)
            IedServer_updateBooleanAttributeValue(server, (DataAttribute*) batNode, false);

        /* SREGGIOxx.AnIn1 / AnIn2：Unix Timestamp H/L */
        snprintf(ref1, sizeof(ref1), "ASR00001/SREGGIO%02d.AnIn1.mag.i", i);
        snprintf(ref2, sizeof(ref2), "ASR00001/SREGGIO%d.AnIn1.mag.i", i);
        updateInt32Try2(server, ref1, ref2, tsHigh);

        snprintf(ref1, sizeof(ref1), "ASR00001/SREGGIO%02d.AnIn2.mag.i", i);
        snprintf(ref2, sizeof(ref2), "ASR00001/SREGGIO%d.AnIn2.mag.i", i);
        updateInt32Try2(server, ref1, ref2, tsLow);
    }
}

/* 更新報價代碼 ASG90004 的 Group 資料點 */
static void
updateGroupData(IedServer server)
{
    /*
     * ASG90004：
     * G = 報價代碼層級
     * 90004 = 目前台電平台測試畫面選到的報價代碼
     */

    int32_t qseId = 8311512;     /* 台電平台畫面顯示的合格交易者 */
    int32_t groupId = 90004;     /* 報價代碼 */
    int32_t serviceType = 3;     /* sReg = 3 */

    updateInt32(server, "ASG90004/QSEGGIO01.IntIn1.stVal", qseId);
    updateInt32(server, "ASG90004/QSEGGIO01.IntIn2.stVal", groupId);
    updateInt32(server, "ASG90004/QSEGGIO01.IntIn3.stVal", serviceType);

    for (int i = 1; i <= 10; i++) {
        char ref1[128];
        char ref2[128];

        int32_t groupPower_001kW = 2566 + i;

        int64_t nowSec = (int64_t) Hal_getTimeInMs() / 1000;
        int32_t tsHigh = (int32_t) ((uint64_t) nowSec >> 32);
        int32_t tsLow  = (int32_t) ((uint64_t) nowSec & 0xffffffff);

        /* GROMMXUxx.TotW.mag.i */
        snprintf(ref1, sizeof(ref1), "ASG90004/GROMMXU%02d.TotW.mag.i", i);
        snprintf(ref2, sizeof(ref2), "ASG90004/GROMMXU%d.TotW.mag.i", i);
        updateInt32Try2(server, ref1, ref2, groupPower_001kW);

        /* GROGGIOxx.AnIn1 / AnIn2：Unix Timestamp H/L */
        snprintf(ref1, sizeof(ref1), "ASG90004/GROGGIO%02d.AnIn1.mag.i", i);
        snprintf(ref2, sizeof(ref2), "ASG90004/GROGGIO%d.AnIn1.mag.i", i);
        updateInt32Try2(server, ref1, ref2, tsHigh);

        snprintf(ref1, sizeof(ref1), "ASG90004/GROGGIO%02d.AnIn2.mag.i", i);
        snprintf(ref2, sizeof(ref2), "ASG90004/GROGGIO%d.AnIn2.mag.i", i);
        updateInt32Try2(server, ref1, ref2, tsLow);
    }

    /* 報價代碼聚合之所有交易資源加總瞬時累計發電量 / 用電量 */
    updateInt64(server, "ASG90004/GROMMTR01.SupWh.actVal", 0);
    updateInt64(server, "ASG90004/GROMMTR01.DmdWh.actVal", 0);

    /* 執行率計算時間點與執行率 */
    int64_t nowSec = (int64_t) Hal_getTimeInMs() / 1000;
    int32_t tsHigh = (int32_t) ((uint64_t) nowSec >> 32);
    int32_t tsLow  = (int32_t) ((uint64_t) nowSec & 0xffffffff);

    updateInt32(server, "ASG90004/GROGGIO11.AnIn1.mag.i", tsHigh);
    updateInt32(server, "ASG90004/GROGGIO11.AnIn2.mag.i", tsLow);
    updateInt32(server, "ASG90004/GROGGIO11.AnIn3.mag.i", 0);

    /* sReg DI 回覆狀態點位：預設 false */
    updateBoolean(server, "ASG90004/SREGGIO01.Ind1.stVal", false);
    updateBoolean(server, "ASG90004/SREGGIO02.Ind1.stVal", false);
    updateBoolean(server, "ASG90004/SREGGIO03.Ind1.stVal", false);
}

int
main(int argc, char** argv)
{
    int tcpPort = 102;

    if (argc > 1)
        tcpPort = atoi(argv[1]);

    printf("Starting IEC 61850 MMS Server with TPC SREG ICD model ASG90004...\n");

    IedServer iedServer = IedServer_create(&iedModel);

    signal(SIGINT, sigint_handler);

    /*
     * DO：平台發送 sReg 狀態指令
     * 文件對應：
     * ASG90004/SREGAPC01.SPCSO1.Oper.ctlVal
     * ASG90004/SREGAPC02.SPCSO1.Oper.ctlVal
     */
    setupControlHandler(iedServer, "ASG90004/SREGAPC01.SPCSO1", "SREGAPC01.SPCSO1");
    setupControlHandler(iedServer, "ASG90004/SREGAPC02.SPCSO1", "SREGAPC02.SPCSO1");

    /*
     * AO：平台發送 sReg 頻率移動目標值 / 時間
     * Wireshark 已看到平台先讀：
     * ASG90004/SREGGIO01$CF$AnOut1$ctlModel
     * ASG90004/SREGGIO02$CF$AnOut2$ctlModel
     *
     * 所以這裡註冊：
     * ASG90004/SREGGIO01.AnOut1
     * ASG90004/SREGGIO02.AnOut1
     * ASG90004/SREGGIO02.AnOut2
     */
    setupControlHandler(iedServer, "ASG90004/SREGGIO01.AnOut1", "SREGGIO01.AnOut1");
    setupControlHandler(iedServer, "ASG90004/SREGGIO02.AnOut1", "SREGGIO02.AnOut1");
    setupControlHandler(iedServer, "ASG90004/SREGGIO02.AnOut2", "SREGGIO02.AnOut2");

    IedServer_start(iedServer, tcpPort);

    if (!IedServer_isRunning(iedServer)) {
        printf("Starting server failed! Check if TCP port %i is already used or needs sudo.\n", tcpPort);
        IedServer_destroy(iedServer);
        return -1;
    }

    printf("MMS Server started on TCP port %i.\n", tcpPort);
    printf("Updating TPC SREG ASG90004 ICD data values every 1 second.\n");
    printf("Press Ctrl+C to stop.\n");

    int counter = 0;

    while (running) {
        updateResourceData(iedServer);
        updateGroupData(iedServer);

        counter++;

        if (counter % 5 == 0) {
            printf("[INFO] data updated. counter = %d\n", counter);
        }

        Thread_sleep(1000);
    }

    IedServer_stop(iedServer);
    IedServer_destroy(iedServer);

    printf("MMS Server stopped.\n");

    return 0;
}
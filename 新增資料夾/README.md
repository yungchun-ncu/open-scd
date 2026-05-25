---
title: Github branches

---

# NCU STAR ETP

智慧能源交易平台

## 專案架構
```text
ncu-star-etp/ (Root)          # 專案名稱
├── .github/                   # GitHub 專用配置
│   ├── workflows/             # CI/CD 自動化腳本 (如：自動弱掃、部署)
│   ├── ISSUE_TEMPLATE/        # 規範團隊回報 Bug 或新功能的格式
│   └── PULL_REQUEST_TEMPLATE.md #  確保工程師合併代碼前有檢查過規範
├── apps/                          # 應用程式區
│   ├── frontend/              # React + Redux-toolkit (監控介面)
│   └── backend/               # Python (API, 權限管理), (61850 cid file,c source code... )
├── packages/                      # 共用模組區 (Monorepo 核心)
│   ├── shared-types/          # 前後端共用 TypeScript 定義 (台電 API 格式)
│   └── iec61850-core/         # 獨立的 61850 通訊處理模組 (核心邏輯) ok
├── docs/                      # 專案文件庫
│   ├── specifications/        # 技術規範書 (Word/PDF)
│   └── user-manuals/          # 使用者操作手冊
├── CHANGELOG .md               # 版本變更紀錄
├── README .md                  # 專案總覽與啟動說明
├── docker-compose.yml         # 一鍵部署正式環境配置
└── docker-compose-dev.yml         # 一鍵部署開發環境配置

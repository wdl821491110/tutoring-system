# Spec: 小程序 P0/P1 Bug 修复 + 短期功能补齐

> 基准：`小程序审计报告.md` (2026-06-13)  
> 范围：仅 P0+P1 Bug + 5 项短期缺失功能，不含中期/长期

---

## Objective

修复导致运行时崩溃的 3 个 P0 Bug 和 4 个 P1 逻辑缺陷，补齐 5 项 PC 端已有但小程序缺失的高频功能。目标：小程序核心流程（签到消课、排课管理、数据浏览）与 PC 端功能一致、无崩溃。

### User Stories

- 作为教师，在排课页签到消课时不应崩溃，且能正确收到成功/失败反馈
- 作为教师，能在排课列表批量选择课程并一键签到
- 作为管理员，能在排课页编辑已有排课（改时间/课程）
- 作为管理员，能在课时记录页撤销误操作
- 作为任何用户，小程序启动时自动校验 token 有效性，过期跳登录
- 作为任何用户，小程序长时间闲置后自动退出

### Success Criteria

| # | 条件 | 验证方式 |
|---|------|---------|
| SC1 | `_submitRecord` 不抛出 ReferenceError | 真机签到消课 |
| SC2 | `_addNote` 成功/失败 toast 与实际 API 结果一致 | 添加备注后验证 |
| SC3 | `showAdd` 无孤立 merge 残留代码 | 代码审查 |
| SC4 | 启动时调用 `/api/auth/me` 校验 token，无效跳登录 | 用过期 token 启动 |
| SC5 | 5 分钟无操作后自动登出 | 闲置 5 分钟后操作 |
| SC6 | 空备注不允许提交 | 输入空格后点提交 |
| SC7 | 学生表单校验与 PC 端一致 | 对比两端表单必填项 |
| SC8 | 排课编辑功能可用：修改时间/学生/课程并保存 | 真机编辑排课 |
| SC9 | 批量签到：多选排课 → 一键签到 → 状态批量更新 | 真机批量签到 |
| SC10 | 撤销消课：点击撤销 → 课时恢复 → 记录状态变更 | 真机撤销 |

---

## Tech Stack

- 微信小程序原生框架（WXML / WXSS / JS）
- WeUI 扩展库（`useExtendedLib.weui: true`）
- 云托管内网通道：`wx.cloud.callContainer()`
- 工具函数：`utils/request.js`、`utils/auth.js`、`utils/validator.js`
- 自定义组件：`components/form-sheet/form-sheet`

---

## Commands

| 用途 | 命令 |
|------|------|
| 本地调试 | 微信开发者工具 → 打开项目 `miniprogram/` → 编译 |
| 真机预览 | 开发者工具 → 预览 → 扫码 |
| 真机调试 | 开发者工具 → 真机调试 → 扫码 |
| 上传代码 | 开发者工具 → 上传（版本号按日期） |
| PC 端启动 | `python run.py`（本地验证 API） |

---

## Project Structure

```
miniprogram/
├── app.js                          # 全局状态、onLaunch
├── app.json                        # 页面注册、TabBar、WeUI扩展
├── app.wxss                        # 全局样式
├── pages/
│   ├── index/index.*               # 首页 Dashboard
│   ├── students/students.*         # 学生管理
│   ├── schedules/schedules.*       # 排课管理 ← 本次重点修改
│   ├── records/records.*           # 课时记录 ← 本次重点修改
│   ├── profile/profile.*           # 个人中心
│   ├── login/login.*               # 登录
│   └── privacy/privacy.*           # 隐私政策
├── components/
│   └── form-sheet/form-sheet.*     # 底部表单组件
└── utils/
    ├── request.js                  # 网络请求 ← 本次修改
    ├── auth.js                     # 认证管理  ← 本次修改
    ├── validator.js                # 表单校验  ← 本次修改
    ├── initializer.js              # 启动初始化
    └── pinyin.js                   # 拼音工具
```

---

## Code Style

沿用项目现有风格，关键规范：

```javascript
// API 调用 - 三端统一方式
app.api('/api/records', { method: 'POST', body: JSON.stringify(payload) })
  .then((res) => {
    if (res.code === 200) {
      wx.showToast({ title: res.message || '成功', icon: 'success' });
      this.load(1, true);
    } else {
      wx.showToast({ title: res.message || '失败', icon: 'none' });
    }
  });

// 表单提交状态管理
this.setData({ submitting: true });
// ... API call ...
this.setData({ submitting: false });
```

### 必须遵守
- **Toast 只在 API 返回后调用**，不可在 `.then()` 之前
- 所有 `throw` 之前先 `toast()`（`request.js` 已处理 401/非200，页面只需处理 `catch`）
- 使用 `setData` 原子更新，避免多次调用
- 表单复用 `form-sheet` 组件，不重复造底部弹窗

---

## Testing Strategy

| 层级 | 方式 | 覆盖 |
|------|------|------|
| 本地开发者工具 | 手动页面操作 | 所有修改页面的正常/异常路径 |
| 真机验收 | 扫码测试 | SC1-SC10 全部 |
| 代码审查 | diff 检查 | 确保无 merge 残留、死代码 |

**不引入自动化测试框架。** 微信小程序测试环境搭建成本高于收益。

---

## Boundaries

### Always do
- 修复 Bug 时先读文件确认当前内容再修改
- 每次修改后通过开发者工具编译验证无语法错误
- Toast/Failure 反馈先于任何 throw
- 遵循 WeUI 组件规范，不自造轮子
- 每完成一个 Bug/功能即记录到 `YYYY-MM-DD.md`

### Ask first
- 新增 npm 依赖
- 修改 `app.json` 页面注册
- 修改后端 API 接口
- 涉及数据库 schema 变更

### Never do
- 在 API 返回前显示 toast
- 删除或修改 PC 端代码
- 留下注释掉的死代码
- 跳过 token 校验直接展示数据

---

## 修复清单

### 阶段 1：P0 Bug ✅ — 已完成

| ID | 文件:行号 | 问题 | 修复 | 状态 |
|----|----------|------|------|------|
| **B1** | `records.js:140` | `showAdd()` 中有孤立表达式 | 删除该行 | ✅ |
| **B2** | `records.js:207` | `_submitRecord` toast 在 API 前 | 移入 `.then()` | ✅ |
| **B3** | `records.js:263` | `_addNote` toast 在 API 前 | 移入 `.then()` | ✅ |

### 阶段 2：P1 Bug ✅ — 已完成

| ID | 文件 | 问题 | 修复 | 状态 |
|----|------|------|------|------|
| **B4** | `auth.js` + `app.js` | 启动不校验 token | 调 `/api/auth/permissions` 静默校验 | ✅ |
| **B5** | `app.js` + `request.js` | 无空闲超时 | 30s 间隔检测 + API 调用更新活动时间 | ✅ |
| **B6** | `records.js:_addNote` | 空内容可提交 | `if (!content) return toast` | ✅ |
| **B7** | `validator.js` + `students.wxml` | 仅 name 校验 | 增加 `parent_phone` 格式 + WXML 错误态 | ✅ |

### 阶段 3：短期缺失功能（5 项）

| ID | 页面 | 功能 | API 端点 |
|----|------|------|---------|
| **F1** | schedules | 排课编辑（修改时间/学生/课程） | `PUT /api/schedules/:id` |
| **F2** | schedules | 批量签到（checkbox+全选+一键签到） | `POST /api/records/batch-checkin` |
| **F3** | records | 撤销消课 | `POST /api/records/:id/undo` |
| **F4** | records | 直接消课（不依赖排课签到） | `POST /api/records` |
| **F5** | records | 删除备注 | `DELETE /api/records/:id/notes/:nid` |

---

## Implementation Plan

### 依赖关系图

```
Stage 1 · P0             Stage 2 · P1              Stage 3 · Features
─────────────────────    ─────────────────────     ─────────────────────
records.js (B1,B2,B3)    auth.js (B4)              schedules.js (F1,F2)
      │                   app.js (B4,B5)            records.js (F3,F4,F5)
      │                   records.js (B6)
  独立，可并行          students.js (B7)
                          validator.js (B7)
                          ─────────────────────
                          B4→B5 同文件顺序
                          B6 + B7 独立并行
```

- **Stage 1** 完成后即可验证崩溃修复
- **Stage 2** 依赖 Stage 1 完成后的 records.js
- **Stage 3** 依赖 Stage 2 完成后的 auth/app 基础设施

### 风险

| 风险 | 缓解 |
|------|------|
| `/api/auth/me` 不存在 | 先用 `GET /api/auth/permissions` 代替，调通即可 |
| `batch-checkin` body 格式未知 | 先读 PC 端 `static/js/app.js` 确认 |
| 空闲定时器误触发（API 调用中） | 网络请求时重置定时器 |
| records.js 多次修改冲突 | Stage 3 在 Stage 1/2 全部完成后进行 |

---

## Tasks

### Stage 1 · P0 Bug

- [ ] **T1** 清理 merge 残留 (B1)
  - 文件：`records.js` ~L140
  - 修改：删除 `showAdd()` 中孤立表达式行
  - 验证：开发者工具编译无语法警告

- [ ] **T2** 修复 `_submitRecord` toast 时机 (B2)
  - 文件：`records.js` ~L200-210
  - 修改：删除 API 调用前的 `wx.showToast`，在 `.then()` 内放置 toast
  - 验证：真机签到消课，成功时 toast 出现 + 不报 ReferenceError

- [ ] **T3** 修复 `_addNote` toast 时机 (B3)
  - 文件：`records.js` ~L263
  - 修改：删除 API 调用前的 `wx.showToast`，仅在 `.then()` 内展示
  - 验证：真机添加备注，成功/失败 toast 与实际一致

### Stage 2 · P1 Bug

- [ ] **T4** Token 启动校验 (B4)
  - 文件：`auth.js` 新增 `validateToken()`，`app.js` `onLaunch` 调用
  - 修改：`validateToken()` 调 `/api/auth/permissions`，失败则 `clearAuth()` + 跳登录
  - 验证：用过期 token 启动 → 自动跳登录页

- [ ] **T5** 空闲超时 (B5)
  - 文件：`app.js` `onLaunch`
  - 修改：全局 `wx.onTouchStart` 监听 → 5min timer → 到期 `logout()` + `reLaunch login`
  - 验证：闲置 5 分钟后点按钮 → 跳登录页

- [ ] **T6** 空备注校验 (B6)
  - 文件：`records.js` `_addNote()`
  - 修改：`if (!content) return wx.showToast({ title: '请输入内容', icon: 'none' })`
  - 验证：输入纯空格点提交 → 提示"请输入内容"

- [ ] **T7** 学生表单校验对齐 (B7)
  - 文件：`validator.js` + `students.js`
  - 修改：`student` 校验增加 `parent_phone` 格式（1xx-xxxx-xxxx）
  - 验证：输入非法手机号 → 保存时提示

### Stage 3 · 短期功能

- [ ] **T8** 排课编辑 (F1)
  - 文件：`schedules.js` + `schedules.wxml`
  - 修改：slideview 增加"编辑"按钮 → 复用 form-sheet 弹出 → `PUT /api/schedules/:id`
  - 验证：编辑排课时间 → 保存 → 列表刷新且数据更新

- [ ] **T9** 批量签到 (F2)
  - 文件：`schedules.js` + `schedules.wxml`
  - 修改：工具栏增加"批量签到" → 进入多选模式（checkbox+全选）→ `POST /api/records/batch-checkin`
  - 验证：选 3 条排课签到 → 全部变为 completed

- [ ] **T10** 撤销消课 (F3)
  - 文件：`records.js` + `records.wxml`
  - 修改：记录行增加"撤销"按钮 → `POST /api/records/:id/undo`
  - 验证：撤销一条记录 → 列表刷新 → 学生课时恢复

- [ ] **T11** 直接消课 (F4)
  - 文件：`records.js` + `records.wxml`
  - 修改：工具栏增加"消课"按钮 → form-sheet 弹出 → 选择学生/课程/课时 → `POST /api/records`
  - 验证：直接消课 → 记录出现在列表 → 剩余课时扣减

- [ ] **T12** 删除备注 (F5)
  - 文件：`records.js` + `records.wxml`
  - 修改：备注弹窗内每条备注加删除按钮 → `DELETE /api/records/:id/notes/:nid`
  - 验证：删除备注 → 列表刷新 → 备注消失

---

## Verification Checkpoints

| Checkpoint | 阶段完成后 | 方式 |
|-----------|-----------|------|
| CP1 | Stage 1 | 开发者工具编译 + `_submitRecord` 手动测试 |
| CP2 | Stage 2 | 重启小程序 token 过期测试 + 闲置测试 |
| CP3 | Stage 3 | 全部 SC1-SC10 真机验收 |

---

## Open Questions

无——基于审计报告已明确所有问题。

---

## Review Checklist

- [x] 用户已确认 spec 范围（P0+P1+5短期）
- [x] 用户已确认执行顺序（Bug先行 → 功能后补）
- [x] 用户已确认不需要中期功能（教师/课程/报名管理）加入本次
- [ ] 用户确认 Plan + Tasks → 进入 Implement

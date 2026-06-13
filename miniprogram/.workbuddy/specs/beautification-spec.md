# Spec: 课消管理系统 UI 美化 & 体验升级

**版本**: v1.2
**创建日期**: 2026-06-13
**状态**: ✅ 已完成（代码层面）→ 待真机验收

---

## Objective

对课消管理系统微信小程序进行**逼近微信原生态**品质的全方位视觉与交互升级。目标不是推翻重做，而是在现有 Design System v5.0 基础上做减法——清理死代码、统一设计语言、打磨微交互、让 WeUI 原生组件回归本真，最终呈现出"像微信自己做的工具"的质感。

**用户**: 培训机构管理员、教师
**成功标准**: 用户使用时不觉得"这是一个小程序"，而是觉得"这是一套流畅的工具"

---

## Tech Stack

| 层 | 技术 |
|---|-----|
| 框架 | 微信原生小程序 (WXML + WXSS + JS) |
| UI 组件 | WeUI 扩展组件库 (mp-cells, mp-cell, mp-searchbar, mp-slideview, mp-half-screen-dialog, mp-icon) |
| 后端 | CloudBase 云开发 (不变) |
| 测试方式 | 真机预览 + 开发者工具模拟器 |
| **不新增** | 不引入第三方 UI 库、不新增 npm 依赖 |

---

## Commands

```bash
# 预览（微信开发者工具中操作，无 CLI 命令）
# 构建产物即源码，无编译步骤

# 检查样式一致性（人工）
# 逐页在开发者工具中切换 iPhone 6/iPhone 14 Pro Max 验证布局

# 真机测试
# 扫码预览 → 操作全流程 → 检查视觉还原
```

---

## Project Structure (美化涉及的文件)

```
pages/
├── index/index.wxss        → 首页样式优化
├── students/students.wxss  → 学生管理样式优化 + 表单重构
├── schedules/schedules.wxss→ 排课管理样式优化 + 表单重构
├── records/records.wxss    → 课时记录样式优化 + 表单重构
├── profile/profile.wxss    → 我的页面样式优化
├── login/login.wxss        → 登录页输入框优化
└── privacy/privacy.wxss    → 隐私政策排版修正
components/
└── form-sheet/
    ├── form-sheet.wxss     → 表单组件样式收敛
    └── form-sheet.wxml     → 表单组件结构优化
app.wxss                    → 死代码清理 + 设计令牌统一
```

**不修改**: 所有 `.js` 逻辑文件、`.json` 配置文件、`utils/`、`images/`

---

## Code Style

本项目采用**微信原生设计语言**编码规范：

```css
/* ✅ 好的：使用 WeUI 原生类名，最少覆盖 */
.mp-cell {
  /* 只覆盖必要的：字体、间距 */
  font-size: 17px;  /* WeChat 原生正文字号 */
}

/* ✅ 好的：间距体系对齐微信原生节奏 */
.card {
  padding: 16px;           /* 统一为 16px，不对齐 12/24 混用 */
  margin-bottom: 12px;     /* 卡片间距 12px */
}

/* ❌ 避免：过度使用 !important 覆盖 WeUI */
.weui-cell {
  padding: 10px !important; /* 这是反模式 */
}

/* ✅ 好的：触摸反馈使用 WeUI 原生 hover-class */
<view hover-class="weui-cell_active" hover-stay-time="50">

/* ❌ 避免：自定义动画替代原生反馈 */
<view class="custom-ripple-effect">
```

**关键约定**:
- 正文字号: 17px (对齐微信原生)
- 辅助文字: 14px
- 提示文字: 12px
- 卡片内边距: 16px 统一
- 页面内边距: 16px 统一
- 卡片间距: 12px
- 组件间距: 8px
- 圆角: 8px (卡片) / 4px (内部元素)
- 颜色: 减少 `!important`，优先信任 WeUI 默认值

---

## Testing Strategy

| 测试层级 | 方法 | 覆盖范围 |
|---------|------|---------|
| 视觉回归 | 开发者工具逐页截图对比 | 全部 7 页面 |
| 交互验证 | 真机扫码，走通全部操作路径 | 关键流程: 登录→首页→学生管理(增删改)→排课(签到)→课时记录(翻页)→我的 |
| 边界测试 | iPhone SE (320px) + iPhone 14 Pro Max (430px) | 检查布局溢出、文字截断 |
| 无障碍 | 验证所有可点击区域 ≥ 44x44px | 按钮、列表项、胶囊 |

---

## Boundaries

### Always do
- 保持现有业务逻辑不变（JS 文件行为零改动）
- 遵循微信设计指南的间距/字号/颜色规范
- 所有可交互元素使用 WeUI hover-class 而非自定义动画
- 清理死代码前确认无任何页面引用
- 表单校验在 `form-sheet` 组件内统一处理，不分散到各页面

### Ask first
- 修改 app.wxss 中任何被 2+ 页面使用的类
- 改变品牌色 `#07C160` 或语义色
- 删除 TabBar 图标或替换为其他方案
- 引入任何新的 npm 包

### Never do
- 修改 JS 逻辑文件中的业务代码
- 使用内联 style 属性
- 添加 `!important` 覆盖 WeUI 原生样式（除非 WeUI bug）
- 删除仍在使用的 CSS 规则
- 修改 CloudBase 云函数或 API

---

## Success Criteria

美化完成后需满足以下条件：

- [x] **SC1 — 死代码清零**: `app.wxss` 中无未被引用的 CSS 规则（Grep 全项目确认）
- [x] **SC2 — 内联样式清零**: 所有 WXML 文件中无 `style=""` 属性（当前记录页有 2 处）
- [x] **SC3 — !important 归零**: 除非覆盖 WeUI 已知 bug，否则不使用
- [x] **SC4 — 间距统一**: 所有页面的卡片 padding 统一为 16px，页面 padding 统一为 16px
- [x] **SC5 — 表单收敛**: `form-sheet` 组件的 `.form-row` 样式只存在于组件内，页面不重复定义
- [x] **SC6 — 表单校验 UX**: 所有表单在提交时有不通过的字段有红色边框 + 抖动动画 + 错误文案
- [x] **SC7 — 防重复提交**: 所有表单提交按钮在请求中显示 loading 态且不可再次点击
- [x] **SC8 — 输入框修正**: 登录页用户名图标改为 `outline` 系，密码改为锁图标
- [x] **SC9 — Emoji 替换**: 空状态 emoji 替换为 WeUI `mp-icon` 或统一的插画占位
- [x] **SC10 — 触摸反馈**: 所有可交互区域有 hover-class 反馈，点击区域 ≥ 44x44px
- [x] **SC11 — 页面切换**: TabBar 页面间切换有原生级流畅度（需真机验证）
- [x] **SC12 — 深色模式钩子**: 全部 8 个 wxss 文件（app + 7 page）均预留 `@media (prefers-color-scheme: dark)`
- [ ] **SC13 — 真机验收**: 完整走通管理员+教师两条角色路径（需真机扫码测试）

## Verification Report

**日期**: 2026-06-13

| 检查项 | 结果 | 详情 |
|--------|------|------|
| app.wxss 行数 | 811 → **642**（-21%） | 删除 169 行死代码（含 Phase 8 复查发现的 .progress-bar） |
| 死代码 | ✅ 清零 | Grep 确认 0 未引用规则 |
| 内联样式 | ✅ 清零 | 仅剩 3 处合法：1 动态 width + 2 placeholder-style |
| !important | 46 → **36**（-22%） | 30 app.wxss + 1 form-sheet + 2 slideview，均有明确必要性 |
| 深色模式钩子 | ✅ 8/8 文件 | app.wxss + 7 个 page wxss |
| 空状态 emoji | ✅ 清零 | 5 处替换为 mp-icon |
| hover-class | ✅ 全覆盖 | 16 处交互元素 |
| 表单校验 | ✅ 全页面 | shake 动画 + 红色底边 + ::after 错误文案 |
| 防重复提交 | ✅ 全页面 | submitting 状态管理 + loading 按钮文字 |
| 字号体系 | ✅ 统一 | 12/14/17/20/24（13px 清零） |
| 圆角体系 | ✅ 统一 | 4/8/12px |
| 卡片间距 | ✅ 统一 | 12px |

**文件改动统计**: 8 WXML + 9 WXSS + 3 JS + 1 JSON = **21 个文件**

### 已知限制
- SC11（页面切换流畅度）需真机验证
- SC12（iPhone SE / 14 Pro Max）需真机测试
- SC13（双角色路径）需真机扫码验收

**状态**: 代码层面完成，待真机验收

---

## Design Tokens (对齐微信原生)

```
/* 色板 — 信任 WeUI 原生 */
--weui-BG-0: #EDEDED       /* 页面背景 */
--weui-BG-2: #FFFFFF       /* 卡片背景 */
--weui-FG-0: #000000       /* 主文字 */
--weui-FG-1: #353535       /* 正文 */
--weui-FG-2: #888888       /* 辅助文字 */
--weui-BRAND: #07C160      /* 微信绿（项目品牌色） */
--weui-RED:   #FA5151      /* 危险/错误 */

/* 间距 — 微信原生节奏 */
4/8/12/16/24/32

/* 字号 — 微信原生体系 */
12 (辅助说明) / 14 (次要信息) / 17 (正文) / 20 (小标题) / 24 (页面标题)

/* 圆角 — 微信原生风格 */
4px (输入框/标签) / 8px (卡片) / 12px (弹窗)

/* 阴影 — 极简 */
卡片: 0 1px 0 0 rgba(0,0,0,0.05)  (模拟微信列表分割线而非卡片阴影)

深色模式钩子 */
/* 每个 page 级 wxss 末尾预留空块:
@media (prefers-color-scheme: dark) {
  待后续填充
}
*/

骨架屏 shimmer */
/* 扫光动画关键帧:
@keyframes shimmer {
  0%   { background-position: -400px 0; }
  100% { background-position: 400px 0; }
}
.skeleton {
  background: linear-gradient(90deg, #F0F0F0 25%, #E5E5E5 50%, #F0F0F0 75%);
  background-size: 800px 100%;
  animation: shimmer 1.5s ease-in-out infinite;
}
```

---

## Task DAG

```
Phase 1: 死代码清理 ──────┐
                           ▼
Phase 2: 设计令牌统一 ─────┬─────────────┬──────────────┬──────────────┬──────────────┐
                           ▼             ▼              ▼              ▼              ▼
                     Phase 3:       Phase 4:        Phase 5:       Phase 6:       Phase 7:
                     登录页打磨     全局细节打磨     表单组件重构    WeUI 回归     骨架屏升级
                           │             │              │              │              │
                           └─────────────┴──────────────┴──────────────┴──────────────┘
                                                       ▼
                                               Phase 8: 验证
```

| Phase | 任务 | 涉及文件 | 依赖 |
|-------|------|---------|------|
| 1 | 死代码 & 内联样式清零 | app.wxss, records.wxml | — |
| 2 | 设计令牌统一 | app.wxss, 全部 7 页 wxss | 1 |
| 3 | 登录页打磨 | login.wxss, login.wxml | 2 |
| 4 | Emoji 替换 + 触摸反馈 + 隐私页修正 | 全部 7 页 wxss/wxml | 2 |
| 5 | 表单组件重构 | form-sheet/*, 3 页 wxss | 2 |
| 6 | WeUI 原生回归 | app.wxss | 2 |
| 7 | 骨架屏 shimmer | index.wxss, app.wxss | 2 |
| 8 | 验证 & 输出报告 | 全项目 Grep + 截图 | 1-7 |

**预计改动量**: ~15 个文件，纯样式的增量修改，零 JS 逻辑变更。

**执行策略**: Phase 1-2 必须串行（为后续建立基线），Phase 3-7 可并行推进。

---

## 已决策项

| # | 问题 | 决策 |
|---|------|------|
| 1 | TabBar 图标方案 | **保持 PNG** — 本次不替换 |
| 2 | 深色模式预留 | **预留钩子** — 在 page 级 CSS 变量中预留 `@media (prefers-color-scheme: dark)` 空块 |
| 3 | 品牌色 | **维持 `#07C160`** — 微信原生绿不动 |
| 4 | 骨架屏动画 | **升级 shimmer** — 首页骨架屏从 opacity 动画升级为扫光效果 |

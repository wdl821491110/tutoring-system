# 课消管理系统 — 项目记忆

## 技术栈
- 微信小程序 + WeUI 样式库（app.wxss @import weui.wxss）
- 后端: Flask + SQLite + JWT，部署在腾讯 CloudBase（env: tutoring-d1g8s1kwf3a000614）
- 小程序 AppID: wxf28edbb317622a4b，wx.cloud.callContainer 内网通道
- PC端: EXE 打包，本地测试通过后再部署

## WeUI 架构
- 样式: 使用 WeUI 扩展库（app.json: useExtendedLib.weui=true），不手动 @import
- app.json: useExtendedLib.weui = true（mp- 前缀组件可用）
- 页面使用原生 weui 类名（weui-cells/weui-cell/weui-btn/weui-grid/weui-progress/weui-article 等）
- mp- 前缀交互组件仍需 JSON 注册：mp-icon, mp-searchbar, mp-slideview, mp-checkbox, mp-half-screen-dialog
- form-sheet 自定义组件封装 mp-half-screen-dialog + slot

## 页面结构
- 首页(index): weui-grid 九宫格 + weui-progress 排行
- 学员(students): weui-cells + mp-slideview + weui-badge
- 排课(schedules): picker mode=date/time + weui-cells + filter-pill 胶囊筛选
- 记录(records): view-mode-bar 切换 + weui-cells + mp-half-screen-dialog 备注
- 个人中心(profile): 头像上传(chooseAvatar+localStorage) + weui-cells
- 登录(login): weui-cells_form + weui-input
- 隐私(privacy): weui-article 排版

## 业务特有样式（WeUI 无等价物）
- tag 标签系列（7色 + xs尺寸）
- filter-pill 胶囊筛选
- schedule-action 排课操作按钮
- view-mode-bar 视图切换栏
- pager-btn 分页器
- record-* 记录展示
- skeleton 骨架屏

## 开发约定
- 用户要求：先提交方案再执行，git push 只提供命令不自动执行
- PC端先本地打包测试EXE，确认后再指向服务器
- 沟通简洁直接，用"改"、"好"等单字指令

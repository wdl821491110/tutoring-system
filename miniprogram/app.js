const { request } = require('./utils/request');
const { isAdmin, isTeacher, restoreSession } = require('./utils/auth');
const { initAll } = require('./utils/initializer');

App({
  globalData: {
    token: null,
    user: null
  },

  onLaunch() {
    // 1. 恢复登录态
    restoreSession();

    // 2. 执行全部初始化（云环境、错误捕获、网络监听、隐私、版本更新）
    initAll();
  },

  // 保持与原有 app.api() 兼容
  api: request,
  isAdmin,
  isTeacher
});

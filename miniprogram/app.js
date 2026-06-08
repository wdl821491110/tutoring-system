const { request } = require('./utils/request');
const { isAdmin, isTeacher, restoreSession } = require('./utils/auth');

App({
  globalData: {
    token: null,
    user: null
  },

  onLaunch() {
    // 1. 恢复登录态
    restoreSession();

    // 2. 隐私授权检查（WeChat 审核强制要求）
    this.checkPrivacy();

    // 3. 版本更新检测
    this.checkUpdate();

    // 4. 网络状态监听
    wx.onNetworkStatusChange((res) => {
      if (!res.isConnected) {
        wx.showToast({ title: '网络已断开', icon: 'none', duration: 3000 });
      }
    });
  },

  /** 隐私授权 — WeChat 2023.09+ 强制要求 */
  checkPrivacy() {
    if (wx.getPrivacySetting) {
      wx.getPrivacySetting({
        success: (res) => {
          if (res.needAuthorization) {
            // 需要用户同意隐私协议后才可调用隐私接口
            // 实际弹窗由 WeChat 自动处理，这里做预检
            console.log('[Privacy] 需要用户授权隐私协议');
          }
        },
        fail: () => {}
      });
    }
  },

  /** 版本更新 — 静默下载，就绪提示 */
  checkUpdate() {
    if (!wx.canIUse('getUpdateManager')) return;
    const updateManager = wx.getUpdateManager();
    updateManager.onUpdateReady(() => {
      wx.showModal({
        title: '更新提示',
        content: '新版本已就绪，是否重启应用？',
        success: (res) => {
          if (res.confirm) updateManager.applyUpdate();
        }
      });
    });
    // 静默检查失败不提示
    updateManager.onUpdateFailed(() => {});
  },

  /** 全局未捕获错误 */
  onError(err) {
    console.error('[App Error]', err);
  },

  /** Promise 未处理拒绝 */
  onUnhandledRejection(res) {
    console.error('[Unhandled Rejection]', res.reason);
  },

  // 保持与原 app.api() 兼容 — 各页面通过 getApp().api() 仍可使用
  api: request,

  isAdmin,
  isTeacher
});

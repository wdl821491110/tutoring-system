/**
 * 初始化模块 - 负责小程序启动时的各项初始化任务
 * 与 app.js 解耦，便于测试和复用
 */

/**
 * 初始化云环境
 */
function initCloud() {
  if (!wx.cloud) {
    wx.showToast({ title: '微信版本过低，请升级', icon: 'none' });
    return false;
  }
  wx.cloud.init({ env: 'tutoring-d1g8s1kwf3a000614' });
  return true;
}

/**
 * 设置全局错误捕获
 */
function registerErrorHandlers() {
  if (typeof getApp === 'function') {
    const app = getApp();
    if (app) {
      app.onError = function(err) {
        console.error('[App Error]', err);
      };
      app.onUnhandledRejection = function(res) {
        console.error('[Unhandled Rejection]', res.reason);
      };
    }
  }
  return true;
}

/**
 * 检查并注册网络状态监听
 */
function registerNetworkMonitor() {
  wx.onNetworkStatusChange((res) => {
    if (!res.isConnected) {
      wx.showToast({ title: '网络已断开', icon: 'none', duration: 3000 });
    }
  });
  return true;
}

/**
 * 检查隐私协议授权（微信 2023.09+ 强制要求）
 */
function checkPrivacy() {
  if (!wx.getPrivacySetting) return true;
  wx.getPrivacySetting({
    success: (res) => {
      if (res.needAuthorization) {
        console.log('[Privacy] 需要用户授权隐私协议');
      }
    },
    fail: () => {}
  });
  return true;
}

/**
 * 检查版本更新
 */
function checkUpdate() {
  if (!wx.canIUse('getUpdateManager')) return true;
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
  updateManager.onUpdateFailed(() => {});
  return true;
}

/**
 * 执行全部初始化任务
 * @returns {object} 初始化结果 { cloud, errors, privacy, update }
 */
function initAll() {
  return {
    cloud: initCloud(),
    errors: registerErrorHandlers(),
    network: registerNetworkMonitor(),
    privacy: checkPrivacy(),
    update: checkUpdate()
  };
}

module.exports = { initAll, initCloud, registerErrorHandlers, checkPrivacy, checkUpdate };

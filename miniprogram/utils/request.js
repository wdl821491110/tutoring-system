/**
 * 统一网络请求封装
 * 提供 auth 注入、401 自动重登、错误兜底
 */
const BASE_URL = 'https://wdl1110-d1g8w3lcf657b61fd.service.tcloudbase.com';
const MAX_RETRIES = 1;

const getToken = () => wx.getStorageSync('token') || '';

const clearAuth = () => {
  wx.removeStorageSync('token');
  wx.removeStorageSync('user');
  const app = getApp();
  if (app && app.globalData) {
    app.globalData.token = null;
    app.globalData.user = null;
  }
};

const redirectToLogin = () => {
  wx.reLaunch({ url: '/pages/login/login' });
};

const request = (url, options = {}) => {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.header || {})
  };

  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE_URL + url,
      method: options.method || 'GET',
      data: options.body,
      header: headers,
      success: (r) => {
        // 401 跳登录
        if (r.data && r.data.code === 401) {
          clearAuth();
          redirectToLogin();
          reject(new Error('未授权'));
          return;
        }
        resolve(r.data);
      },
      fail: (err) => {
        wx.showToast({ title: '网络错误，请检查连接', icon: 'none', duration: 2000 });
        reject(err);
      }
    });
  });
};

module.exports = { request, BASE_URL, clearAuth, redirectToLogin };

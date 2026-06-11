/**
 * 认证与角色管理
 */
const { request } = require('./request');

const STORAGE_KEY_TOKEN = 'token';
const STORAGE_KEY_USER = 'user';

/** 获取 app 实例的安全方法 */
const safeApp = () => getApp() || { globalData: {} };

/** 恢复本地缓存的登录态 */
const restoreSession = () => {
  const token = wx.getStorageSync(STORAGE_KEY_TOKEN);
  const user = wx.getStorageSync(STORAGE_KEY_USER);
  if (token && user) {
    const app = safeApp();
    app.globalData.token = token;
    app.globalData.user = user;
    return true;
  }
  return false;
};

/** 用户名密码登录 */
const login = (username, password) => {
  return request('/api/auth/login', {
    method: 'POST',
    body: { username, password }
  }).then((res) => {
    if (res.code === 200) {
      const app = safeApp();
      wx.setStorageSync(STORAGE_KEY_TOKEN, res.data.token);
      wx.setStorageSync(STORAGE_KEY_USER, res.data.user);
      app.globalData.token = res.data.token;
      app.globalData.user = res.data.user;
    }
    return res;
  });
};

/** 是否已登录 */
const isLoggedIn = () => {
  return !!(safeApp().globalData.token);
};

/** 角色判断 */
const isAdmin = () => {
  const user = safeApp().globalData.user;
  return user && user.role === 'admin';
};

const isTeacher = () => {
  const user = safeApp().globalData.user;
  return user && (user.role === 'teacher' || user.role === 'admin');
};

/** 退出登录 */
const logout = () => {
  wx.removeStorageSync(STORAGE_KEY_TOKEN);
  wx.removeStorageSync(STORAGE_KEY_USER);
  const app = safeApp();
  app.globalData.token = null;
  app.globalData.user = null;
};

module.exports = { login, logout, isLoggedIn, isAdmin, isTeacher, restoreSession,
  STORAGE_KEY_TOKEN, STORAGE_KEY_USER };

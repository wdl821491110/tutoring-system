/**
 * 统一网络请求封装 — 使用 wx.cloud.callContainer 走微信内网通道
 * 提供 auth 注入、401 自动重登、错误兜底
 *
 * 与原 wx.request 版本的区别：
 *   - 不再需要 BASE_URL（走微信内网，不经过公网）
 *   - 不再需要 sig/ts/b64 的 Cloudflare WAF 绕过逻辑
 *   - 直接使用 Authorization header 传递 JWT token
 */
const SERVICE_NAME = 'tutoring';   // CloudBase 云托管服务名
const ENV_ID = 'tutoring-d1g8s1kwf3a000614';

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

/**
 * 统一请求函数
 * @param {string} url  - 路径，如 '/api/students'
 * @param {object} options - { method, body, header }
 * @returns {Promise<object>} 解析为后端返回的 JSON body（{ code, data, message }）
 */
const request = (url, options = {}) => {
  const token = getToken();
  const method = options.method || 'GET';

  const headers = {
    'Content-Type': 'application/json',
    'X-WX-SERVICE': SERVICE_NAME,
    ...(options.header || {})
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // wx.cloud 可用性检查
  if (!wx.cloud || !wx.cloud.callContainer) {
    wx.showToast({ title: '微信版本过低，请升级', icon: 'none' });
    return Promise.reject(new Error('wx.cloud.callContainer not available'));
  }

  return new Promise((resolve, reject) => {
    wx.cloud.callContainer({
      config: { env: ENV_ID },
      path: url,
      method: method,
      header: headers,
      data: method !== 'GET' ? (options.body || {}) : {},
      success: (r) => {
        // r.data = 响应体 { code, data, message }
        // r.statusCode = HTTP 状态码
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

module.exports = { request, clearAuth, redirectToLogin };

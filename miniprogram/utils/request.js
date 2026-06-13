/**
 * 统一网络请求封装 - 使用 wx.cloud.callContainer 走微信内网通道
 * 提供 auth 注入、401 自动重登、错误兜底、业务 code 校验
 */
const SERVICE_NAME = 'tutoring';
const ENV_ID = 'tutoring-d1g8s1kwf3a000614';

const getToken = () => wx.getStorageSync('token') || '';
const BASE_URL = 'https://tutoring-d1g8s1kwf3a000614.cloudbasefunc.cloud';

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
  // 避免重复跳转
  if (wx.getCurrentPages().some(p => p.route === 'pages/login/login')) return;
  wx.reLaunch({ url: '/pages/login/login' });
};

/**
 * 统一请求函数
 * @param {string} url  - 路径，如 '/api/students'
 * @param {object} options - { method, body, header, silent }
 *   - silent: true 时不弹 toast 错误（用于静默校验场景）
 * @returns {Promise<object>} 解析为后端返回的 JSON body ({ code, data, message })
 */
const request = (url, options = {}) => {
  const token = getToken();
  const method = options.method || 'GET';
  const silent = options.silent || false;

  const headers = {
    'Content-Type': 'application/json',
    'X-WX-SERVICE': SERVICE_NAME,
    ...(options.header || {})
  };
  if (token) {
    headers['Authorization'] = 'Bearer ' + token;
  }

  if (!wx.cloud || !wx.cloud.callContainer) {
    if (!silent) wx.showToast({ title: '微信版本过低，请升级', icon: 'none' });
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
        // 1. 未授权 → 清除凭证并跳转登录
        if (r.data && r.data.code === 401) {
          clearAuth();
          redirectToLogin();
          reject(new Error('Unauthorized'));
          return;
        }
        // 2. 业务码异常 → 统一处理 toast
        if (r.data && r.data.code !== undefined && r.data.code !== 200) {
          if (!silent && r.data.message) {
            wx.showToast({ title: r.data.message, icon: 'none', duration: 2000 });
          }
          resolve(r.data);
          return;
        }
        // 3. HTTP 状态码异常
        if (r.statusCode >= 400 && r.statusCode < 600) {
          if (!silent) {
            wx.showToast({ title: '请求失败，请重试', icon: 'none', duration: 2000 });
          }
          reject(new Error('HTTP ' + r.statusCode));
          return;
        }
        resolve(r.data);
      },
      fail: (err) => {
        if (!silent) {
          wx.showToast({ title: '网络错误，请检查连接', icon: 'none', duration: 2000 });
        }
        reject(err);
      }
    });
  });
};

module.exports = { request, clearAuth, redirectToLogin, BASE_URL };

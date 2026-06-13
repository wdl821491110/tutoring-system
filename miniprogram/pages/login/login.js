const { login } = require('../../utils/auth');

Page({
  data: { username: '', password: '', loading: false, passwordVisible: false, agreed: false },

  toggleAgree() {
    this.setData({ agreed: !this.data.agreed });
  },

  onInput(e) {
    this.setData({ [e.currentTarget.dataset.key]: e.detail.value });
  },

  clearUsername() {
    this.setData({ username: '' });
  },

  togglePassword() {
    this.setData({ passwordVisible: !this.data.passwordVisible });
  },

  goPrivacy() {
    wx.navigateTo({ url: '/pages/privacy/privacy' });
  },

  doLogin() {
    const u = this.data.username.trim();
    const p = this.data.password.trim();
    if (!u || !p) { wx.showToast({ title: '请输入账号密码', icon: 'none' }); return; }

    this.setData({ loading: true });
    login(u, p).then((res) => {
      this.setData({ loading: false });
      if (res.code === 200) {
        wx.switchTab({ url: '/pages/index/index' });
      } else {
        wx.showToast({ title: res.message || '登录失败', icon: 'none' });
      }
    }).catch(() => {
      this.setData({ loading: false });
      wx.showToast({ title: '网络错误，请重试', icon: 'none' });
    });
  }
});

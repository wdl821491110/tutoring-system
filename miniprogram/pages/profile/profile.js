const app = getApp();
const { BASE_URL } = require('../../utils/request');
const { logout } = require('../../utils/auth');

Page({
  data: { isAdmin: false, user: {}, userPerms: null, loading: true },

  onShow() {
    if (!app.globalData.token) { wx.reLaunch({ url: '/pages/login/login' }); return; }
    this.setData({
      isAdmin: app.isAdmin(),
      user: app.globalData.user || {},
      loading: true
    });
    this.loadPerms();
  },

  loadPerms() {
    app.api('/api/auth/permissions').then((res) => {
      if (res.code === 200) this.setData({ userPerms: res.data });
      this.setData({ loading: false });
    }).catch(() => {
      this.setData({ loading: false });
    });
  },

  downloadBackup() {
    wx.showLoading({ title: '下载中' });
    wx.downloadFile({
      url: `${BASE_URL}/api/backup/download`,
      header: { Authorization: `Bearer ${app.globalData.token}` },
      success: (res) => {
        wx.hideLoading();
        if (res.statusCode === 200) {
          wx.saveFile({
            tempFilePath: res.tempFilePath,
            success: () => wx.showToast({ title: '下载成功', icon: 'success' }),
            fail: () => wx.showToast({ title: '保存失败', icon: 'none' })
          });
        } else {
          wx.showToast({ title: '下载失败', icon: 'none' });
        }
      },
      fail: () => { wx.hideLoading(); wx.showToast({ title: '下载失败', icon: 'none' }); }
    });
  },

  doLogout() {
    logout();
    wx.reLaunch({ url: '/pages/login/login' });
  },

  /** 跳转隐私政策 */
  goPrivacy() {
    wx.navigateTo({ url: '/pages/privacy/privacy' });
  }
});

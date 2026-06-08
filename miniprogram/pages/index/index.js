const app = getApp();

Page({
  data: {
    stats: {},
    loading: true
  },

  onShow() {
    if (!app.globalData.token) { wx.reLaunch({ url: '/pages/login/login' }); return; }
    this.load();
  },

  onPullDownRefresh() {
    this.load(true).then(() => wx.stopPullDownRefresh());
  },

  /**
   * 加载仪表盘 — 30s 缓存，下拉强制刷新
   */
  load(force) {
    // 缓存策略
    if (!force && this._cache && Date.now() - this._cache.time < 30000) {
      this.setData({ stats: this._cache.data, loading: false });
      return Promise.resolve();
    }

    this.setData({ loading: true });
    return app.api('/api/dashboard').then((res) => {
      const stats = res.code === 200 ? (res.data || {}) : {};
      this._cache = { time: Date.now(), data: stats };
      this.setData({ stats, loading: false });
    }).catch(() => {
      this.setData({ loading: false });
    });
  }
});

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
      const stats = res.data || {};

      // 前端从 course_details 聚合课程消耗排行
      // 公式：所有报名学生已消耗课时之和 / 所有报名学生报名总课时之和 × 100%
      const details = stats.course_details || [];
      const courseMap = {};
      details.forEach((d) => {
        const key = d.course_name;
        if (!courseMap[key]) {
          courseMap[key] = {
            name: d.course_name,
            subject: d.subject,
            teacher_name: d.teacher_name,
            total_consumed: 0,
            total_enrolled: 0
          };
        }
        courseMap[key].total_consumed += d.consumed_hours || 0;
        courseMap[key].total_enrolled += d.enrolled_hours || 0;
      });

      stats.course_ranking = Object.values(courseMap)
        .sort((a, b) => b.total_consumed - a.total_consumed)
        .slice(0, 10)
        .map((c) => ({
          ...c,
          total_hours: c.total_consumed,
          enrolled_hours: c.total_enrolled,
          percent: c.total_enrolled > 0 ? Math.round((c.total_consumed / c.total_enrolled) * 100) : 0
        }));

      this._cache = { time: Date.now(), data: stats };
      this.setData({ stats, loading: false });
    }).catch(() => {});
  },

  goPage(e) {
    const url = e.currentTarget.dataset.url;
    if (url) wx.switchTab({ url });
  }
});

const app = getApp();
const STATUS_MAP = ['', 'scheduled', 'completed', 'cancelled'];

Page({
  data: {
    isAdmin: false, isTeacher: false,
    list: [], loading: true,
    dateFilter: '', statusIdx: 0,
    showForm: false,
    students: [], courses: [], enrollments: [],
    studentNames: [], courseNames: [],
    form: { studentIdx: 0, courseIdx: 0, schedule_date: '', start_time: '', end_time: '', hours: 1, notes: '' }
  },

  onShow() {
    if (!app.globalData.token) { wx.reLaunch({ url: '/pages/login/login' }); return; }
    this.setData({ isAdmin: app.isAdmin(), isTeacher: app.isTeacher() });
    this.load();
  },

  onPullDownRefresh() {
    this.load(true).then(() => wx.stopPullDownRefresh());
  },

  load(force) {
    if (!force && this._cache && Date.now() - this._cache.time < 30000) {
      this.setData({ list: this._cache.data, loading: false });
      return Promise.resolve();
    }
    this.setData({ loading: true });

    let url = '/api/schedules?';
    if (this.data.dateFilter) {
      url += `date_from=${this.data.dateFilter}&date_to=${this.data.dateFilter}&`;
    }
    if (this.data.statusIdx > 0) {
      url += `status=${STATUS_MAP[this.data.statusIdx]}&`;
    }

    return app.api(url).then((res) => {
      const list = res.code === 200 ? (res.data || []) : [];
      this._cache = { time: Date.now(), data: list };
      this.setData({ list, loading: false });
    }).catch(() => {
      this.setData({ loading: false });
    });
  },

  filterToday() {
    const d = new Date();
    const ds = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    this.setData({ dateFilter: ds });
    this.load(true);
  },

  onDateChange(e) { this.setData({ dateFilter: e.detail }); this.load(true); },

  onStatusChange(e) {
    this.setData({ statusIdx: parseInt(e.currentTarget.dataset.idx) });
    this.load(true);
  },

  doCheckin(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '确认签到',
      content: '签到后将自动消课，确定吗？',
      success: (r) => {
        if (!r.confirm) return;
        app.api('/api/records', { method: 'POST', body: { schedule_id: id } }).then((res) => {
          wx.showToast({ title: res.message || '完成', icon: res.code === 200 ? 'success' : 'none' });
          this.load(true);
        });
      }
    });
  },

  doCancel(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '取消排课',
      content: '确定取消该排课？',
      success: (r) => {
        if (!r.confirm) return;
        app.api(`/api/schedules/${id}/cancel`, { method: 'POST' }).then(() => {
          wx.showToast({ title: '已取消', icon: 'success' });
          this.load(true);
        });
      }
    });
  },

  /** ✅ 修复：Promise.all 并行加载，错误兜底保证 hideLoading */
  showAdd() {
    wx.showLoading({ title: '加载中' });
    Promise.all([
      app.api('/api/students?status=active'),
      app.api('/api/courses'),
      app.api('/api/enrollments?status=active')
    ]).then(([s, c, e]) => {
      wx.hideLoading();
      const students = (s.data || []).filter((x) => x.status !== 'inactive');
      const courses = (c.data || []).filter((x) => x.status !== 'inactive');
      const d = new Date();
      const ds = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      this.setData({
        showForm: true,
        students, courses,
        enrollments: e.data || [],
        studentNames: students.map((x) => x.name),
        courseNames: courses.map((x) => x.name),
        form: { studentIdx: 0, courseIdx: 0, schedule_date: ds, start_time: '', end_time: '', hours: 1, notes: '' }
      });
    }).catch(() => {
      wx.hideLoading();
      wx.showToast({ title: '加载失败', icon: 'none' });
    });
  },

  /** ✅ 修复：使用 setData 路径更新，不直接修改 data */
  onFormChange(e) {
    this.setData({ [`form.${e.currentTarget.dataset.field}`]: e.detail.value });
  },

  onStudentChange(e) {
    const idx = parseInt(e.detail.value);
    const student = this.data.students[idx];
    const sid = student ? student.id : 0;
    const enrollments = this.data.enrollments || [];
    const es = enrollments.filter((en) => en.student_id === sid);

    // 学生只关联一门课 → 自动选中
    let courseIdx = this.data.form.courseIdx;
    if (es.length === 1) {
      const cid = es[0].course_id;
      const found = this.data.courses.findIndex((c) => c.id === cid);
      if (found !== -1) courseIdx = found;
    }

    this.setData({
      'form.studentIdx': idx,
      'form.courseIdx': courseIdx
    });
  },

  onCourseChange(e) {
    this.setData({ 'form.courseIdx': parseInt(e.detail.value) });
  },

  saveSchedule(e) {
    if (e.detail.index !== 1) { this.setData({ showForm: false }); return; }
    this._doSaveSchedule();
  },

  closeForm() {
    this.setData({ showForm: false });
  },

  /** 提交排课（替代原 mp-dialog 的 bindbuttontap） */
  submitSchedule() {
    this._doSaveSchedule();
  },

  _doSaveSchedule() {
    const { form, students, courses } = this.data;
    const sid = students[form.studentIdx] ? students[form.studentIdx].id : 0;
    const cid = courses[form.courseIdx] ? courses[form.courseIdx].id : 0;
    if (!sid || !cid) { wx.showToast({ title: '请选择学生和课程', icon: 'none' }); return; }
    if (!form.schedule_date) { wx.showToast({ title: '请选择日期', icon: 'none' }); return; }

    const body = JSON.stringify({
      student_id: sid, course_id: cid,
      schedule_date: form.schedule_date, start_time: form.start_time,
      end_time: form.end_time, hours: parseInt(form.hours) || 1,
      notes: form.notes
    });

    app.api('/api/schedules', { method: 'POST', body }).then((res) => {
      if (res.code === 200) {
        wx.showToast({ title: '排课成功', icon: 'success' });
        this.setData({ showForm: false });
        this.load(true);
      } else {
        wx.showToast({ title: res.message, icon: 'none' });
      }
    });
  },

  deleteSchedule(e) {
    const s = e.currentTarget.dataset.schedule;
    wx.showModal({
      title: '删除排课',
      content: '确定删除？',
      success: (r) => {
        if (!r.confirm) return;
        app.api(`/api/schedules/${s.id}`, { method: 'DELETE' }).then((res) => {
          if (res.code === 200) { wx.showToast({ title: '已删除', icon: 'success' }); this.load(true); }
          else wx.showToast({ title: res.message, icon: 'none' });
        });
      }
    });
  },

  noop() {}
});

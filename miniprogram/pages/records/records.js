const app = getApp();

Page({
  data: {
    isAdmin: false,
    list: [], loading: true,
    page: 1, totalPages: 1, total: 0,
    dateFrom: '', dateTo: '',
    showForm: false, showNotes: false,
    noteRecordId: 0, notes: [], newNoteContent: '',
    students: [], courses: [], enrollments: [],
    studentNames: [], courseNames: [],
    form: { studentIdx: 0, courseIdx: 0, record_date: '', hours_consumed: 1, attendance: 'present', notes: '' }
  },

  onShow() {
    if (!app.globalData.token) { wx.reLaunch({ url: '/pages/login/login' }); return; }
    this.setData({ isAdmin: app.isAdmin() });
    this.load();
  },

  onPullDownRefresh() {
    this.load(this.data.page, true).then(() => wx.stopPullDownRefresh());
  },

  load(p, force) {
    p = p || this.data.page;
    // cache only page 1, 30s
    if (!force && p === 1 && this._cache && Date.now() - this._cache.time < 30000) {
      const c = this._cache;
      this.setData({ list: c.list, page: c.page, totalPages: c.totalPages, total: c.total, loading: false });
      return Promise.resolve();
    }
    this.setData({ loading: true });

    let url = `/api/records?page=${p}&per_page=20`;
    if (this.data.dateFrom) url += `&date_from=${this.data.dateFrom}`;
    if (this.data.dateTo) url += `&date_to=${this.data.dateTo}`;

    return app.api(url).then((res) => {
      const list = res.code === 200 ? (res.data.records || []) : [];
      const pageVal = res.code === 200 ? res.data.page : 1;
      const totalPages = res.code === 200 ? res.data.total_pages : 1;
      const total = res.code === 200 ? res.data.total : 0;
      if (p === 1) {
        this._cache = { time: Date.now(), list, page: pageVal, totalPages, total };
      }
      this.setData({ list, page: pageVal, totalPages, total, loading: false });
    }).catch(() => {
      this.setData({ loading: false });
    });
  },

  onDateFrom(e) { this.setData({ dateFrom: e.detail }); this.load(1, true); },
  onDateTo(e) { this.setData({ dateTo: e.detail }); this.load(1, true); },

  prevPage() { if (this.data.page > 1) this.load(this.data.page - 1); },
  nextPage() { if (this.data.page < this.data.totalPages) this.load(this.data.page + 1); },

  /** ✅ Promise.all 并行加载 + 错误兜底 */
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
        form: { studentIdx: 0, courseIdx: 0, record_date: ds, hours_consumed: 1, attendance: 'present', notes: '' }
      });
    }).catch(() => {
      wx.hideLoading();
      wx.showToast({ title: '加载失败', icon: 'none' });
    });
  },

  /** ✅ 路径更新 */
  onFieldChange(e) {
    this.setData({ [`form.${e.currentTarget.dataset.field}`]: e.detail.value });
  },

  onStudentChange(e) {
    const idx = parseInt(e.detail.value);
    const student = this.data.students[idx];
    const sid = student ? student.id : 0;
    const es = (this.data.enrollments || []).filter((en) => en.student_id === sid);

    let courseIdx = this.data.form.courseIdx;
    if (es.length === 1) {
      const cid = es[0].course_id;
      const found = this.data.courses.findIndex((c) => c.id === cid);
      if (found !== -1) courseIdx = found;
    }

    this.setData({ 'form.studentIdx': idx, 'form.courseIdx': courseIdx });
  },

  onCourseChange(e) {
    this.setData({ 'form.courseIdx': parseInt(e.detail.value) });
  },

  closeForm() { this.setData({ showForm: false }); },

  /** 提交消课记录 */
  submitRecord() {
    const { form, students, courses } = this.data;
    const sid = students[form.studentIdx] ? students[form.studentIdx].id : 0;
    const cid = courses[form.courseIdx] ? courses[form.courseIdx].id : 0;
    if (!sid || !cid) { wx.showToast({ title: '请选择学生和课程', icon: 'none' }); return; }

    const body = JSON.stringify({
      student_id: sid, course_id: cid, record_date: form.record_date,
      hours_consumed: parseInt(form.hours_consumed) || 1,
      attendance: form.attendance, notes: form.notes
    });

    app.api('/api/records', { method: 'POST', body }).then((res) => {
      if (res.code === 200) {
        wx.showToast({ title: '消课成功', icon: 'success' });
        this.setData({ showForm: false });
        this.load(1, true);
      } else {
        wx.showToast({ title: res.message, icon: 'none' });
      }
    });
  },

  undoRecord(e) {
    const rid = e.currentTarget.dataset.rid;
    wx.showModal({
      title: '撤销记录',
      content: '确定撤销该消课记录吗？',
      success: (r) => {
        if (!r.confirm) return;
        app.api(`/api/records/${rid}`, { method: 'DELETE' }).then((res) => {
          if (res.code === 200) { wx.showToast({ title: '已撤销', icon: 'success' }); this.load(1, true); }
          else wx.showToast({ title: res.message, icon: 'none' });
        });
      }
    });
  },

  showNotes(e) {
    const rid = e.currentTarget.dataset.rid;
    app.api(`/api/records/${rid}/notes`).then((res) => {
      this.setData({ showNotes: true, noteRecordId: rid, notes: res.data || [], newNoteContent: '' });
    });
  },

  onNoteInput(e) {
    this.setData({ newNoteContent: e.detail.value });
  },

  closeNotes() { this.setData({ showNotes: false }); },

  /** 添加备注（替代原 mp-dialog 的 bindbuttontap） */
  addNote() {
    const content = this.data.newNoteContent.trim();
    if (!content) { wx.showToast({ title: '请输入内容', icon: 'none' }); return; }

    app.api(`/api/records/${this.data.noteRecordId}/notes`, {
      method: 'POST',
      body: JSON.stringify({ content })
    }).then((res) => {
      if (res.code === 200) {
        wx.showToast({ title: '已添加', icon: 'success' });
        // 重新拉取备注 + 刷新列表
        this.showNotes({ currentTarget: { dataset: { rid: this.data.noteRecordId } } });
        this.load(1, true);
      } else {
        wx.showToast({ title: res.message, icon: 'none' });
      }
    });
  },

  noop() {}
});

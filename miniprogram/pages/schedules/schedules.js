const app = getApp();
const { validate } = require('../../utils/validator');
const STATUS_MAP = ['', 'scheduled', 'completed', 'cancelled'];

Page({
  data: {
    isAdmin: false, isTeacher: false,
    list: [], loading: true,
    dateFilter: '', statusIdx: 0,
    showForm: false,
    submitting: false,
    students: [], courses: [], enrollments: [],
    studentNames: [], courseNames: [],
    form: { studentIdx: 0, courseIdx: 0, schedule_date: '', start_time: '', end_time: '', hours: 1, notes: '' },
    errors: {},
    formValid: false,
    /* 排课编辑 */
    editingId: null,
    /* 批量签到 */
    batchMode: false,
    checkedIds: [],
    batchSubmitting: false
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
      const list = res.data || [];
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

  onDateChange(e) { this.setData({ dateFilter: e.detail.value }); this.load(true); },

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
          this.load(true);
        });
      }
    });
  },

  /* 表单校验 */
  _validate() {
    const result = validate('schedule', {
      form: this.data.form,
      students: this.data.students,
      courses: this.data.courses
    });
    this.setData({ errors: result.errors, formValid: result.formValid });
  },

  showAdd() {
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
        errors: {}, formValid: false, editingId: null,
        form: { studentIdx: 0, courseIdx: 0, schedule_date: ds, start_time: '', end_time: '', hours: 1, notes: '' }
      });
    }).catch(() => {
      wx.hideLoading();
      wx.showToast({ title: '加载失败', icon: 'none' });
    });
  },

  onFormChange(e) {
    const field = e.currentTarget.dataset.field;
    if (field) { this.setData({ [`form.${field}`]: e.detail.value }); this._validate(); }
  },

  onFieldInput(e) {
    const field = e.currentTarget.dataset.field;
    if (field) { this.setData({ [`form.${field}`]: e.detail.value }); this._validate(); }
  },

  onStudentChange(e) {
    const idx = parseInt(e.detail.value);
    const student = this.data.students[idx];
    const sid = student ? student.id : 0;
    const enrollments = this.data.enrollments || [];
    const es = enrollments.filter((en) => en.student_id === sid);

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
    this._validate();
  },

  onCourseChange(e) {
    this.setData({ 'form.courseIdx': parseInt(e.detail.value) });
    this._validate();
  },

  closeForm() {
    this.setData({ showForm: false });
  },

  submitSchedule() {
    this._validate();
    if (!this.data.formValid) return;
    this.setData({ submitting: true });
    this._doSaveSchedule();
  },

  _doSaveSchedule() {
    const { form, students, courses, editingId } = this.data;
    const sid = students[form.studentIdx] ? students[form.studentIdx].id : 0;
    const cid = courses[form.courseIdx] ? courses[form.courseIdx].id : 0;
    const isEdit = !!editingId;

    const body = JSON.stringify({
      student_id: sid, course_id: cid,
      schedule_date: form.schedule_date, start_time: form.start_time,
      end_time: form.end_time, hours: parseInt(form.hours) || 1,
      notes: form.notes
    });

    const url = isEdit ? `/api/schedules/${editingId}` : '/api/schedules';
    const method = isEdit ? 'PUT' : 'POST';

    app.api(url, { method, body }).then((res) => {
      this.setData({ submitting: false });
      if (res.code === 200) {
        wx.showToast({ title: res.message || '已保存', icon: 'success' });
        this.setData({ showForm: false, editingId: null });
        this.load(true);
      }
    }).catch(() => {
      this.setData({ submitting: false });
    });
  },

  /* ======== 排课编辑 F1 ======== */
  showEdit(e) {
    const item = e.currentTarget.dataset.schedule;
    Promise.all([
      app.api('/api/students?status=active'),
      app.api('/api/courses'),
      app.api('/api/enrollments?status=active')
    ]).then(([s, c, e]) => {
      wx.hideLoading();
      const students = (s.data || []).filter((x) => x.status !== 'inactive');
      const courses = (c.data || []).filter((x) => x.status !== 'inactive');
      const studentIdx = students.findIndex((x) => x.id === item.student_id);
      const courseIdx = courses.findIndex((x) => x.id === item.course_id);
      this.setData({
        showForm: true, editingId: item.id,
        students, courses,
        enrollments: e.data || [],
        studentNames: students.map((x) => x.name),
        courseNames: courses.map((x) => x.name),
        errors: {}, formValid: true,
        form: {
          studentIdx: Math.max(studentIdx, 0),
          courseIdx: Math.max(courseIdx, 0),
          schedule_date: item.schedule_date || '',
          start_time: item.start_time || '',
          end_time: item.end_time || '',
          hours: item.hours || 1,
          notes: item.notes || ''
        }
      });
    }).catch(() => {
      wx.hideLoading();
      wx.showToast({ title: '加载失败', icon: 'none' });
    });
  },

  /* ======== 批量签到 F2 ======== */
  toggleBatchMode() {
    this.setData({ batchMode: !this.data.batchMode, checkedIds: [] });
  },

  onCheckToggle(e) {
    const id = e.currentTarget.dataset.id;
    const ids = this.data.checkedIds.slice();
    const idx = ids.indexOf(id);
    if (idx > -1) ids.splice(idx, 1);
    else ids.push(id);
    this.setData({ checkedIds: ids });
  },

  selectAll() {
    const all = this.data.list.filter((x) => x.status === 'scheduled').map((x) => x.id);
    this.setData({ checkedIds: all });
  },

  batchCheckin() {
    const { checkedIds } = this.data;
    if (!checkedIds.length) { wx.showToast({ title: '请选择排课', icon: 'none' }); return; }
    wx.showModal({
      title: '批量签到',
      content: `确认对 ${checkedIds.length} 节排课签到消课？`,
      success: (r) => {
        if (!r.confirm) return;
        this.setData({ batchSubmitting: true });
        app.api('/api/records/batch-checkin', {
          method: 'POST',
          body: JSON.stringify({ schedule_ids: checkedIds })
        }).then((res) => {
          wx.showToast({ title: res.message || '完成', icon: res.code === 200 ? 'success' : 'none' });
          this.setData({ batchMode: false, checkedIds: [], batchSubmitting: false });
          this.load(true);
        }).catch(() => {
          this.setData({ batchSubmitting: false });
        });
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
        });
      }
    });
  },

  noop() {}
});


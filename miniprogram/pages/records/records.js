const app = getApp();
const { validate } = require('../../utils/validator');
const { getFirstLetter } = require('../../utils/pinyin');
Page({

  data: {
    isAdmin: false,
    list: [], loading: true, alphaList: [],
    page: 1, totalPages: 1, total: 0,
    viewMode: 'date',
    pickDate: '',
    dateFrom: '', dateTo: '',
    showForm: false, showNotes: false, submitting: false,
    noteRecordId: 0, notes: [], newNoteContent: '',
    students: [], courses: [], enrollments: [],
    studentNames: [], courseNames: [],
    form: { studentIdx: 0, courseIdx: 0, record_date: '', hours_consumed: 1, attendance: 'present', notes: '' },
    errors: {},
    formValid: false,
    expandedMap: {},

    noteButtons: [
      { type: 'default', text: '关闭' },
      { type: 'primary', text: '添加' }
    ]
  },

  onShow() {
    if (!app.globalData.token) { wx.reLaunch({ url: '/pages/login/login' }); return; }
    this.setData({ isAdmin: app.isAdmin() });
    if (!this.data.pickDate) {
      const d = new Date();
      const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      this.setData({ pickDate: today, dateFrom: today, dateTo: today });
    }
    this.load();
  },

  onPullDownRefresh() {
    this.load(this.data.page, true).then(() => wx.stopPullDownRefresh());
  },

  load(p, force, limit) {
    p = p || this.data.page;
    if (!force && p === 1 && this._cache && Date.now() - this._cache.time < 30000) {
      const c = this._cache;
      this.setData({ list: c.list, page: c.page, totalPages: c.totalPages, total: c.total, loading: false });
      return Promise.resolve();
    }
    this.setData({ loading: true });

    const perPage = (limit && limit > 0) ? limit : 20;
    let url = `/api/records?page=${p}&per_page=${perPage}`;
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
      this._buildAlphaList(list);
    }).catch(() => {
      this.setData({ loading: false });
    });
  },

  _buildAlphaList(list) {
    const map = {};
    (list || []).forEach(r => {
      const name = r.student_name || '鏈煡';
      const letter = getFirstLetter(name);
      if (!map[name]) map[name] = { name, letter, records: [], total_hours: 0 };
      map[name].records.push(r);
      map[name].total_hours += r.hours_consumed || 0;
    });
    const alphaMap = {};
    Object.values(map).forEach(stu => {
      const l = stu.letter;
      if (!alphaMap[l]) alphaMap[l] = [];
      alphaMap[l].push(stu);
    });
    const sorted = Object.keys(alphaMap).sort().map(l => ({
      letter: l,
      students: alphaMap[l].sort((a, b) => a.name.localeCompare(b.name, 'zh'))
    }));
    this.setData({ alphaList: sorted });
  },

  switchView(e) {
    const mode = e.currentTarget.dataset.mode;
    this.setData({ viewMode: mode, expandedMap: {} });
    if (mode === 'student') {
      this.setData({ dateFrom: '', dateTo: '', page: 1 });
      this._cache = null;
      // 学生模式按字母分页，每页 50 条
      this.load(1, true, 50);
    } else {
      const d = new Date();
      const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      this.setData({ pickDate: today, dateFrom: today, dateTo: today, page: 1 });
      this._cache = null;
      this.load(1, true);
    }
  },

  toggleExpand(e) {
    const name = e.currentTarget.dataset.name;
    const expandedMap = { ...this.data.expandedMap };
    expandedMap[name] = !expandedMap[name];
    this.setData({ expandedMap });
  },

  onPickDate(e) {
    const val = e.detail.value;
    this.setData({ pickDate: val, dateFrom: val, dateTo: val, page: 1 });
    this._cache = null;
    this.load(1, true);
  },

  filterToday() {
    const d = new Date();
    const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    this.setData({ pickDate: today, dateFrom: today, dateTo: today, page: 1 });
    this._cache = null;
    this.load(1, true);
  },

  prevPage() { if (this.data.page > 1) this.load(this.data.page - 1); },
  nextPage() { if (this.data.page < this.data.totalPages) this.load(this.data.page + 1); },

  _validate() {
    const f = this.data.form;
    const s = this.data.students;
    const c = this.data.courses;
    const errors = {};
    if (!s[f.studentIdx]) errors.student = true;
    if (!c[f.courseIdx]) errors.course = true;
    this.setData({ errors, formValid: Object.keys(errors).length === 0 });
  },

  closeForm() { this.setData({ showForm: false }); },

  submitRecord() {
    this._validate();
    if (!this.data.formValid) return;
    this.setData({ submitting: true });
    this._submitRecord();
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
        errors: {}, formValid: false,
        form: { studentIdx: 0, courseIdx: 0, record_date: ds, hours_consumed: 1, attendance: 'present', notes: '' }
      });
    }).catch(() => {
      wx.hideLoading();
      wx.showToast({ title: '加载失败', icon: 'none' });
    });
  },

  onFieldChange(e) {
    const field = e.currentTarget.dataset.field;
    if (!field) return;
    this.setData({ [`form.${field}`]: e.detail.value });
    this._validate();
  },

  onRadioChange(e) {
    this.setData({ 'form.attendance': e.detail.value });
    this._validate();
  },

  onFormDateChange(e) {
    this.setData({ 'form.record_date': e.detail.value });
    this._validate();
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
    this._validate();
  },

  onCourseChange(e) {
    this.setData({ 'form.courseIdx': parseInt(e.detail.value) });
    this._validate();
  },

  _submitRecord() {
    if (this.data.submitting) return;
    const { form, students, courses } = this.data;
    const sid = students[form.studentIdx] ? students[form.studentIdx].id : 0;
    const cid = courses[form.courseIdx] ? courses[form.courseIdx].id : 0;
    const body = JSON.stringify({
      student_id: sid, course_id: cid, record_date: form.record_date,
      hours_consumed: parseInt(form.hours_consumed) || 1,
      attendance: form.attendance, notes: form.notes
    });

    app.api('/api/records', { method: 'POST', body }).then((res) => {
      this.setData({ submitting: false });
      if (res.code === 200) {
        wx.showToast({ title: '消课成功', icon: 'success' });
        this.setData({ showForm: false });
        this.load(1, true);
      } else {
        wx.showToast({ title: res.message, icon: 'none' });
      }
    }).catch(() => {
      this.setData({ submitting: false });
      wx.showToast({ title: '网络错误', icon: 'none' });
    });
  },

  undoRecord(e) {
    const rid = e.currentTarget.dataset.rid;
    wx.showModal({
      title: '撤销记录',
      content: '确定撤销该签到记录吗？',
      success: (r) => {
        if (!r.confirm) return;
        app.api(`/api/records/${rid}`, { method: 'DELETE' }).then((res) => {
          if (res.code === 200) { wx.showToast({ title: '已撤销', icon: 'success' }); this.load(1, true); }
          else wx.showToast({ title: res.message, icon: 'none' });
        });
      }
    });
  },

  onNoteButtonTap(e) {
    if (e.detail.index === 0) { this.setData({ showNotes: false }); }
    else { this._addNote(); }
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

  _addNote() {
    const content = this.data.newNoteContent.trim();
    if (!content) return wx.showToast({ title: '请输入备注内容', icon: 'none' });

    app.api(`/api/records/${this.data.noteRecordId}/notes`, {
      method: 'POST',
      body: JSON.stringify({ content })
    }).then((res) => {
      if (res.code === 200) {
wx.showToast({ title: '已添加', icon: 'success' });
        this.showNotes({ currentTarget: { dataset: { rid: this.data.noteRecordId } } });
        this.load(1, true);
      } else {
        wx.showToast({ title: res.message, icon: 'none' });
      }
    });
  },

  /* 删除备注 F5 */
  deleteNote(e) {
    const nid = e.currentTarget.dataset.nid;
    wx.showModal({
      title: '删除备注',
      content: '确定删除该备注？',
      success: (r) => {
        if (!r.confirm) return;
        app.api(`/api/records/${this.data.noteRecordId}/notes/${nid}`, { method: 'DELETE' }).then((res) => {
          if (res.code === 200) {
            wx.showToast({ title: '已删除', icon: 'success' });
            this.showNotes({ currentTarget: { dataset: { rid: this.data.noteRecordId } } });
          } else {
            wx.showToast({ title: res.message, icon: 'none' });
          }
        });
      }
    });
  },

  noop() {}
});



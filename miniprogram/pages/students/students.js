const app = getApp();
const { validate } = require('../../utils/validator');

Page({
  data: {
    isAdmin: false,
    students: [],
    search: '',
    loading: true,
    showForm: false,
    editing: null,
    submitting: false,
    teachers: [],
    form: { name: '', gender: '男', grade: '', school: '', parent_name: '', parent_phone: '', notes: '', teacher_ids: [] },
    errors: {},
    formValid: false,

    /* WeUI 组件配置 */
    slideButtons: [
      { type: 'primary', text: '编辑', extClass: 'slide-edit' },
      { type: 'warn', text: '删除', extClass: 'slide-delete' }
    ]
  },

  onShow() {
    if (!app.globalData.token) { wx.reLaunch({ url: '/pages/login/login' }); return; }
    this.setData({ isAdmin: app.isAdmin() });
    this.load();
  },

  onPullDownRefresh() {
    this.load(true).then(() => wx.stopPullDownRefresh());
  },

  load(force) {
    if (!force && this._cache && Date.now() - this._cache.time < 30000) {
      this.setData({ students: this._cache.data, loading: false });
      return Promise.resolve();
    }
    this.setData({ loading: true });
    const q = this.data.search ? `?search=${encodeURIComponent(this.data.search)}` : '';
    return app.api(`/api/students${q}`).then((res) => {
      const list = res.data || [];
      this._cache = { time: Date.now(), data: list };
      this.setData({ students: list, loading: false });
    }).catch(() => {
      this.setData({ loading: false });
    });
  },

  /* mp-searchbar */
  onSearchBarInput(e) {
    const value = e.detail.value;
    this.setData({ search: value });
    clearTimeout(this._timer);
    this._timer = setTimeout(() => this.load(true), 400);
  },

  onSearchBarCancel() {
    this.setData({ search: '' });
    this.load(true);
  },

  /* 琛ㄥ崟鏍￠獙 */
  _validate() {
    const result = validate('student', { form: this.data.form });
    this.setData({ errors: result.errors, formValid: result.formValid });
  },

  /* 加载教师列表 */
  _loadTeachers(cb) {
    if (this.data.teachers.length > 0) { cb(); return; }
    app.api('/api/teachers').then(res => {
      this.setData({ teachers: (res.data || []).filter(t => t.status === 'active') });
      cb();
    }).catch(() => cb());
  },

  showAdd() {
    this._loadTeachers(() => {
      this.setData({
        showForm: true, editing: null, errors: {}, formValid: false,
        form: { name: '', gender: '男', grade: '', school: '', parent_name: '', parent_phone: '', notes: '', teacher_ids: [] }
      });
    });
  },

  /* mp-slideview 左滑按钮 */
  onSlideButtonTap(e) {
    const idx = e.detail.index; // 0=编辑, 1=删除
    const s = e.currentTarget.dataset.student;
    if (idx === 0) {
      this._loadTeachers(() => {
        this.setData({
          showForm: true, editing: s.id, errors: {},
          form: {
            name: s.name, gender: s.gender || '男', grade: s.grade || '',
            school: s.school || '', parent_name: s.parent_name || '',
            parent_phone: s.parent_phone || '', notes: s.notes || '',
            teacher_ids: s.teacher_ids || []
          }
        });
        this._validate();
      });
    } else {
      wx.showModal({
        title: '确认删除',
        content: `确定删除学生「${s.name}」吗？`,
        success: (r) => {
          if (!r.confirm) return;
          app.api(`/api/students/${s.id}`, { method: 'DELETE' }).then((res) => {
            if (res.code === 200) { wx.showToast({ title: '已删除', icon: 'success' }); this.load(true); }
            else wx.showToast({ title: res.message, icon: 'none' });
          });
        }
      });
    }
  },

  onGenderChange(e) {
    this.setData({ 'form.gender': e.detail.value });
  },

  onTeacherSelect(e) {
    const teacherId = parseInt(e.currentTarget.dataset.id);
    let teacherIds = [...this.data.form.teacher_ids];
    const index = teacherIds.indexOf(teacherId);
    if (index > -1) {
      teacherIds.splice(index, 1);
    } else {
      teacherIds.push(teacherId);
    }
    this.setData({ 'form.teacher_ids': teacherIds });
    this._validate();
  },

  preventBubble() {},

  closeForm() {
    this.setData({ showForm: false });
  },

  onFieldChange(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`form.${field}`]: e.detail.value });
    this._validate();
  },

  submitForm() {
    this._validate();
    if (!this.data.formValid) return;

    this.setData({ submitting: true });
    const f = this.data.form;
    const body = {
      name: f.name.trim(), gender: f.gender, grade: f.grade, school: f.school,
      parent_name: f.parent_name, parent_phone: f.parent_phone, notes: f.notes,
      teacher_ids: f.teacher_ids || []
    };
    const method = this.data.editing ? 'PUT' : 'POST';
    const url = this.data.editing ? `/api/students/${this.data.editing}` : '/api/students';

    app.api(url, { method, body: JSON.stringify(body) }).then((res) => {
      this.setData({ submitting: false });
      if (res.code === 200) {
        wx.showToast({ title: res.message || '已保存', icon: 'success' });
        this.setData({ showForm: false });
        this.load(true);
      } else {
        wx.showToast({ title: res.message, icon: 'none' });
      }
    }).catch(() => {
      this.setData({ submitting: false });
      wx.showToast({ title: '网络错误，请重试', icon: 'none' });
    });
  },

  noop() {}
});


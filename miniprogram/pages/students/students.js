const app = getApp();

Page({
  data: {
    isAdmin: false,
    students: [],
    search: '',
    loading: true,
    showForm: false,
    editing: null,
    form: { name: '', gender: '男', grade: '', school: '', parent_name: '', parent_phone: '', notes: '' }
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
      const list = res.code === 200 ? (res.data || []) : [];
      this._cache = { time: Date.now(), data: list };
      this.setData({ students: list, loading: false });
    }).catch(() => {
      this.setData({ loading: false });
    });
  },

  /** 自定义输入框 bindinput 事件 */
  onSearch(e) {
    const value = e.detail.value;
    this.setData({ search: value });
    clearTimeout(this._timer);
    this._timer = setTimeout(() => this.load(true), 400);
  },

  onClearSearch() {
    this.setData({ search: '' });
    this.load(true);
  },

  showAdd() {
    this.setData({
      showForm: true, editing: null,
      form: { name: '', gender: '男', grade: '', school: '', parent_name: '', parent_phone: '', notes: '' }
    });
  },

  showEdit(e) {
    const s = e.currentTarget.dataset.student;
    this.setData({
      showForm: true, editing: s.id,
      form: {
        name: s.name, gender: s.gender || '男', grade: s.grade || '',
        school: s.school || '', parent_name: s.parent_name || '',
        parent_phone: s.parent_phone || '', notes: s.notes || ''
      }
    });
  },

  closeForm() {
    this.setData({ showForm: false });
  },

  onFieldChange(e) {
    const field = e.currentTarget.dataset.field;
    const value = e.detail.value;
    this.setData({ [`form.${field}`]: value });
  },

  /** 提交表单（替代原 mp-dialog 的 bindbuttontap） */
  submitForm() {
    const f = this.data.form;
    if (!f.name.trim()) { wx.showToast({ title: '请输入姓名', icon: 'none' }); return; }

    const body = {
      name: f.name.trim(), gender: f.gender, grade: f.grade, school: f.school,
      parent_name: f.parent_name, parent_phone: f.parent_phone, notes: f.notes
    };
    const method = this.data.editing ? 'PUT' : 'POST';
    const url = this.data.editing ? `/api/students/${this.data.editing}` : '/api/students';

    app.api(url, { method, body: JSON.stringify(body) }).then((res) => {
      if (res.code === 200) {
        wx.showToast({ title: res.message || '已保存', icon: 'success' });
        this.setData({ showForm: false });
        this.load(true);
      } else {
        wx.showToast({ title: res.message, icon: 'none' });
      }
    });
  },

  deleteStudent(e) {
    const s = e.currentTarget.dataset.student;
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
  },

  noop() {}
});

Component({
  properties: {
    show: Boolean,
    title: String,
    confirmText: { type: String, value: '保存' },
    confirmDisabled: { type: Boolean, value: false },
    submitting: { type: Boolean, value: false }
  },

  data: {
    _buttons: []
  },

  observers: {
    'confirmText, confirmDisabled, submitting'(text, disabled, submitting) {
      this._updateButtons(disabled, text, submitting);
    }
  },

  lifetimes: {
    attached() {
      this._updateButtons(this.data.confirmDisabled, this.data.confirmText, this.data.submitting);
    }
  },

  methods: {
    _updateButtons(disabled, text, submitting) {
      let label;
      if (submitting) {
        label = '保存中...';
      } else if (disabled) {
        label = '请完善信息';
      } else {
        label = text || '保存';
      }
      this.setData({
        _buttons: [
          { type: 'default', text: '取消' },
          { type: 'primary', text: label }
        ]
      });
    },

    onButtonTap(e) {
      const idx = e.detail.index;
      if (idx === 0) {
        this.triggerEvent('cancel');
      } else if (!this.data.confirmDisabled && !this.data.submitting) {
        this.triggerEvent('confirm');
      }
    }
  }
});

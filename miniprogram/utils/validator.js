/**
 * 表单验证器 - 可复用的业务表单校验规则
 * 各页面通过 validator.validate(type, data) 调用
 */

/**
 * 学生表单验证
 */
function validateStudent(form) {
  const errors = {};
  if (!form.name || !form.name.trim()) errors.name = true;
  // 家长电话格式校验（非必填，填了必须合法）
  const phone = (form.parent_phone || '').trim();
  if (phone && !/^1[3-9]\d{9}$/.test(phone)) errors.parent_phone = true;
  return { errors, formValid: Object.keys(errors).length === 0 };
}

/**
 * 排课表单验证
 */
function validateSchedule(form, students, courses) {
  const errors = {};
  if (!students[form.studentIdx]) errors.student = true;
  if (!courses[form.courseIdx]) errors.course = true;
  if (!form.schedule_date) errors.schedule_date = true;
  if (form.start_time && form.end_time && form.start_time >= form.end_time) {
    errors.time_range = true;
  }
  return { errors, formValid: Object.keys(errors).length === 0 };
}

/**
 * 消课记录表单验证
 */
function validateRecord(form, students, courses) {
  const errors = {};
  if (!students[form.studentIdx]) errors.student = true;
  if (!courses[form.courseIdx]) errors.course = true;
  if (!form.record_date) errors.record_date = true;
  const hours = parseInt(form.hours_consumed);
  if (!hours || hours < 1) errors.hours = true;
  return { errors, formValid: Object.keys(errors).length === 0 };
}

/**
 * 登录表单验证
 */
function validateLogin(form) {
  const errors = {};
  if (!form.username || !form.username.trim()) errors.username = true;
  if (!form.password || !form.password.trim()) errors.password = true;
  return { errors, formValid: Object.keys(errors).length === 0 };
}

/**
 * 批量验证（传入 { type, data }）
 */
function validate(type, data) {
  const { form, students, courses } = data;
  switch (type) {
    case 'student':
      return validateStudent(form);
    case 'schedule':
      return validateSchedule(form, students || [], courses || []);
    case 'record':
      return validateRecord(form, students || [], courses || []);
    case 'login':
      return validateLogin(form);
    default:
      return { errors: {}, formValid: false };
  }
}

module.exports = { validate, validateStudent, validateSchedule, validateRecord, validateLogin };

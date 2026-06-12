/**
 * 课消管理系统 v3.0 - 前端应用
 * 新增：登录鉴权、角色控制、备份恢复、用户管理
 */
// ==================== 全局状态 ====================
// PC 端和小程序端直连 CloudBase CloudRun，共享同一套 API 和数据库
// 小程序：使用 miniprogram/app.js 中的 BASE_URL 直连 CloudBase
const API_BASE = 'https://tutoring-269057-7-1316430031.sh.run.tcloudbase.com';
const STATE = { currentPage: 'dashboard', students: [], teachers: [], courses: [], editingId: null, token: null, user: null };

// ==================== 工具 ====================
function $(s) { return document.querySelector(s); }
function $$(s) { return document.querySelectorAll(s); }

async function api(url, options = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (STATE.token) headers['Authorization'] = `Bearer ${STATE.token}`;
    let res;
    try {
        res = await fetch(API_BASE + url, { headers, ...options });
    } catch (e) {
        const msg = '网络连接失败，请检查网络或稍后重试';
        toast(msg, 'error');
        throw new Error(msg);
    }
    // 检测响应是否为 JSON
    const ct = res.headers.get('content-type') || '';
    if (!ct.includes('application/json')) {
        const text = await res.text();
        let msg;
        if (res.status === 503 || text.includes('503')) {
            msg = '服务器正在启动中，请稍后重试（约30秒）';
        } else if (res.status >= 500) {
            msg = '服务器错误(' + res.status + ')，请稍后重试';
        } else {
            msg = '服务器响应异常(' + res.status + ')';
        }
        toast(msg, 'error');
        throw new Error(msg);
    }
    // 安全解析JSON（防止冷启动返回HTML伪装成JSON Content-Type）
    let text, json;
    try {
        text = await res.text();
        json = JSON.parse(text);
    } catch(e) {
        const msg = '服务器响应格式异常，请稍后重试';
        toast(msg, 'error');
        throw new Error(msg);
    }
    if (json.code === 401) { doLogout(); throw new Error('登录已过期'); }
    return json;
}

function apiData(json) { return json.data !== undefined ? json.data : json; }

function toast(msg, type = 'info') {
    const c = $('#toastContainer'); const el = document.createElement('div');
    el.className = `toast toast-${type}`; el.textContent = msg; c.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity 0.3s'; }, 2500);
    setTimeout(() => el.remove(), 2800);
}

function isAdmin() { return STATE.user && STATE.user.role === 'admin'; }
function isTeacher() { return STATE.user && STATE.user.role === 'teacher'; }
function isParent() { return STATE.user && STATE.user.role === 'parent'; }

// ==================== 认证 ====================
async function doLogin() {
    const u = $('#loginUsername').value.trim(), p = $('#loginPassword').value;
    if (!u || !p) { showLoginError('请输入用户名和密码'); return; }
    try {
        const json = await api('/api/auth/login', { method: 'POST',
            body: JSON.stringify({ username: u, password: p }) });
        if (json.code !== 200) { showLoginError(json.message); return; }
        STATE.token = json.data.token; STATE.user = json.data.user;
        localStorage.setItem('tutoring_token', STATE.token);
        localStorage.setItem('tutoring_user', JSON.stringify(STATE.user));
        localStorage.setItem('tutoring_login_time', Date.now().toString());
        $('#loginOverlay').style.display = 'none';
        $('#mainApp').style.display = 'flex';
        updateUIByRole(); updateUserDisplay();
        switchPage('dashboard').catch(e => { toast('仪表盘加载失败: ' + e.message, 'error'); });
    } catch (e) { showLoginError('登录失败: ' + e.message); }
}

function doLogout() {
    api('/api/auth/logout', { method: 'POST' }).catch(() => {});
    STATE.token = null; STATE.user = null;
    localStorage.removeItem('tutoring_token'); localStorage.removeItem('tutoring_user');
    localStorage.removeItem('tutoring_login_time');
    $('#mainApp').style.display = 'none'; $('#loginOverlay').style.display = 'flex';
    $('#loginPassword').value = '';
}

function showLoginError(msg) { const el = $('#loginError'); el.textContent = msg; el.style.display = 'block'; }



function updateUserDisplay() {
    if (!STATE.user) return;
    const roleMap = { admin: '管理员', teacher: '教师', parent: '家长' };
    $('#userInfoDisplay').textContent = `${STATE.user.real_name} (${roleMap[STATE.user.role] || STATE.user.role})`;
}

function updateUIByRole() {
    const adminOnly = ['#navStudents btnAddStudent', '#navTeachers btnAddTeacher', '#navCourses btnAddCourse',
        '#navEnrollments btnAddEnrollment', '#navUsers', '#navBackup', '#navPermissions',
        '#btnAddStudent', '#btnAddTeacher',
        '#btnAddCourse', '#btnAddEnrollment'];
    const teacherParentHide = ['#navStudents', '#navTeachers', '#navUsers', '#navBackup'];

    if (isAdmin()) {
        // 显示所有
        document.querySelectorAll('[id^="nav"]').forEach(el => el.style.display = '');
        document.querySelectorAll('[id^="btnAdd"]').forEach(el => { if (el) el.style.display = ''; });
        if ($('#btnBatchConsume')) $('#btnBatchConsume').style.display = '';
        if ($('#btnDirectRecord')) $('#btnDirectRecord').style.display = '';
    } else if (isTeacher()) {
        // 隐藏管理员专属
        teacherParentHide.forEach(s => { const el = $(s); if (el) el.style.display = 'none'; });
        document.querySelectorAll('[id^="btnAdd"]').forEach(el => { if (el) el.style.display = 'none'; });
        // 显示课程和排课
        if ($('#navCourses')) $('#navCourses').style.display = '';
        if ($('#navSchedules')) $('#navSchedules').style.display = '';
        // 可以消课
        if ($('#btnBatchConsume')) $('#btnBatchConsume').style.display = '';
        if ($('#btnDirectRecord')) $('#btnDirectRecord').style.display = '';
    } else if (isParent()) {
        // 只显示仪表盘、课程查看、课时记录
        teacherParentHide.forEach(s => { const el = $(s); if (el) el.style.display = 'none'; });
        ['#navSchedules','#navCourses','#navEnrollments'].forEach(s => { const el = $(s); if (el) el.style.display = 'none'; });
        document.querySelectorAll('[id^="btnAdd"]').forEach(el => { if (el) el.style.display = 'none'; });
        if ($('#btnBatchConsume')) $('#btnBatchConsume').style.display = 'none';
        if ($('#btnDirectRecord')) $('#btnDirectRecord').style.display = 'none';
    }
}

function tryAutoLogin() {
    const tok = localStorage.getItem('tutoring_token'), usr = localStorage.getItem('tutoring_user');
    if (!tok || !usr) return;
    if (!checkIdleTimeout()) {
        localStorage.removeItem('tutoring_token');
        localStorage.removeItem('tutoring_user');
        localStorage.removeItem('tutoring_login_time');
        return;
    }
    STATE.token = tok; STATE.user = JSON.parse(usr);
    api('/api/auth/me').then(function(res) {
        if (res.code === 200) {
            STATE.user = res.data;
            $('#loginOverlay').style.display = 'none'; $('#mainApp').style.display = 'flex';
            updateUIByRole(); updateUserDisplay();
            switchPage('dashboard').catch(function(e) { toast('仪表盘加载失败: ' + e.message, 'error'); });
            resetIdleTimer();
        } else { localStorage.removeItem('tutoring_token'); localStorage.removeItem('tutoring_user'); localStorage.removeItem('tutoring_login_time'); }
    }).catch(function() {});
}


// ==================== 空闲超时控制（5分钟无操作退出）====================
const IDLE_TIMEOUT_MS = 5 * 60 * 1000;
let idleTimer = null;

function resetIdleTimer() {
    localStorage.setItem('tutoring_login_time', Date.now().toString());
    if (idleTimer) {
        clearTimeout(idleTimer);
    }
    if (STATE.token) {
        idleTimer = setTimeout(function() {
            if (STATE.token) {
                toast('已登录超时，请重新登录', 'info');
                doLogout();
            }
        }, IDLE_TIMEOUT_MS);
    }
}

function checkIdleTimeout() {
    var loginTimeStr = localStorage.getItem('tutoring_login_time');
    if (!loginTimeStr) return false;
    var elapsed = Date.now() - parseInt(loginTimeStr, 10);
    if (elapsed > IDLE_TIMEOUT_MS) {
        return false;
    }
    return true;
}

function setupIdleListener() {
    var events = ['mousedown', 'keydown', 'touchstart', 'scroll', 'mousemove'];
    events.forEach(function(evt) {
        document.addEventListener(evt, resetIdleTimer, { capture: true, passive: true });
    });
}

// ==================== 导航 ====================
function initNavigation() {
    $$('.nav-item').forEach(item => item.addEventListener('click', () => switchPage(item.dataset.page)));
}

function switchPage(page) {
    STATE.currentPage = page;
    $$('.nav-item').forEach(i => i.classList.remove('active'));
    const navItem = $(`.nav-item[data-page="${page}"]`);
    if (navItem) navItem.classList.add('active');
    $$('.page').forEach(p => p.classList.remove('active'));
    const pg = $(`#page-${page}`); if (pg) pg.classList.add('active');

    const titles = { dashboard: '📊 首页仪表盘', students: '👨‍🎓 学生管理', teachers: '👩‍🏫 教师管理',
        courses: '📖 课程管理', enrollments: '📝 报名管理', schedules: '📅 排课管理',
        records: '✅ 课时记录', users: '👥 用户管理', backup: '💾 备份恢复', permissions: '🔐 权限管理' };
    $('#pageTitle').textContent = titles[page] || '';

    const loaders = { dashboard: loadDashboard, students: loadStudents, teachers: loadTeachers,
        courses: loadCourses, enrollments: loadEnrollments, schedules: loadSchedules,
        records: () => loadRecords(), users: loadUsers, backup: loadBackup, permissions: loadPermissions };
    const p = loaders[page] ? loaders[page]() : null;
    return p;
}

// ==================== 弹窗 ====================
function showModal(title, bodyHtml, footerHtml = '', size = '') {
    $('#modalContainer').innerHTML = `<div class="modal-overlay" onclick="if(event.target===this)closeModal()"><div class="modal ${size}"><div class="modal-header"><h3>${title}</h3><button class="modal-close" onclick="closeModal()">✕</button></div><div class="modal-body">${bodyHtml}</div>${footerHtml?`<div class="modal-footer">${footerHtml}</div>`:''}</div></div>`;
}
function closeModal() { $('#modalContainer').innerHTML = ''; }

// ==================== 仪表盘 ====================
async function loadDashboard() {
    try {
        const d = apiData(await api('/api/dashboard'));
        $('#dashboardStats').innerHTML = `
            <div class="stat-card"><div class="stat-icon blue">👨‍🎓</div><div class="stat-info"><div class="stat-value">${d.total_students}</div><div class="stat-label">在读学生</div></div></div>
            <div class="stat-card"><div class="stat-icon green">👩‍🏫</div><div class="stat-info"><div class="stat-value">${d.total_teachers}</div><div class="stat-label">在职教师</div></div></div>
            <div class="stat-card"><div class="stat-icon purple">📖</div><div class="stat-info"><div class="stat-value">${d.total_courses}</div><div class="stat-label">开设课程</div></div></div>
            <div class="stat-card"><div class="stat-icon orange">📅</div><div class="stat-info"><div class="stat-value">${d.today_count}</div><div class="stat-label">今日课程</div></div></div>
            <div class="stat-card"><div class="stat-icon red">✅</div><div class="stat-info"><div class="stat-value">${d.today_consumed}</div><div class="stat-label">今日已消</div></div></div>
            <div class="stat-card"><div class="stat-icon blue">⏳</div><div class="stat-info"><div class="stat-value">${d.total_remaining}</div><div class="stat-label">剩余课时</div></div></div>`;

        const maxVal = Math.max(1, ...d.daily_stats.map(x => x.total));
        $('#weekChart').innerHTML = d.daily_stats.map(x => {
            const h = (x.total / maxVal * 140) || 4;
            return `<div class="chart-bar-wrap"><div class="chart-bar-value">${x.total}</div><div class="chart-bar" style="height:${h}px" title="${x.record_date}: ${x.total}课时"></div><div class="chart-bar-label">${(x.record_date||'').slice(5)}</div></div>`;
        }).join('');

        $('#courseRanking').innerHTML = d.course_ranking.length === 0 ? '<div class="empty-state"><div class="empty-text">暂无数据</div></div>'
            : d.course_ranking.map((c,i) => `<div style="display:flex;align-items:center;padding:8px 0;border-bottom:1px solid var(--gray-100);gap:10px;"><span style="font-weight:700;color:var(--primary);">#${i+1}</span><span style="flex:1;font-size:13px;">${c.name}</span><span class="font-bold font-mono">${c.total_hours} 课时</span></div>`).join('');

        const today = new Date();
        $('#todayDate').textContent = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
        $('#todayScheduleTable').innerHTML = d.today_schedules.length === 0 ? '<tr><td colspan="8"><div class="empty-state"><div class="empty-text">今日暂无排课</div></div></td></tr>'
            : d.today_schedules.map(s => {
                const st = s.status==='completed'?'<span class="tag tag-success">已完成</span>':s.status==='cancelled'?'<span class="tag tag-danger">已取消</span>':'<span class="tag tag-info">待上课</span>';
                const act = s.status==='scheduled'?`<button class="btn btn-success btn-xs" onclick="checkinSchedule(${s.id})">签到消课</button>`:'';
                return `<tr><td>${s.start_time} - ${s.end_time}</td><td class="font-bold">${s.student_name}</td><td>${s.course_name}</td><td>${s.subject||'-'}</td><td>${s.teacher_name||'-'}</td><td>${s.hours}</td><td>${st}</td><td>${act}</td></tr>`;
            }).join('');
    } catch (e) {
        toast('加载失败，请检查网络连接', 'error');
        $('#dashboardStats').innerHTML = '<div class="empty-state"><div class="empty-text" style="font-size:16px;">⚠️ 数据加载失败</div><div style="color:#9CA3AF;margin-top:8px;">请检查网络连接或稍后重试</div></div>';
        $('#weekChart').innerHTML = '';
        $('#courseRanking').innerHTML = '';
        $('#todayScheduleTable').innerHTML = '<tr><td colspan="8"><div class="empty-state"><div class="empty-text">暂无排课数据</div></div></td></tr>';
    }
}

async function checkinSchedule(sid) {
    if (!confirm('确认签到并消课？')) return;
    const res = await api('/api/records', { method: 'POST', body: JSON.stringify({ schedule_id: sid }) });
    toast(res.message || '完成', res.code===200?'success':'error'); loadDashboard();
}

// ==================== 学生管理 ====================
async function loadStudents() {
    try {
        const s = $('#studentSearch')?.value || '';
        STATE.students = apiData(await api(`/api/students?search=${encodeURIComponent(s)}`));
        const tbody = $('#studentTable');
        if (!tbody) return;
        if (STATE.students.length === 0) { tbody.innerHTML = '<tr><td colspan="10"><div class="empty-state"><div class="empty-text">暂无数据</div></div></td></tr>'; return; }
        tbody.innerHTML = STATE.students.map(s => {
            const cn = (s.enrollments||[]).map(e=>e.course_name).join('、')||'-';
            const r = s.total_remaining??0;
            const tn = s.teacher_names||'-';
            return `<tr><td class="font-bold">${s.name}</td><td>${s.gender||'-'}</td><td>${s.grade||'-'}</td><td>${s.school||'-'}</td><td>${tn}</td><td>${s.parent_name||'-'}</td><td>${s.parent_phone||'-'}</td><td>${cn}</td><td class="font-bold ${r<=2?'text-danger':'text-success'}">${r}</td><td>${isAdmin()?`<button class="btn btn-outline btn-xs" onclick="viewStudent(${s.id})">详情</button> <button class="btn btn-outline btn-xs" onclick="showStudentModal(${s.id})">编辑</button> <button class="btn btn-danger btn-xs" onclick="deleteStudent(${s.id})">停用</button>`:`<button class="btn btn-outline btn-xs" onclick="viewStudent(${s.id})">详情</button>`}</td></tr>`;
        }).join('');
    } catch(e) {
        console.error('loadStudents error:', e);
        toast('加载学生列表失败', 'error');
    }
}

async function viewStudent(sid) {
    const s = apiData(await api(`/api/students/${sid}`));
    const eh = (s.enrollments||[]).map(e=>`<tr><td>${e.course_name}</td><td>${e.subject||'-'}</td><td>${e.purchased_hours}</td><td>${e.consumed_hours}</td><td class="font-bold ${e.remaining_hours<=2?'text-danger':''}">${e.remaining_hours}</td></tr>`).join('');
    const rh = (s.recent_records||[]).slice(0,10).map(r=>`<tr><td>${r.record_date}</td><td>${r.course_name}</td><td>${r.teacher_name||'-'}</td><td>${r.hours_consumed}</td><td>${r.remaining_after}</td><td>${r.attendance==='present'?'<span class="tag tag-success">出勤</span>':'<span class="tag tag-danger">缺勤</span>'}</td></tr>`).join('')||'<tr><td colspan="6">暂无</td></tr>';
    showModal(`学生详情 - ${s.name}`, `
        <div class="detail-grid">
            <div class="detail-item"><div class="detail-label">姓名</div><div class="detail-value">${s.name}</div></div>
            <div class="detail-item"><div class="detail-label">性别</div><div class="detail-value">${s.gender||'-'}</div></div>
            <div class="detail-item"><div class="detail-label">年级</div><div class="detail-value">${s.grade||'-'}</div></div>
            <div class="detail-item"><div class="detail-label">学校</div><div class="detail-value">${s.school||'-'}</div></div>
            <div class="detail-item"><div class="detail-label">家长</div><div class="detail-value">${s.parent_name||'-'}</div></div>
            <div class="detail-item"><div class="detail-label">电话</div><div class="detail-value">${s.parent_phone||'-'}</div></div>
            <div class="detail-item"><div class="detail-label">关联教师</div><div class="detail-value">${s.teacher_names||'未关联'}</div></div>
        </div>
        <h4 style="margin:16px 0 8px;">📝 报名课程</h4><table><thead><tr><th>课程</th><th>科目</th><th>购买</th><th>已消</th><th>剩余</th></tr></thead><tbody>${eh}</tbody></table>
        <h4 style="margin:16px 0 8px;">📋 近期消课</h4><table><thead><tr><th>日期</th><th>课程</th><th>教师</th><th>消耗</th><th>剩余</th><th>出勤</th></tr></thead><tbody>${rh}</tbody></table>
    `, '', 'modal-lg');
}

async function showStudentModal(id = null) {
    STATE.editingId = id; const s = id ? STATE.students.find(st=>st.id===id) : null;
    // 确保教师列表已加载
    if (!STATE.teachers || STATE.teachers.length === 0) {
        try { STATE.teachers = apiData(await api('/api/teachers')); } catch(e) { STATE.teachers = []; }
    }
    const existingTids = s?.teacher_ids || [];
    const teacherCheckboxes = STATE.teachers.map(t => `<label style="display:inline-flex;align-items:center;margin-right:16px;cursor:pointer;"><input type="checkbox" class="fTeacherCb" value="${t.id}" ${existingTids.includes(t.id)?'checked':''} style="margin-right:4px;">${t.name}</label>`).join('');
    showModal(id?'编辑学生':'添加学生', `
        <div class="form-row"><div class="form-group"><label>姓名*</label><input type="text" class="form-input" id="fName" value="${s?.name||''}"></div><div class="form-group"><label>性别</label><select class="form-select" id="fGender"><option value="男" ${s?.gender==='男'?'selected':''}>男</option><option value="女" ${s?.gender==='女'?'selected':''}>女</option></select></div></div>
        <div class="form-row"><div class="form-group"><label>年级</label><input type="text" class="form-input" id="fGrade" value="${s?.grade||''}"></div><div class="form-group"><label>学校</label><input type="text" class="form-input" id="fSchool" value="${s?.school||''}"></div></div>
        <div class="form-row"><div class="form-group"><label>家长姓名</label><input type="text" class="form-input" id="fParentName" value="${s?.parent_name||''}"></div><div class="form-group"><label>家长电话</label><input type="text" class="form-input" id="fParentPhone" value="${s?.parent_phone||''}"></div></div>
        <div class="form-group"><label>地址</label><input type="text" class="form-input" id="fAddress" value="${s?.address||''}"></div>
        <div class="form-group"><label>关联教师</label><div style="padding:8px 0;">${teacherCheckboxes || '<span class="text-muted">暂无教师，请先添加教师</span>'}</div></div>
        <div class="form-group"><label>备注</label><textarea class="form-textarea" id="fNotes" rows="2">${s?.notes||''}</textarea></div>
    `, `<button class="btn btn-outline" onclick="closeModal()">取消</button><button class="btn btn-primary" onclick="saveStudent()">保存</button>`);
}

async function saveStudent() {
    const tids = [...document.querySelectorAll('.fTeacherCb:checked')].map(cb => parseInt(cb.value));
    const d = { name: $('#fName').value.trim(), gender: $('#fGender').value, grade: $('#fGrade').value.trim(), school: $('#fSchool').value.trim(), parent_name: $('#fParentName').value.trim(), parent_phone: $('#fParentPhone').value.trim(), address: $('#fAddress').value.trim(), notes: $('#fNotes').value.trim(), teacher_ids: tids };
    if (!d.name) { toast('请输入姓名', 'error'); return; }
    const res = await api(STATE.editingId?`/api/students/${STATE.editingId}`:'/api/students', { method: STATE.editingId?'PUT':'POST', body: JSON.stringify(d) });
    toast(res.message||'成功','success'); closeModal(); loadStudents();
}
async function deleteStudent(id) { if(!confirm('确定停用?'))return; await api(`/api/students/${id}`,{method:'DELETE'}); toast('已停用','success'); loadStudents(); }

// ==================== 教师管理 ====================
async function loadTeachers() {
    const s = $('#teacherSearch')?.value||''; STATE.teachers = apiData(await api(`/api/teachers?search=${encodeURIComponent(s)}`));
    const tbody = $('#teacherTable');
    if (STATE.teachers.length===0) { tbody.innerHTML='<tr><td colspan="6"><div class="empty-state"><div class="empty-text">暂无数据</div></div></td></tr>'; return; }
    tbody.innerHTML = STATE.teachers.map(t=>`<tr><td class="font-bold">${t.name}</td><td>${t.gender||'-'}</td><td>${t.phone||'-'}</td><td>${t.subjects||'-'}</td><td>${t.course_count||0}门</td><td>${isAdmin()?`<button class="btn btn-outline btn-xs" onclick="showTeacherModal(${t.id})">编辑</button> <button class="btn btn-danger btn-xs" onclick="deleteTeacher(${t.id})">停用</button>`:''}</td></tr>`).join('');
}

function showTeacherModal(id=null) {
    STATE.editingId=id; const t=id?STATE.teachers.find(tc=>tc.id===id):null;
    showModal(id?'编辑教师':'添加教师', `
        <div class="form-row"><div class="form-group"><label>姓名*</label><input type="text" class="form-input" id="fTName" value="${t?.name||''}"></div><div class="form-group"><label>性别</label><select class="form-select" id="fTGender"><option value="男" ${t?.gender==='男'?'selected':''}>男</option><option value="女" ${t?.gender==='女'?'selected':''}>女</option></select></div></div>
        <div class="form-group"><label>电话</label><input type="text" class="form-input" id="fTPhone" value="${t?.phone||''}"></div>
        <div class="form-group"><label>擅长科目</label><input type="text" class="form-input" id="fTSubjects" value="${t?.subjects||''}" placeholder="逗号分隔"></div>
        <div class="form-group"><label>备注</label><textarea class="form-textarea" id="fTNotes" rows="2">${t?.notes||''}</textarea></div>
    `, '<button class="btn btn-outline" onclick="closeModal()">取消</button><button class="btn btn-primary" onclick="saveTeacher()">保存</button>');
}

async function saveTeacher() {
    const d={name:$('#fTName').value.trim(),gender:$('#fTGender').value,phone:$('#fTPhone').value.trim(),subjects:$('#fTSubjects').value.trim(),notes:$('#fTNotes').value.trim()};
    if(!d.name){toast('请输入姓名','error');return;}
    const res=await api(STATE.editingId?`/api/teachers/${STATE.editingId}`:'/api/teachers',{method:STATE.editingId?'PUT':'POST',body:JSON.stringify(d)});
    toast(res.message||'成功','success'); closeModal(); loadTeachers();
}
async function deleteTeacher(id){if(!confirm('确定停用?'))return;await api(`/api/teachers/${id}`,{method:'DELETE'});toast('已停用','success');loadTeachers();}

// ==================== 课程管理 ====================
async function loadCourses() {
    try {
            const s=$('#courseSearch')?.value||''; STATE.courses=apiData(await api(`/api/courses?search=${encodeURIComponent(s)}`));
            const tbody=$('#courseTable');
            if (!tbody) return;
            if(STATE.courses.length===0){tbody.innerHTML='<tr><td colspan="6"><div class="empty-state"><div class="empty-text">暂无数据</div></div></td></tr>';return;}
        const showPrice = isAdmin();
        tbody.innerHTML=STATE.courses.map(c=>`<tr><td class="font-bold">${c.name}</td><td>${c.subject||'-'}</td><td>${c.teacher_names||'-'}</td><td>${showPrice?(c.price_per_hour||0):'***'}</td><td>${c.student_count||0}人</td><td>${isAdmin()?`<button class="btn btn-outline btn-xs" onclick="showCourseModal(${c.id})">编辑</button> <button class="btn btn-danger btn-xs" onclick="deleteCourse(${c.id})">停用</button>`:''}</td></tr>`).join('');
    } catch(e) { console.error("loadCourses error:", e); toast("加载课程失败", "error"); }
}

async function showCourseModal(id=null) {
    STATE.editingId=id; const c=id?STATE.courses.find(cs=>cs.id===id):null;
    let teachers=[]; try{teachers=apiData(await api('/api/teachers'));}catch(e){}
    const etids=c?.teacher_ids||[];
    const tcb=teachers.map(t=>`<label style="display:inline-flex;align-items:center;gap:4px;margin-right:12px;margin-bottom:6px;cursor:pointer;"><input type="checkbox" class="course-teacher-cb" value="${t.id}" ${etids.includes(t.id)?'checked':''}>${t.name}</label>`).join('');
    showModal(id?'编辑课程':'添加课程', `
        <div class="form-row"><div class="form-group"><label>课程名称*</label><input type="text" class="form-input" id="fCName" value="${c?.name||''}"></div><div class="form-group"><label>科目</label><input type="text" class="form-input" id="fCSubject" value="${c?.subject||''}"></div></div>
        <div class="form-group"><label>任课教师（可多选）</label><div style="padding:8px;border:1px solid var(--gray-200);border-radius:6px;max-height:150px;overflow-y:auto;">${tcb||'暂无教师'}</div></div>
        <div class="form-row"><div class="form-group"><label>单价</label><input type="number" class="form-input" id="fCPrice" value="${c?.price_per_hour||0}" step="0.01"></div><div class="form-group"><label>总课时</label><input type="number" class="form-input" id="fCTotalHours" value="${c?.total_hours||0}"></div></div>
        <div class="form-group"><label>备注</label><textarea class="form-textarea" id="fCNotes" rows="2">${c?.notes||''}</textarea></div>
    `, '<button class="btn btn-outline" onclick="closeModal()">取消</button><button class="btn btn-primary" onclick="saveCourse()">保存</button>');
}

async function saveCourse() {
    const tids=[...$$('.course-teacher-cb:checked')].map(cb=>parseInt(cb.value));
    const d={name:$('#fCName').value.trim(),subject:$('#fCSubject').value.trim(),teacher_ids:tids,price_per_hour:parseFloat($('#fCPrice').value)||0,total_hours:parseInt($('#fCTotalHours').value)||0,notes:$('#fCNotes').value.trim()};
    if(!d.name){toast('请输入课程名称','error');return;}
    const res=await api(STATE.editingId?`/api/courses/${STATE.editingId}`:'/api/courses',{method:STATE.editingId?'PUT':'POST',body:JSON.stringify(d)});
    toast(res.message||'成功','success');closeModal();loadCourses();
}
async function deleteCourse(id){if(!confirm('确定停用?'))return;await api(`/api/courses/${id}`,{method:'DELETE'});toast('已停用','success');loadCourses();}

// ==================== 报名管理 ====================
async function loadEnrollments() {
    try {
    const data=apiData(await api('/api/enrollments'));
    const tbody=$('#enrollmentTable');
    const showAmount = isAdmin();
    if(data.length===0){tbody.innerHTML='<tr><td colspan="11"><div class="empty-state"><div class="empty-text">暂无数据</div></div></td></tr>';return;}
    tbody.innerHTML=data.map(e=>`<tr><td class="font-bold">${e.student_name}</td><td>${e.grade||'-'}</td><td>${e.course_name}</td><td>${e.subject||'-'}</td><td>${e.teacher_names||'-'}</td><td>${e.purchased_hours}</td><td>${e.consumed_hours}</td><td class="font-bold ${(e.remaining_hours??0)<=2?'text-danger':'text-success'}">${e.remaining_hours}</td><td>${showAmount?(e.amount_paid||0):'***'}</td><td>${e.enrolled_date||'-'}</td><td>${isAdmin()?`<button class="btn btn-outline btn-xs" onclick="showEnrollmentModal(${e.id})">编辑</button> <button class="btn btn-danger btn-xs" onclick="deleteEnrollment(${e.id})">取消</button>`:''}</td></tr>`).join('');
    } catch(e) { console.error('loadEnrollments error:', e); toast('加载报名失败', 'error'); }
}

async function showEnrollmentModal(id=null) {
    STATE.editingId=id; let existing=null;
    if(id){try{const all=apiData(await api('/api/enrollments'));existing=(all||[]).find(e=>Number(e.id)===Number(id));if(!existing){toast('未找到记录','error');return;}}catch(e){toast('加载失败','error');return;}}
    let students=[],courses=[];try{students=apiData(await api('/api/students'));courses=apiData(await api('/api/courses'));}catch(e){}
    const ss=existing?existing.student_id:''; const sc=existing?existing.course_id:'';
    showModal(id?'编辑报名':'新增报名', `
        <div class="form-row"><div class="form-group"><label>学生*</label><select class="form-select" id="fEStudent">${students.map(s=>`<option value="${s.id}" ${Number(ss)===Number(s.id)?'selected':''}>${s.name}</option>`).join('')}</select></div><div class="form-group"><label>课程*</label><select class="form-select" id="fECourse">${courses.map(c=>`<option value="${c.id}" ${Number(sc)===Number(c.id)?'selected':''}>${c.name}-${c.subject||''}</option>`).join('')}</select></div></div>
        <div class="form-row-3"><div class="form-group"><label>购买课时*</label><input type="number" class="form-input" id="fEHours" value="${existing?existing.purchased_hours:''}" min="1"></div><div class="form-group"><label>金额</label><input type="number" class="form-input" id="fEAmount" value="${existing&&existing.amount_paid?existing.amount_paid:''}" step="0.01"></div><div class="form-group"><label>日期</label><input type="date" class="form-input" id="fEDate" value="${existing&&existing.enrolled_date?existing.enrolled_date:new Date().toISOString().slice(0,10)}"></div></div>
        <div class="form-group"><label>备注</label><textarea class="form-textarea" id="fENotes" rows="2">${existing&&existing.notes?existing.notes:''}</textarea></div>
    `, '<button class="btn btn-outline" onclick="closeModal()">取消</button><button class="btn btn-primary" onclick="saveEnrollment()">保存</button>');
}

async function saveEnrollment() {
    const d={student_id:parseInt($('#fEStudent').value),course_id:parseInt($('#fECourse').value),purchased_hours:parseInt($('#fEHours').value)||0,amount_paid:parseFloat($('#fEAmount').value)||0,enrolled_date:$('#fEDate').value,notes:$('#fENotes').value.trim()};
    if(!d.student_id||!d.course_id){toast('请选择学生和课程','error');return;}
    if(!d.purchased_hours||d.purchased_hours<=0){toast('请输入课时数','error');return;}
    const res=await api(STATE.editingId?`/api/enrollments/${STATE.editingId}`:'/api/enrollments',{method:STATE.editingId?'PUT':'POST',body:JSON.stringify(d)});
    toast(res.message||'成功','success');closeModal();loadEnrollments();
}
async function deleteEnrollment(id){if(!confirm('确定取消?'))return;await api(`/api/enrollments/${id}`,{method:'DELETE'});toast('已取消','success');loadEnrollments();}

// ==================== 排课管理 ====================
async function loadSchedules() {
    const df=$('#scheduleDateFilter')?.value||'',sf=$('#scheduleStatusFilter')?.value||'';
    let url='/api/schedules?';if(df)url+=`date_from=${df}&date_to=${df}&`;if(sf)url+=`status=${sf}&`;
    const data=apiData(await api(url));
    const tbody=$('#scheduleTable');
    if(data.length===0){tbody.innerHTML='<tr><td colspan="9"><div class="empty-state"><div class="empty-text">暂无数据</div></div></td></tr>';return;}
    tbody.innerHTML=data.map(s=>{
        const st=s.status==='completed'?'<span class="tag tag-success">已完成</span>':s.status==='cancelled'?'<span class="tag tag-danger">已取消</span>':'<span class="tag tag-info">待上课</span>';
        const act=s.status==='scheduled'?`<button class="btn btn-success btn-xs" onclick="checkinScheduleFromList(${s.id})">签到</button> <button class="btn btn-warning btn-xs" onclick="cancelScheduleItem(${s.id})">取消</button>`:'';
        return `<tr><td><input type="checkbox" class="schedule-checkbox" value="${s.id}" data-status="${s.status}" ${s.status==='scheduled'?'':'disabled'}></td><td>${s.schedule_date}</td><td>${s.start_time}-${s.end_time}</td><td class="font-bold">${s.student_name}</td><td>${s.course_name}</td><td>${s.teacher_name||'-'}</td><td>${s.hours}</td><td>${st}</td><td>${act}</td></tr>`;
    }).join('');
}

async function showScheduleModal() {
    let enrollments=[],teachers=[];try{enrollments=apiData(await api('/api/enrollments?status=active'));teachers=apiData(await api('/api/teachers'));}catch(e){}
    showModal('新增排课', `
        <div class="form-group"><label>选择报名*</label><select class="form-select" id="fSEnrollment" onchange="onScheduleEnrollChange()">${enrollments.map(e=>`<option value="${e.student_id}" data-course="${e.course_id}" data-teacher="${e.teacher_id||''}">${e.student_name}-${e.course_name}(剩${e.remaining_hours}课时)</option>`).join('')}</select></div>
        <div class="form-row-3"><div class="form-group"><label>日期*</label><input type="date" class="form-input" id="fSDate" value="${new Date().toISOString().slice(0,10)}"></div><div class="form-group"><label>开始*</label><input type="time" class="form-input" id="fSStart" value="09:00"></div><div class="form-group"><label>结束*</label><input type="time" class="form-input" id="fSEnd" value="10:00"></div></div>
        <div class="form-row"><div class="form-group"><label>课时</label><input type="number" class="form-input" id="fSHours" value="1" min="1"></div><div class="form-group"><label>教师</label><select class="form-select" id="fSTeacher"><option value="">跟随课程</option>${teachers.map(t=>`<option value="${t.id}">${t.name}</option>`).join('')}</select></div></div>
        <div class="form-group"><label>备注</label><textarea class="form-textarea" id="fSNotes" rows="2"></textarea></div><input type="hidden" id="fSCourse">
    `, '<button class="btn btn-outline" onclick="closeModal()">取消</button><button class="btn btn-primary" onclick="saveSchedule()">确认</button>');
    onScheduleEnrollChange();
}
function onScheduleEnrollChange(){const s=$('#fSEnrollment'),o=s.options[s.selectedIndex];$('#fSCourse').value=o?.dataset?.course||'';}
async function saveSchedule(){
    const d={student_id:parseInt($('#fSEnrollment').value),course_id:parseInt($('#fSCourse').value),schedule_date:$('#fSDate').value,start_time:$('#fSStart').value,end_time:$('#fSEnd').value,hours:parseInt($('#fSHours').value)||1,teacher_id:$('#fSTeacher').value||null,notes:$('#fSNotes').value.trim()};
    if(!d.student_id||!d.course_id||!d.schedule_date){toast('请填写完整','error');return;}
    const res=await api('/api/schedules',{method:'POST',body:JSON.stringify(d)});
    toast(res.message||'成功','success');closeModal();loadSchedules();
}
async function checkinScheduleFromList(sid){await checkinSchedule(sid);loadSchedules();}
async function cancelScheduleItem(sid){if(!confirm('确定取消?'))return;await api(`/api/schedules/${sid}/cancel`,{method:'POST'});toast('已取消','success');loadSchedules();}
function toggleSelectAll(){const c=$('#scheduleSelectAll').checked;$$('.schedule-checkbox').forEach(cb=>{if(!cb.disabled)cb.checked=c;});}
async function batchCheckin(){
    const checked=[...$$('.schedule-checkbox:checked')].map(cb=>cb.value);
    if(checked.length===0){toast('请勾选','warning');return;}
    if(!confirm(`确认批量签到${checked.length}条？`))return;
    const res=await api('/api/records/batch-checkin',{method:'POST',body:JSON.stringify({schedule_ids:checked.map(Number)})});
    toast(res.message||'完成','success');loadSchedules();
}

// ==================== 课时记录 ====================
async function loadRecords(page=1){
    try {
    const f=$('#recordDateFrom')?.value||'',t=$('#recordDateTo')?.value||'',c=$('#recordCourseFilter')?.value||'';
    let url=`/api/records?page=${page}&per_page=30`;if(f)url+=`&date_from=${f}`;if(t)url+=`&date_to=${t}`;if(c)url+=`&course_id=${c}`;
    const d=apiData(await api(url));
    const tbody=$('#recordTable');
    if(d.records.length===0){tbody.innerHTML='<tr><td colspan="13"><div class="empty-state"><div class="empty-text">暂无记录</div></div></td></tr>';$('#recordPagination').innerHTML='';return;}
    tbody.innerHTML=d.records.map(r=>{
        const at=r.attendance==='present'?'<span class="tag tag-success">出勤</span>':r.attendance==='late'?'<span class="tag tag-warning">迟到</span>':'<span class="tag tag-danger">缺勤</span>';
        const nc = r.note_count > 0 ? `<span class="tag tag-info" style="cursor:pointer" onclick="showNotesModal(${r.id})" title="查看备注">📝${r.note_count}</span>` : `<span style="cursor:pointer;opacity:0.4" onclick="showNotesModal(${r.id})" title="添加备注">📝</span>`;
        const ops = [];
        ops.push(nc);
        if(isAdmin()) ops.push(`<button class="btn btn-danger btn-xs" onclick="deleteRecord(${r.id})">撤销</button>`);
        return `<tr><td>${r.record_date}</td><td class="font-bold">${r.student_name}</td><td>${r.student_gender||'-'}</td><td>${r.grade||'-'}</td><td>${r.school||'-'}</td><td>${r.course_name}</td><td>${r.subject||'-'}</td><td>${r.teacher_name||'-'}</td><td>${r.parent_phone||'-'}</td><td class="font-bold text-primary">${r.hours_consumed}</td><td>${r.remaining_after}</td><td>${at}</td><td class="nowrap">${ops.join(' ')}</td></tr>`;
    }).join('');
    let pag='';if(d.total_pages>1){pag+=`<button ${d.page===1?'disabled':''} onclick="loadRecords(${d.page-1})">◀</button>`;for(let i=1;i<=d.total_pages;i++){if(i===1||i===d.total_pages||Math.abs(i-d.page)<=2)pag+=`<button class="${i===d.page?'active':''}" onclick="loadRecords(${i})">${i}</button>`;else if(Math.abs(i-d.page)===3)pag+='<span class="text-muted">...</span>';}pag+=`<button ${d.page===d.total_pages?'disabled':''} onclick="loadRecords(${d.page+1})">▶</button>`;}
    $('#recordPagination').innerHTML=pag;
    } catch(e) { console.error("loadRecords error:", e); toast("加载记录失败", "error"); }
}

async function showDirectRecordModal(){
    let enrollments=[],teachers=[];try{enrollments=apiData(await api('/api/enrollments?status=active'));teachers=apiData(await api('/api/teachers'));}catch(e){}
    showModal('直接消课', `
        <div class="form-group"><label>选择报名*</label><select class="form-select" id="fDREnrollment" onchange="onDirectRecordChange()">${enrollments.map(e=>`<option value="${e.student_id}" data-course="${e.course_id}" data-teacher="${e.teacher_id||''}" data-remaining="${e.remaining_hours}">${e.student_name}-${e.course_name}(剩${e.remaining_hours})</option>`).join('')}</select></div>
        <div class="form-row-3"><div class="form-group"><label>日期*</label><input type="date" class="form-input" id="fDRDate" value="${new Date().toISOString().slice(0,10)}"></div><div class="form-group"><label>课时*</label><input type="number" class="form-input" id="fDRHours" value="1" min="1"></div><div class="form-group"><label>出勤</label><select class="form-select" id="fDRAttendance"><option value="present">出勤</option><option value="late">迟到</option><option value="absent">缺勤</option></select></div></div>
        <div class="form-group"><label>教师</label><select class="form-select" id="fDRTeacher"><option value="">跟随课程</option>${teachers.map(t=>`<option value="${t.id}">${t.name}</option>`).join('')}</select></div>
        <div class="form-group"><label>备注</label><textarea class="form-textarea" id="fDRNotes" rows="2"></textarea></div><input type="hidden" id="fDRCourse">
    `, '<button class="btn btn-outline" onclick="closeModal()">取消</button><button class="btn btn-primary" onclick="saveDirectRecord()">确认消课</button>');
    onDirectRecordChange();
}
function onDirectRecordChange(){const s=$('#fDREnrollment'),o=s.options[s.selectedIndex];$('#fDRCourse').value=o?.dataset?.course||'';$('#fDRHours').max=o?.dataset?.remaining||0;}
async function saveDirectRecord(){
    const d={student_id:parseInt($('#fDREnrollment').value),course_id:parseInt($('#fDRCourse').value),record_date:$('#fDRDate').value,hours_consumed:parseInt($('#fDRHours').value)||1,attendance:$('#fDRAttendance').value,teacher_id:$('#fDRTeacher').value||null,notes:$('#fDRNotes').value.trim()};
    if(!d.student_id||!d.course_id||!d.record_date){toast('请填写完整','error');return;}
    const res=await api('/api/records',{method:'POST',body:JSON.stringify(d)});
    if(res.code!==200){toast(res.message,'error');return;}
    toast(`消课成功！剩余${res.data?.remaining_after}课时`,'success');closeModal();loadRecords();
}

// 批量消课
async function showBatchConsumeModal(){
    try{
        const enrollments=apiData(await api('/api/students/active-with-enrollments'));
        if(enrollments.length===0){toast('暂无可消课学生','warning');return;}
        const sm={};enrollments.forEach(e=>{if(!sm[e.student_id])sm[e.student_id]={name:e.student_name,grade:e.grade,courses:[]};sm[e.student_id].courses.push(e);});
        const rows=Object.entries(sm).map(([sid,info])=>`<tr class="batch-row" data-sid="${sid}"><td><input type="checkbox" class="batch-student-cb" checked onchange="updateBatchPreview()"></td><td class="font-bold">${info.name}</td><td>${info.grade||'-'}</td><td><select class="form-select batch-course" style="width:100%;" onchange="updateBatchPreview()">${info.courses.map((c,i)=>`<option value="${c.course_id}" data-remaining="${c.remaining_hours}" ${i===0?'selected':''}>${c.course_name}(${c.subject||''})|剩${c.remaining_hours}</option>`).join('')}</select></td><td><input type="number" class="form-input batch-hours" value="1" min="1" style="width:70px;" onchange="updateBatchPreview()"></td><td><span class="batch-preview text-muted">-</span></td></tr>`).join('');
        showModal('📋 批量消课', `
            <div style="margin-bottom:12px;display:flex;align-items:center;gap:12px;">
                <div class="form-group" style="margin-bottom:0;flex:1;"><label>日期</label><input type="date" class="form-input" id="batchDate" value="${new Date().toISOString().slice(0,10)}"></div>
                <div class="form-group" style="margin-bottom:0;flex:1;"><label>出勤</label><select class="form-select" id="batchAttendance"><option value="present">出勤</option><option value="late">迟到</option><option value="absent">缺勤</option></select></div>
                <div class="form-group" style="margin-bottom:0;"><label>统一课时</label><input type="number" class="form-input" id="batchUniformHours" value="1" min="1" style="width:80px;" onchange="setUniformHours()"></div>
            </div>
            <div class="table-wrap" style="max-height:400px;overflow-y:auto;"><table><thead><tr><th><input type="checkbox" id="batchSelectAll" checked onchange="toggleBatchAll()"></th><th>学生</th><th>年级</th><th>课程</th><th>课时</th><th>预览</th></tr></thead><tbody>${rows}</tbody></table></div>
            <div id="batchSummary" style="margin-top:12px;font-size:13px;color:var(--gray-600);"></div>
        `, '<button class="btn btn-outline" onclick="closeModal()">取消</button><button class="btn btn-success" onclick="executeBatchConsume()">✅ 确认批量消课</button>', 'modal-lg');
        updateBatchPreview();
    }catch(e){toast('加载失败','error');}
}
function toggleBatchAll(){const c=$('#batchSelectAll').checked;$$('.batch-student-cb').forEach(cb=>cb.checked=c);updateBatchPreview();}
function setUniformHours(){const v=$('#batchUniformHours').value;$$('.batch-hours').forEach(i=>i.value=v);updateBatchPreview();}
function updateBatchPreview(){
    let ts=0,th=0;
    $$('.batch-row').forEach(row=>{
        const cb=row.querySelector('.batch-student-cb');
        if(!cb.checked){row.querySelector('.batch-preview').textContent='跳过';return;}
        const h=parseInt(row.querySelector('.batch-hours').value)||1;
        const cs=row.querySelector('.batch-course'),r=parseInt(cs.options[cs.selectedIndex]?.dataset?.remaining)||0;
        ts++;th+=h;
        row.querySelector('.batch-preview').innerHTML=h>r?'<span class="text-danger">课时不足!</span>':`<span class="text-success">剩${r}→${r-h}</span>`;
    });
    $('#batchSummary').textContent=`已选${ts}名学生，合计${th}课时`;
}
async function executeBatchConsume(){
    const items=[];
    $$('.batch-row').forEach(row=>{
        const cb=row.querySelector('.batch-student-cb');if(!cb.checked)return;
        const h=parseInt(row.querySelector('.batch-hours').value)||1;
        const cs=row.querySelector('.batch-course'),r=parseInt(cs.options[cs.selectedIndex]?.dataset?.remaining)||0;
        if(h>r)return;
        items.push({student_id:parseInt(row.dataset.sid),course_id:parseInt(cs.value),hours:h,student_name:row.querySelector('.font-bold')?.textContent||'',record_date:$('#batchDate').value,attendance:$('#batchAttendance').value});
    });
    if(items.length===0){toast('没有可消课的学生','warning');return;}
    const res=await api('/api/records/batch-consume',{method:'POST',body:JSON.stringify({items})});
    toast(res.message,'success');
    if(res.data?.fail_list?.length>0)toast('部分失败:'+res.data.fail_list.join('; '),'warning');
    closeModal();loadRecords();
}
async function deleteRecord(rid){if(!confirm('确定撤销？'))return;const res=await api(`/api/records/${rid}`,{method:'DELETE'});toast(res.message||'已撤销','success');loadRecords();}

// ==================== 用户管理 ====================
async function loadUsers(){
    const users=apiData(await api('/api/users'));
    const tbody=$('#userTable');
    if(users.length===0){tbody.innerHTML='<tr><td colspan="7"><div class="empty-state"><div class="empty-text">暂无用户</div></div></td></tr>';return;}
    const rm={admin:'管理员',teacher:'教师',parent:'家长'};
    tbody.innerHTML=users.map(u=>`<tr><td>${u.username}</td><td>${u.real_name||'-'}</td><td>${rm[u.role]||u.role}</td><td>${u.student_name||'-'}</td><td>${u.teacher_name||'-'}</td><td><span class="tag ${u.status==='active'?'tag-success':'tag-default'}">${u.status}</span></td><td><button class="btn btn-outline btn-xs" onclick="showUserModal(${u.id})">编辑</button>${u.role!=='admin'?` <button class="btn btn-danger btn-xs" onclick="deleteUser(${u.id})">删除</button>`:''}</td></tr>`).join('');
}

async function showUserModal(id=null){
    STATE.editingId=id;let u=null;let students=[],teachers=[];
    if(id){const users=apiData(await api('/api/users'));u=users.find(x=>x.id===id);}
    try{students=apiData(await api('/api/students'));teachers=apiData(await api('/api/teachers'));}catch(e){}
    showModal(id?'编辑用户':'添加用户', `
        <div class="form-row"><div class="form-group"><label>用户名*</label><input type="text" class="form-input" id="fUName" value="${u?.username||''}" ${id?'readonly':''}></div><div class="form-group"><label>密码${id?'(留空不修改)':''}</label><input type="text" class="form-input" id="fUPassword" placeholder="${id?'留空不修改':'默认123456'}"></div></div>
        <div class="form-row"><div class="form-group"><label>姓名</label><input type="text" class="form-input" id="fURealName" value="${u?.real_name||''}"></div><div class="form-group"><label>手机</label><input type="text" class="form-input" id="fUPhone" value="${u?.phone||''}"></div></div>
        <div class="form-row"><div class="form-group"><label>角色</label><select class="form-select" id="fURole"><option value="admin" ${u?.role==='admin'?'selected':''}>管理员</option><option value="teacher" ${u?.role==='teacher'?'selected':''}>教师</option><option value="parent" ${u?.role==='parent'?'selected':''}>家长</option></select></div><div class="form-group"><label>状态</label><select class="form-select" id="fUStatus"><option value="active" ${u?.status==='active'?'selected':''}>启用</option><option value="inactive" ${u?.status==='inactive'?'selected':''}>停用</option></select></div></div>
        <div class="form-row"><div class="form-group"><label>关联学生</label><select class="form-select" id="fUStudent"><option value="">无</option>${students.map(s=>`<option value="${s.id}" ${u?.linked_student_id===s.id?'selected':''}>${s.name}</option>`).join('')}</select></div><div class="form-group"><label>关联教师</label><select class="form-select" id="fUTeacher"><option value="">无</option>${teachers.map(t=>`<option value="${t.id}" ${u?.linked_teacher_id===t.id?'selected':''}>${t.name}</option>`).join('')}</select></div></div>
    `, '<button class="btn btn-outline" onclick="closeModal()">取消</button><button class="btn btn-primary" onclick="saveUser()">保存</button>');
}

async function saveUser(){
    const d={real_name:$('#fURealName').value.trim(),phone:$('#fUPhone').value.trim(),role:$('#fURole').value,status:$('#fUStatus').value,linked_student_id:$('#fUStudent').value||null,linked_teacher_id:$('#fUTeacher').value||null};
    if($('#fUPassword').value)d.password=$('#fUPassword').value;
    if(!STATE.editingId){
        d.username=$('#fUName').value.trim();
        if(!d.username){toast('请输入用户名','error');return;}
    }
    const res=await api(STATE.editingId?`/api/users/${STATE.editingId}`:'/api/users',{method:STATE.editingId?'PUT':'POST',body:JSON.stringify(d)});
    if(res.code===200&&!STATE.editingId)toast(`创建成功！用户名:${res.data.username} 密码:${res.data.password}`,'success');
    else toast(res.message||'成功','success');
    closeModal();loadUsers();
}
async function deleteUser(uid){if(!confirm('确定删除？'))return;await api(`/api/users/${uid}`,{method:'DELETE'});toast('已删除','success');loadUsers();}

// ==================== 备份恢复 ====================
async function loadBackup(){
    const history=apiData(await api('/api/backup/history'));
    const tbody=$('#backupHistoryTable');
    if(history.length===0){tbody.innerHTML='<tr><td colspan="3"><div class="empty-state"><div class="empty-text">暂无备份记录</div></div></td></tr>';return;}
    tbody.innerHTML=history.map(h=>`<tr><td>${h.filename}</td><td>${(h.file_size/1024).toFixed(1)}KB</td><td>${h.created_at}</td></tr>`).join('');
}


async function loadPermissions() {
    showPermTab('roles');
}

function downloadBackup(){
    fetch(API_BASE + '/api/backup/download',{headers:{'Authorization':`Bearer ${STATE.token}`}})
        .then(r=>r.blob()).then(blob=>{
            const url=URL.createObjectURL(blob);
            const a=document.createElement('a');a.href=url;a.download=`backup_${new Date().toISOString().slice(0,10)}.db`;
            a.click();URL.revokeObjectURL(url);
            toast('备份下载成功！','success');
            setTimeout(loadBackup,1000);
        }).catch(e=>toast('下载失败','error'));
}

async function restoreBackup(){
    const file=$('#restoreFile').files[0];
    if(!file){toast('请选择备份文件','warning');return;}
    if(!confirm('确定恢复？当前数据将被替换！（会自动备份当前数据）'))return;
    const fd=new FormData();fd.append('file',file);
    const res=await fetch(API_BASE + '/api/backup/restore',{method:'POST',headers:{'Authorization':`Bearer ${STATE.token}`},body:fd}).then(r=>r.json());
    if(res.code===200){toast(res.message,'success');setTimeout(loadBackup,1000);}
    else toast(res.message,'error');
}

// ==================== 过滤绑定 ====================
function bindFilters(){
    ['studentSearch','teacherSearch','courseSearch'].forEach(id=>{
        const el=$(`#${id}`);if(el){let t;el.addEventListener('input',()=>{clearTimeout(t);t=setTimeout(()=>{if(id==='studentSearch')loadStudents();else if(id==='teacherSearch')loadTeachers();else loadCourses();},400);});}
    });
    const sd=$('#scheduleDateFilter'),ss=$('#scheduleStatusFilter');if(sd)sd.addEventListener('change',loadSchedules);if(ss)ss.addEventListener('change',loadSchedules);
    const rf=$('#recordDateFrom'),rt=$('#recordDateTo'),rc=$('#recordCourseFilter');if(rf)rf.addEventListener('change',()=>loadRecords());if(rt)rt.addEventListener('change',()=>loadRecords());if(rc)rc.addEventListener('change',()=>loadRecords());
}
async function loadRecordCourseFilter(){
    try{const c=apiData(await api('/api/courses'));const s=$('#recordCourseFilter');if(s)s.innerHTML='<option value="">全部课程</option>'+c.map(x=>`<option value="${x.id}">${x.name}</option>`).join('');}catch(e){}
}

// ==================== 云端同步 ====================
async function cloudSync(){
    const btn=$('#btnCloudSync'),st=$('#cloudSyncStatus');
    btn.disabled=true;btn.textContent='同步中...';st.textContent='';
    try{
        const r=await api('/api/backup/cloud-sync',{method:'POST'});
        if(r.code===200){st.textContent='同步成功！';st.style.color='#10B981';}
        else{st.textContent=r.message;st.style.color='#EF4444';}
    }catch(e){st.textContent='同步失败';st.style.color='#EF4444';}
    btn.disabled=false;btn.textContent='同步到云端';
}

async function cloudRestore(){
    if(!confirm('⚠️ 云端恢复将用云端备份覆盖当前数据，确定继续？\n\n恢复前会自动保存当前数据到本地。')) return;
    const btn=$('#btnCloudRestore'),st=$('#cloudRestoreStatus');
    btn.disabled=true;btn.textContent='恢复中...';st.textContent='';
    try{
        const r=await api('/api/backup/cloud-restore',{method:'POST'});
        if(r.code===200){st.textContent='恢复成功！刷新页面生效';st.style.color='#10B981';}
        else{st.textContent=r.message;st.style.color='#EF4444';}
    }catch(e){st.textContent='恢复失败';st.style.color='#EF4444';}
    btn.disabled=false;btn.textContent='☁️ 云端恢复';
}

// ==================== 课时备注 ====================
async function showNotesModal(rid){
    try {
        const notes = apiData(await api(`/api/records/${rid}/notes`));
        const html = notes.map(n => `<div style="padding:8px 0;border-bottom:1px solid #e5e7eb;">
            <div style="font-size:12px;color:#9ca3af;">${n.created_at} · ${n.created_by||''}</div>
            <div style="margin-top:4px;">${n.content}</div>
        </div>`).join('');
        showModal('📝 课时备注（记录#'+rid+'）',
            `<div style="max-height:300px;overflow-y:auto;margin-bottom:12px;">${html||'<div class="text-muted" style="text-align:center;padding:20px;">暂无备注</div>'}</div>
             <div class="form-group"><label>添加备注</label><textarea class="form-textarea" id="newNoteContent" rows="2" placeholder="输入备注内容..."></textarea></div>`,
            `<button class="btn btn-outline" onclick="closeModal()">关闭</button><button class="btn btn-primary" onclick="addNote(${rid})">添加备注</button>`);
    } catch(e) { toast('加载备注失败', 'error'); }
}
async function addNote(rid){
    const content = $('#newNoteContent')?.value?.trim();
    if(!content) { toast('请输入备注内容', 'warning'); return; }
    const res = await api(`/api/records/${rid}/notes`, { method: 'POST', body: JSON.stringify({content}) });
    if(res.code===200) { toast('备注已添加', 'success'); closeModal(); loadRecords(); }
    else toast(res.message, 'error');
}
// ==================== 权限管理 ====================
const _PERM_LABELS = [
    {key:'can_manage_students',label:'学生管理',desc:'添加、编辑、删除学生'},
    {key:'can_manage_teachers',label:'教师管理',desc:'添加、编辑、删除教师'},
    {key:'can_manage_courses',label:'课程管理',desc:'添加、编辑、删除课程'},
    {key:'can_manage_enrollments',label:'报名管理',desc:'管理学生报名记录'},
    {key:'can_create_schedules',label:'排课管理',desc:'创建和修改排课计划'},
    {key:'can_checkin',label:'签到操作',desc:'对排课进行签到确认'},
    {key:'can_view_all_data',label:'查看全部数据',desc:'查看所有学生和课程'},
    {key:'can_view_prices',label:'查看价格/金额',desc:'查看课程单价和缴费信息'},
    {key:'can_manage_users',label:'用户管理',desc:'管理系统用户账号'},
    {key:'can_backup',label:'备份管理',desc:'备份和恢复数据库'},
];

function showPermTab(tab) {
    $$('.perm-tab').forEach(t => t.classList.remove('active'));
    $$('.perm-tab').forEach(t => { if(t.dataset.tab === tab) t.classList.add('active'); });
    $('#permRolesPanel').style.display = tab === 'roles' ? '' : 'none';
    $('#permUsersPanel').style.display = tab === 'users' ? '' : 'none';
    if (tab === 'roles') loadRolePermissions();
    else loadUserPermissions();
}

async function loadRolePermissions() {
    try {
        const res = await api('/api/admin/permissions');
        const perms = res.data || { roles: [], overrides: [] };
        const roleIcons = { admin: '👑', teacher: '👩‍🏫', parent: '👨‍👩‍👧' };
        const roleNames = { admin: '管理员', teacher: '教师', parent: '学生/家长' };
        const roleBg = { admin: 'linear-gradient(135deg,#FEF3C7,#FDE68A)', teacher: 'linear-gradient(135deg,#DBEAFE,#BFDBFE)', parent: 'linear-gradient(135deg,#D1FAE5,#A7F3D0)' };
        const html = perms.roles.map(p => {
            const roleClass = p.role;
            return `
            <div class="perm-role-card" style="background:${roleBg[p.role]||'#F9FAFB'};">
                <div class="perm-role-header">
                    <span class="perm-role-badge ${roleClass}">${roleIcons[p.role]||'👤'} ${roleNames[p.role]||p.role}</span>
                    <span style="font-size:12px;color:var(--gray-500);">点击切换开关，再点「保存更改」生效</span>
                </div>
                <div class="perm-grid">
                    ${_PERM_LABELS.map(f => `
                        <label class="perm-item">
                            <span>
                                <span class="perm-item-label">${f.label}</span>
                                <span class="perm-item-desc">${f.desc}</span>
                            </span>
                            <div class="toggle-wrap">
                                <input type="checkbox" class="perm-checkbox perm-toggle-input" id="perm_${p.role}_${f.key}" data-role="${p.role}" data-key="${f.key}" ${p[f.key]?'checked':''}>
                                <label class="perm-toggle-label" for="perm_${p.role}_${f.key}"></label>
                            </div>
                        </label>
                    `).join('')}
                </div>
            </div>`;
        }).join('');
        $('#rolePermTable').innerHTML = html || '<p style="text-align:center;color:var(--gray-400);padding:40px;">暂无数据</p>';
    } catch(e) { toast('加载权限失败', 'error'); }
}

async function saveAllRolePerms() {
    const boxes = $$('.perm-checkbox');
    const changes = {};
    boxes.forEach(b => {
        const role = b.dataset.role;
        const key = b.dataset.key;
        if (!changes[role]) changes[role] = {};
        changes[role][key] = b.checked ? 1 : 0;
    });
    try {
        for (const role in changes) {
            await api('/api/admin/permissions/' + role, { method: 'PUT', body: JSON.stringify(changes[role]) });
        }
        toast('角色权限已保存', 'success');
    } catch(e) { toast('保存失败：' + e.message, 'error'); }
}

async function loadUserPermissions() {
    try {
        const res = await api('/api/admin/users-permissions');
        const users = res.data || [];
        let html = '<div class="perm-user-grid">';
        users.forEach(u => {
            const avatarBg = u.role==='admin'?'linear-gradient(135deg,#F59E0B,#D97706)':u.role==='teacher'?'linear-gradient(135deg,#3B82F6,#2563EB)':'linear-gradient(135deg,#10B981,#059669)';
            const roleLabel = u.role==='admin'?'管理员':u.role==='teacher'?'教师':'学生/家长';
            html += `
            <div class="perm-user-card" onclick="showUserPermDetail(${u.id})">
                <div class="perm-user-header">
                    <div style="width:44px;height:44px;border-radius:50%;background:${avatarBg};display:flex;align-items:center;justify-content:center;font-weight:700;color:white;font-size:18px;flex-shrink:0;">${(u.real_name||u.username)[0]}</div>
                    <div class="perm-user-info">
                        <div class="perm-user-name">${u.real_name || u.username}</div>
                        <div class="perm-user-meta"><span class="perm-role-badge ${u.role}" style="font-size:10px;padding:2px 8px;">${roleLabel}</span>${u.phone ? ' · '+u.phone : ''}</div>
                    </div>
                    <div style="margin-left:auto;color:var(--gray-300);font-size:20px;">›</div>
                </div>
            </div>`;
        });
        html += '</div>';
        if (!users.length) html = '<p style="text-align:center;color:var(--gray-400);padding:40px;">暂无用户数据</p>';
        $('#userPermContent').innerHTML = html;
    } catch(e) { toast('加载用户列表失败', 'error'); }
}

async function showUserPermDetail(uid) {
    try {
        const res = await api('/api/admin/user-permissions/' + uid);
        const d = res.data;
        if (!d) return;
        const u = d.user;
        const isOverride = (key) => d.user_permissions && d.user_permissions[key] >= 0;
        const roleLabel = d.role==='admin'?'管理员':d.role==='teacher'?'教师':'学生/家长';
        const avatarBg = d.role==='admin'?'linear-gradient(135deg,#F59E0B,#D97706)':d.role==='teacher'?'linear-gradient(135deg,#3B82F6,#2563EB)':'linear-gradient(135deg,#10B981,#059669)';
        const permRow = (f) => {
            const roleVal = d.role_permissions ? d.role_permissions[f.key] : 0;
            const userRaw = d.user_permissions ? d.user_permissions[f.key] : -1;
            const effectiveVal = d.effective_permissions ? d.effective_permissions[f.key] : roleVal;
            const hasOverride = userRaw >= 0;
            return `<div class="perm-comparison-row">
                <div class="perm-comp-label">${f.label}<span style="font-size:11px;color:var(--gray-400);display:block;">${f.desc}</span></div>
                <div class="perm-comp-cell">${roleVal?'<span class="perm-yes">✓</span>':'<span class="perm-no">✗</span>'}</div>
                <div class="perm-comp-cell">${hasOverride?(userRaw?'<span class="perm-yes perm-override">✓</span>':'<span class="perm-no perm-override">✗</span>'):'<span style="color:var(--gray-300);">—</span>'}</div>
                <div class="perm-comp-cell">${effectiveVal?'<span class="perm-yes perm-effective">✓</span>':'<span class="perm-no perm-effective">✗</span>'}</div>
            </div>`;
        };
        const overlay = document.createElement('div');
        overlay.className = 'perm-overlay';
        overlay.onclick = (e) => { if(e.target===overlay) overlay.remove(); };
        overlay.innerHTML = `
            <div class="perm-overlay-content">
                <div style="display:flex;align-items:center;gap:16px;margin-bottom:24px;">
                    <div style="width:56px;height:56px;border-radius:50%;background:${avatarBg};display:flex;align-items:center;justify-content:center;font-weight:700;color:white;font-size:24px;">${(u.real_name||u.username)[0]}</div>
                    <div>
                        <div style="font-size:20px;font-weight:700;">${u.real_name||u.username}</div>
                        <span class="perm-role-badge ${d.role}" style="font-size:12px;">${roleLabel}</span>
                    </div>
                    <button class="btn btn-outline btn-sm" style="margin-left:auto;" onclick="this.closest('.perm-overlay').remove()">关闭</button>
                </div>
                <div style="display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap;">
                    <button class="btn btn-primary btn-sm" onclick="editUserPerms(${uid})">✏️ 编辑覆盖权限</button>
                    <button class="btn btn-outline btn-sm" onclick="resetUserPerms(${uid})">↩ 重置为角色默认</button>
                </div>
                <div class="perm-comparison-header">
                    <div class="perm-col-header">权限</div>
                    <div class="perm-col-header">角色默认</div>
                    <div class="perm-col-header">个人覆盖</div>
                    <div class="perm-col-header">实际生效</div>
                </div>
                <div class="perm-comparison">
                    ${_PERM_LABELS.map(f => permRow(f)).join('')}
                </div>
                <div class="perm-form" id="permFormArea_${uid}"></div>
            </div>`;
        document.body.appendChild(overlay);
    } catch(e) { toast('加载权限详情失败', 'error'); }
}

async function editUserPerms(uid) {
    try {
        const res = await api('/api/admin/user-permissions/' + uid);
        const d = res.data;
        const formArea = document.getElementById('permFormArea_' + uid);
        if (!formArea) return;
        formArea.innerHTML = `
            <div style="margin-top:20px;padding:20px;background:var(--gray-50);border-radius:12px;">
                <h4 style="margin-bottom:4px;">✏️ 编辑个人权限覆盖</h4>
                <p style="font-size:12px;color:var(--gray-500);margin-bottom:16px;">选"继承角色"则使用角色默认值；选"开启/关闭"则覆盖角色设置</p>
                ${_PERM_LABELS.map(f => `
                    <div class="perm-edit-row">
                        <span class="perm-item-label">${f.label}</span>
                        <select class="form-select perm-perm-select" data-key="${f.key}" style="width:120px;font-size:13px;">
                            <option value="-1" ${(d.user_permissions && d.user_permissions[f.key]===-1)||(!d.user_permissions||d.user_permissions[f.key]===undefined)?'selected':''}>继承角色</option>
                            <option value="1" ${d.user_permissions && d.user_permissions[f.key]===1?'selected':''}>✓ 开启</option>
                            <option value="0" ${d.user_permissions && d.user_permissions[f.key]===0?'selected':''}>✗ 关闭</option>
                        </select>
                    </div>
                `).join('')}
                <div style="margin-top:16px;display:flex;gap:12px;justify-content:flex-end;">
                    <button class="btn btn-outline btn-sm" onclick="document.getElementById('permFormArea_${uid}').innerHTML=''">取消</button>
                    <button class="btn btn-primary btn-sm" onclick="saveUserPerms(${uid})">保存</button>
                </div>
            </div>`;
    } catch(e) { toast('加载失败', 'error'); }
}

async function saveUserPerms(uid) {
    const selects = document.querySelectorAll('.perm-perm-select');
    const data = {};
    selects.forEach(s => { data[s.dataset.key] = parseInt(s.value); });
    try {
        await api('/api/admin/user-permissions/' + uid, { method: 'PUT', body: JSON.stringify(data) });
        toast('权限已保存', 'success');
        document.querySelector('.perm-overlay')?.remove();
        showUserPermDetail(uid);
    } catch(e) { toast('保存失败：' + e.message, 'error'); }
}

async function resetUserPerms(uid) {
    if (!confirm('确定要重置该用户权限为角色默认值吗？')) return;
    try {
        await api('/api/admin/user-permissions/' + uid, { method: 'DELETE' });
        toast('已重置', 'success');
        document.querySelector('.perm-overlay')?.remove();
        showUserPermDetail(uid);
    } catch(e) { toast('重置失败：' + e.message, 'error'); }
}

// ==================== 初始化 ====================
function init(){initNavigation();bindFilters();setupIdleListener();tryAutoLogin();}
document.addEventListener('DOMContentLoaded', init);

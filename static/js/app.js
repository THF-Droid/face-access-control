/**
 * 人脸通行管控系统 - 管理后台主逻辑
 */

// ═══════════════════════════════════════════════════════
//  初始化 & 鉴权检查
// ═══════════════════════════════════════════════════════

const API = {
    async get(url) {
        const r = await fetch(url);
        if (r.status === 401) { window.location.href = '/'; return null; }
        return r.json();
    },
    async post(url, data) {
        const r = await fetch(url, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) });
        if (r.status === 401) { window.location.href = '/'; return null; }
        return r.json();
    },
    async put(url, data) {
        const r = await fetch(url, { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) });
        if (r.status === 401) { window.location.href = '/'; return null; }
        return r.json();
    },
    async del(url) {
        const r = await fetch(url, { method: 'DELETE' });
        if (r.status === 401) { window.location.href = '/'; return null; }
        return r.json();
    }
};

// 认证检查
(async () => {
    const resp = await API.get('/api/check-auth');
    if (!resp || !resp.success) return;
    document.getElementById('admin-name').textContent = resp.data.username;
    document.getElementById('admin-avatar-initial').textContent = resp.data.username.charAt(0).toUpperCase();
})();

// 退出登录
document.getElementById('logout-btn').addEventListener('click', async () => {
    await API.post('/api/logout');
    window.location.href = '/';
});

// 实时时钟
setInterval(() => {
    document.getElementById('live-time').textContent = new Date().toLocaleString('zh-CN');
}, 1000);
document.getElementById('live-time').textContent = new Date().toLocaleString('zh-CN');


// ═══════════════════════════════════════════════════════
//  导航切换
// ═══════════════════════════════════════════════════════

const panels = {};
document.querySelectorAll('.panel').forEach(p => panels[p.id.replace('panel-','')] = p);

document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const panelName = item.dataset.panel;
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        item.classList.add('active');
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        document.getElementById(`panel-${panelName}`).classList.add('active');
        loadPanel(panelName);
    });
});

function loadPanel(name) {
    switch(name) {
        case 'dashboard': loadDashboard(); break;
        case 'persons': loadPersons(); break;
        case 'records': loadRecords(); break;
        case 'analytics': loadAnalytics(); break;
        case 'admins': loadAdmins(); break;
    }
}

// 初始加载
loadDashboard();


// ═══════════════════════════════════════════════════════
//  Toast 提示
// ═══════════════════════════════════════════════════════

function toast(msg, type='info') {
    const container = document.getElementById('toast-container');
    const t = document.createElement('div');
    t.className = `toast toast-${type}`;
    t.textContent = msg;
    container.appendChild(t);
    setTimeout(() => {
        t.classList.add('hiding');
        t.addEventListener('animationend', () => t.remove());
    }, 3000);
}


// ═══════════════════════════════════════════════════════
//  模态框
// ═══════════════════════════════════════════════════════

function showModal(id) { document.getElementById(id).classList.add('show'); }
function hideModal(id) { document.getElementById(id).classList.remove('show'); }

document.querySelectorAll('.modal-close').forEach(btn => {
    btn.addEventListener('click', () => {
        btn.closest('.modal').classList.remove('show');
    });
});

document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.classList.remove('show'); });
});


// ═══════════════════════════════════════════════════════
//  系统概览
// ═══════════════════════════════════════════════════════

async function loadDashboard() {
    const resp = await API.get('/api/stats');
    if (!resp || !resp.success) return;
    const s = resp.data;
    document.getElementById('stat-persons').textContent = s.total_persons;
    document.getElementById('stat-allow').textContent = s.allow_count;
    document.getElementById('stat-deny').textContent = s.deny_count;
    document.getElementById('stat-unknown').textContent = s.unknown_count;
    document.getElementById('stat-total').textContent = s.total_records;
    document.getElementById('stat-today').textContent = s.today_records;

    // 允许率
    document.getElementById('allow-rate-bar').style.width = s.allow_rate + '%';
    document.getElementById('allow-rate-text').textContent = s.allow_rate + '%';

    // 模型状态
    const modelEl = document.getElementById('model-status');
    if (s.model_trained) {
        modelEl.innerHTML = '<span class="status-dot green"></span><span>模型已训练 - 可进行识别</span>';
    } else {
        modelEl.innerHTML = '<span class="status-dot red"></span><span>模型未训练，请先注册人员并训练</span>';
    }

    // 训练按钮
    document.getElementById('btn-train-model').onclick = async () => {
        const btn = event.target;
        btn.disabled = true; btn.textContent = '训练中...';
        const r = await API.post('/api/model/train');
        if (r && r.success) toast('模型训练完成！', 'success');
        else toast(r.message || '训练失败', 'error');
        btn.disabled = false; btn.textContent = '训练模型';
        loadDashboard();
    };
}


// ═══════════════════════════════════════════════════════
//  人员管理
// ═══════════════════════════════════════════════════════

let currentPersons = [];

async function loadPersons(keyword = '') {
    const url = keyword ? `/api/persons?keyword=${encodeURIComponent(keyword)}` : '/api/persons';
    const resp = await API.get(url);
    if (!resp || !resp.success) return;
    currentPersons = resp.data;
    renderPersonsTable(currentPersons);
}

function renderPersonsTable(persons) {
    const tbody = document.querySelector('#persons-table tbody');
    tbody.innerHTML = persons.map(p => `
        <tr>
            <td>${p.id}</td>
            <td><strong>${esc(p.name)}</strong></td>
            <td>${esc(p.department)}</td>
            <td>${esc(p.role)}</td>
            <td>${esc(p.phone)}</td>
            <td><span class="badge ${p.permission==='允许'?'badge-allow':'badge-deny'}">${p.permission}</span></td>
            <td><span class="badge ${p.has_face?'badge-face-yes':'badge-face-no'}">${p.has_face?'已采集':'未采集'}</span></td>
            <td class="actions">
                <button class="btn btn-sm btn-primary" onclick="editPerson(${p.id})">编辑</button>
                <button class="btn btn-sm btn-danger" onclick="confirmDeletePerson(${p.id},'${esc(p.name)}')">删除</button>
            </td>
        </tr>
    `).join('');

    // 更新采集页的下拉列表
    const sel = document.getElementById('capture-person');
    sel.innerHTML = '<option value="">-- 请选择 --</option>' +
        persons.map(p => `<option value="${p.id}">${esc(p.name)} (ID:${p.id})</option>`).join('');
}

function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

// 搜索
document.getElementById('person-search').addEventListener('input', (e) => {
    loadPersons(e.target.value);
});

// 新增人员按钮
document.getElementById('btn-add-person').addEventListener('click', () => {
    document.getElementById('modal-person-title').textContent = '新增人员';
    document.getElementById('form-name').value = '';
    document.getElementById('form-department').value = '';
    document.getElementById('form-role').value = '';
    document.getElementById('form-phone').value = '';
    document.getElementById('form-permission').value = '允许';
    document.getElementById('form-remark').value = '';
    document.getElementById('btn-save-person').dataset.editingId = '';
    showModal('modal-person');
});

// 编辑人员
function editPerson(id) {
    const p = currentPersons.find(x => x.id === id);
    if (!p) return;
    document.getElementById('modal-person-title').textContent = '编辑人员';
    document.getElementById('form-name').value = p.name;
    document.getElementById('form-department').value = p.department;
    document.getElementById('form-role').value = p.role;
    document.getElementById('form-phone').value = p.phone;
    document.getElementById('form-permission').value = p.permission;
    document.getElementById('form-remark').value = p.remark;
    document.getElementById('btn-save-person').dataset.editingId = id;
    showModal('modal-person');
}

// 保存人员
document.getElementById('btn-save-person').addEventListener('click', async () => {
    const id = document.getElementById('btn-save-person').dataset.editingId;
    const data = {
        name: document.getElementById('form-name').value.trim(),
        department: document.getElementById('form-department').value.trim(),
        role: document.getElementById('form-role').value.trim(),
        phone: document.getElementById('form-phone').value.trim(),
        permission: document.getElementById('form-permission').value,
        remark: document.getElementById('form-remark').value.trim()
    };
    if (!data.name) { toast('姓名不能为空', 'error'); return; }

    let resp;
    if (id) {
        resp = await API.put(`/api/persons/${id}`, data);
    } else {
        resp = await API.post('/api/persons', data);
    }

    if (resp && resp.success) {
        toast(resp.message, 'success');
        hideModal('modal-person');
        loadPersons(document.getElementById('person-search').value);
    } else {
        toast(resp.message || '操作失败', 'error');
    }
});

// 删除人员
function confirmDeletePerson(id, name) {
    document.getElementById('confirm-message').textContent = `确定要删除「${name}」吗？此操作不可恢复。`;
    document.getElementById('btn-confirm-ok').onclick = async () => {
        const resp = await API.del(`/api/persons/${id}`);
        if (resp && resp.success) {
            toast(resp.message, 'success');
            hideModal('modal-confirm');
            loadPersons(document.getElementById('person-search').value);
        } else {
            toast(resp.message || '删除失败', 'error');
        }
    };
    showModal('modal-confirm');
}


// ═══════════════════════════════════════════════════════
//  人脸采集
// ═══════════════════════════════════════════════════════

let captureStream = null;
let captureInterval = null;
let captureCount = 0;
let captureTarget = 30;

document.getElementById('btn-start-camera').addEventListener('click', async () => {
    try {
        captureStream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
        document.getElementById('capture-video').srcObject = captureStream;
        document.getElementById('btn-capture').disabled = false;
        document.getElementById('btn-auto-capture').disabled = false;
        toast('摄像头已开启', 'success');
    } catch (err) {
        toast('无法访问摄像头: ' + err.message, 'error');
    }
});

// 拍照采集
document.getElementById('btn-capture').addEventListener('click', () => captureOnce());

async function captureOnce() {
    const pid = document.getElementById('capture-person').value;
    if (!pid) { toast('请先选择人员', 'warning'); return; }

    const video = document.getElementById('capture-video');
    const canvas = document.getElementById('capture-canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    const imageData = canvas.toDataURL('image/jpeg', 0.9);

    const resp = await API.post('/api/face/capture', { person_id: parseInt(pid), image: imageData });
    if (resp && resp.success) {
        captureCount = resp.data.total;
        document.getElementById('capture-progress').textContent = `已采集 ${captureCount} 张`;
        document.getElementById('capture-log').innerHTML +=
            `<span style="color:#16a34a">&#10003;</span> 第 ${resp.data.sample_num} 张采集成功<br>`;
    } else {
        document.getElementById('capture-log').innerHTML +=
            `<span style="color:#dc2626">&#10007;</span> ${resp.message}<br>`;
    }
}

// 自动采集
document.getElementById('btn-auto-capture').addEventListener('click', () => {
    const pid = document.getElementById('capture-person').value;
    if (!pid) { toast('请先选择人员', 'warning'); return;
    }
    captureTarget = parseInt(document.getElementById('capture-target').value) || 30;
    captureCount = 0;
    document.getElementById('capture-log').innerHTML = '';
    document.getElementById('capture-progress').textContent = '自动采集中...';

    if (captureInterval) clearInterval(captureInterval);
    captureInterval = setInterval(async () => {
        await captureOnce();
        if (captureCount >= captureTarget) {
            clearInterval(captureInterval);
            captureInterval = null;
            document.getElementById('capture-progress').textContent = `采集完成！共 ${captureCount} 张`;
            toast(`人脸采集完成，共 ${captureCount} 张样本`, 'success');
        }
    }, 500);
});


// ═══════════════════════════════════════════════════════
//  实时识别
// ═══════════════════════════════════════════════════════

let recognizeStream = null;
let recognizeRunning = false;

document.getElementById('btn-start-recognize').addEventListener('click', async () => {
    const btn = document.getElementById('btn-start-recognize');
    if (recognizeRunning) {
        // 停止
        recognizeRunning = false;
        btn.textContent = '开始识别';
        if (recognizeStream) {
            recognizeStream.getTracks().forEach(t => t.stop());
            recognizeStream = null;
        }
        document.getElementById('recognize-overlay').style.display = 'flex';
        document.getElementById('recognize-timer').textContent = '';
        return;
    }

    const statusEl = document.getElementById('verdict-status');
    const nameEl = document.getElementById('verdict-name');
    const detailEl = document.getElementById('verdict-detail');

    // 重置显示
    document.getElementById('verdict-placeholder').style.display = 'block';
    document.getElementById('verdict-result-block').style.display = 'none';
    statusEl.textContent = '';
    nameEl.textContent = '';
    detailEl.textContent = '';
    document.getElementById('recognize-timer').textContent = '';

    // 检查模型
    const statusResp = await API.get('/api/model/status');
    if (!statusResp || !statusResp.data.trained) {
        toast('模型未训练，请先注册人员并训练模型', 'warning');
        return;
    }

    try {
        recognizeStream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
        document.getElementById('recognize-video').srcObject = recognizeStream;
        document.getElementById('recognize-overlay').style.display = 'none';
        recognizeRunning = true;
        btn.textContent = '停止识别';
    } catch (err) {
        toast('无法访问摄像头', 'error');
        return;
    }

    // 3 秒采集
    const canvas = document.getElementById('recognize-canvas');
    const video = document.getElementById('recognize-video');
    const images = [];
    const duration = 3;
    const interval = 200;

    for (let t = 3; t >= 0; t -= 0.2) {
        document.getElementById('recognize-timer').textContent = `剩余 ${t.toFixed(1)}s`;
        await sleep(200);
        if (!recognizeRunning) return;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        images.push(canvas.toDataURL('image/jpeg', 0.8));
    }

    document.getElementById('recognize-timer').textContent = '识别中...';
    const resp = await API.post('/api/recognize/quick', { images });
    recognizeRunning = false;
    btn.textContent = '开始识别';
    if (recognizeStream) { recognizeStream.getTracks().forEach(t => t.stop()); recognizeStream = null; }
    document.getElementById('recognize-timer').textContent = '';

    if (resp && resp.success) {
        const v = resp.data.verdict;
        const statusEl = document.getElementById('verdict-status');
        const nameEl = document.getElementById('verdict-name');
        const detailEl = document.getElementById('verdict-detail');

        document.getElementById('verdict-placeholder').style.display = 'none';
        const resultBlock = document.getElementById('verdict-result-block');
        resultBlock.style.display = 'block';

        if (v.result === '允许通行') {
            const titleDiv = document.createElement('div');
            titleDiv.className = 'verdict-title allow';
            titleDiv.textContent = '允许通行';
            document.getElementById('verdict-status').innerHTML = '&#9989;';
            document.getElementById('verdict-status').style.fontSize = '52px';
            nameEl.innerHTML = v.name;
            detailEl.innerHTML = `<span>部门</span> ${v.department} &nbsp; <span>置信度</span> ${(100 - v.confidence).toFixed(1)}%`;
        } else {
            const titleDiv = document.createElement('div');
            titleDiv.className = 'verdict-title deny';
            titleDiv.textContent = '拒绝通行';
            document.getElementById('verdict-status').innerHTML = '&#10060;';
            document.getElementById('verdict-status').style.fontSize = '52px';
            nameEl.innerHTML = v.name;
            detailEl.innerHTML = `<span>部门</span> ${v.department} &nbsp; <span>权限</span> ${v.permission}`;
        }
        toast(`识别结果: ${v.name} - ${v.result}`, v.result==='允许通行'?'success':'error');
    } else {
        toast('未检测到人脸', 'warning');
    }
});


// ═══════════════════════════════════════════════════════
//  通行记录
// ═══════════════════════════════════════════════════════

let recordsPage = 1;

async function loadRecords(page = 1) {
    recordsPage = page;
    const resp = await API.get(`/api/records?page=${page}&per_page=20`);
    if (!resp || !resp.success) return;

    const tbody = document.querySelector('#records-table tbody');
    tbody.innerHTML = resp.data.records.map(r => `
        <tr>
            <td>${r.record_id}</td>
            <td>${r.access_time}</td>
            <td>${esc(r.name)}</td>
            <td>${esc(r.department)}</td>
            <td><span class="badge ${r.access_result==='允许通行'?'badge-allow':'badge-deny'}">${r.access_result}</span></td>
            <td>${(100 - r.confidence).toFixed(1)}%</td>
            <td><button class="btn btn-sm btn-danger" onclick="deleteRecord(${r.record_id})">删除</button></td>
        </tr>
    `).join('');

    // 分页
    const total = resp.data.total;
    const totalPages = Math.ceil(total / 20);
    let paginationHtml = '';
    for (let i = 1; i <= totalPages; i++) {
        paginationHtml += `<button class="${i===page?'active':''}" onclick="loadRecords(${i})" ${i===page?'disabled':''}>${i}</button>`;
    }
    document.getElementById('records-pagination').innerHTML = paginationHtml;
}

async function deleteRecord(id) {
    if (!confirm('确定删除此记录？')) return;
    const resp = await API.del(`/api/records/${id}`);
    if (resp && resp.success) toast('已删除', 'success');
    loadRecords(recordsPage);
}

// 清理记录
document.getElementById('btn-clear-records').addEventListener('click', () => {
    const dateStr = prompt('清除此日期之前的记录（格式 YYYY-MM-DD）:');
    if (!dateStr) return;
    API.post('/api/records/clear', { before_date: dateStr }).then(r => {
        if (r && r.success) toast(`已清除 ${r.data.deleted} 条记录`, 'success');
        loadRecords(recordsPage);
    });
});


// ═══════════════════════════════════════════════════════
//  数据分析
// ═══════════════════════════════════════════════════════

let charts = {};

async function loadAnalytics() {
    const [daily, hourly, pie, top] = await Promise.all([
        API.get('/api/analytics/daily'),
        API.get('/api/analytics/hourly'),
        API.get('/api/analytics/result-pie'),
        API.get('/api/analytics/top-persons')
    ]);

    if (daily && daily.success) renderDailyChart(daily.data);
    if (hourly && hourly.success) renderHourlyChart(hourly.data);
    if (pie && pie.success) renderPieChart(pie.data);
    if (top && top.success) renderTopChart(top.data);
}

function renderDailyChart(data) {
    if (charts.daily) charts.daily.destroy();
    charts.daily = new Chart(document.getElementById('chart-daily'), {
        type: 'line',
        data: {
            labels: data.dates,
            datasets: [{ label: '通行人数', data: data.counts, borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,0.1)', fill: true, tension: 0.3 }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });
}

function renderHourlyChart(data) {
    if (charts.hourly) charts.hourly.destroy();
    charts.hourly = new Chart(document.getElementById('chart-hourly'), {
        type: 'bar',
        data: {
            labels: data.hours,
            datasets: [
                { label: '允许', data: data.allows, backgroundColor: '#22c55e' },
                { label: '拒绝', data: data.denies, backgroundColor: '#ef4444' }
            ]
        },
        options: { responsive: true, maintainAspectRatio: false, scales: { x: { stacked: true }, y: { stacked: true } } }
    });
}

function renderPieChart(data) {
    if (charts.pie) charts.pie.destroy();
    charts.pie = new Chart(document.getElementById('chart-pie'), {
        type: 'doughnut',
        data: {
            labels: data.labels,
            datasets: [{ data: data.values, backgroundColor: ['#22c55e', '#ef4444', '#f59e0b', '#3b82f6'] }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });
}

function renderTopChart(data) {
    if (charts.top) charts.top.destroy();
    charts.top = new Chart(document.getElementById('chart-top'), {
        type: 'bar',
        data: {
            labels: data.names,
            datasets: [{ label: '通行次数', data: data.counts, backgroundColor: '#8b5cf6' }]
        },
        options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y' }
    });
}


// ═══════════════════════════════════════════════════════
//  管理员账户管理
// ═══════════════════════════════════════════════════════

async function loadAdmins() {
    const resp = await API.get('/api/admins');
    if (!resp || !resp.success) return;
    const tbody = document.querySelector('#admins-table tbody');
    tbody.innerHTML = resp.data.map(a => `
        <tr>
            <td><strong>${esc(a.username)}</strong></td>
            <td>${a.create_time}</td>
            <td class="actions">
                <button class="btn btn-sm btn-primary" onclick="changePassword('${esc(a.username)}')">修改密码</button>
                <button class="btn btn-sm btn-danger" onclick="deleteAdmin('${esc(a.username)}')">删除</button>
            </td>
        </tr>
    `).join('');
}

document.getElementById('btn-add-admin').addEventListener('click', () => {
    document.getElementById('form-admin-username').value = '';
    document.getElementById('form-admin-password').value = '';
    showModal('modal-admin');
});

document.getElementById('btn-save-admin').addEventListener('click', async () => {
    const username = document.getElementById('form-admin-username').value.trim();
    const password = document.getElementById('form-admin-password').value.trim();
    if (!username || !password) { toast('账号和密码不能为空', 'error'); return; }
    const resp = await API.post('/api/admins', { username, password });
    if (resp && resp.success) {
        toast(resp.message, 'success');
        hideModal('modal-admin');
        loadAdmins();
    } else toast(resp.message || '添加失败', 'error');
});

function changePassword(username) {
    document.getElementById('form-pw-username').value = username;
    document.getElementById('form-pw-password').value = '';
    showModal('modal-password');
}

document.getElementById('btn-save-password').addEventListener('click', async () => {
    const username = document.getElementById('form-pw-username').value;
    const password = document.getElementById('form-pw-password').value.trim();
    if (!password) { toast('密码不能为空', 'error'); return; }
    const resp = await API.put('/api/admins/password', { username, password });
    if (resp && resp.success) {
        toast('密码已修改', 'success');
        hideModal('modal-password');
    } else toast(resp.message || '修改失败', 'error');
});

function deleteAdmin(username) {
    document.getElementById('confirm-message').textContent = `确定要删除管理员「${username}」吗？`;
    document.getElementById('btn-confirm-ok').onclick = async () => {
        const resp = await API.del(`/api/admins/${username}`);
        if (resp && resp.success) {
            toast(resp.message, 'success');
            hideModal('modal-confirm');
            loadAdmins();
        } else toast(resp.message || '删除失败', 'error');
    };
    showModal('modal-confirm');
}


// ═══════════════════════════════════════════════════════
//  工具函数
// ═══════════════════════════════════════════════════════

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

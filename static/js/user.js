/**
 * 用户刷脸通行页面逻辑
 */

let stream = null;
let scanning = false;

document.getElementById('btn-user-recognize').addEventListener('click', async () => {
    const btn = document.getElementById('btn-user-recognize');

    if (scanning) {
        stopScan();
        btn.textContent = '开始识别 (3秒)';
        return;
    }

    // 启动摄像头
    try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
        document.getElementById('user-video').srcObject = stream;
    } catch (err) {
        showResult('error', '摄像头不可用', err.message);
        return;
    }

    scanning = true;
    btn.textContent = '识别中...';
    btn.disabled = true;

    // 视觉效果
    document.getElementById('user-video-box').classList.add('recognizing');
    document.getElementById('user-result').classList.remove('has-result');

    // 重置结果
    document.getElementById('result-icon').className = 'result-icon waiting';
    document.getElementById('result-icon').textContent = '\u23F3';
    document.getElementById('result-text').textContent = '识别中...';
    document.getElementById('result-detail').textContent = '';

    // 3 秒采集
    const video = document.getElementById('user-video');
    const canvas = document.getElementById('user-canvas');
    const images = [];

    for (let t = 3; t > 0; t--) {
        document.getElementById('user-timer').textContent = `剩余 ${t} 秒`;
        await sleep(1000);
        if (!scanning) break;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        images.push(canvas.toDataURL('image/jpeg', 0.8));
    }

    if (!scanning) return;
    document.getElementById('user-timer').textContent = '正在分析...';

    // 发送到后端
    try {
        const resp = await fetch('/api/recognize/quick', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ images })
        });
        const data = await resp.json();

        if (data.success) {
            const v = data.data.verdict;
            if (v.result === '允许通行') {
                showResult('allow', `${v.name} - 允许通行`,
                    `部门: ${v.department} | 置信度: ${(100 - v.confidence).toFixed(1)}%`);
            } else {
                showResult('deny', `${v.name} - 拒绝通行`,
                    `部门: ${v.department} | 权限: ${v.permission}`);
            }
        } else {
            showResult('deny', '未识别到人脸', '请正对摄像头并确保光线充足');
        }
    } catch (err) {
        showResult('deny', '识别失败', '网络错误');

    }

    stopScan();
    btn.textContent = '开始识别 (3秒)';
    btn.disabled = false;
    scanning = false;
    document.getElementById('user-video-box').classList.remove('recognizing');
});

function showResult(type, text, detail) {
    const icon = document.getElementById('result-icon');
    const resultPanel = document.getElementById('user-result');
    resultPanel.classList.add('has-result');

    if (type === 'allow') {
        icon.className = 'result-icon allow';
        icon.textContent = '\u2705';
    } else {
        icon.className = 'result-icon deny';
        icon.textContent = '\u274C';
    }
    document.getElementById('result-text').textContent = text;
    document.getElementById('result-detail').textContent = detail;
    document.getElementById('user-timer').textContent = '';
}

function stopScan() {
    if (stream) {
        stream.getTracks().forEach(t => t.stop());
        stream = null;
    }
    document.getElementById('user-video').srcObject = null;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

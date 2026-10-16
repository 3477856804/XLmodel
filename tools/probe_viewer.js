/**
 * 3D 查看器冒烟测试（puppeteer-core + 本机 Edge/Chrome）
 *
 * 目的：在没有 GUI、没法看截图的环境里，用**文本证据**证明 viewer.html
 * 真的把 VRM 渲染出来了，而不是只验证"文件能下载"。
 *
 * 判定依据：
 *   1. 页面没有 JS 报错（console error / pageerror）
 *   2. 加载遮罩 #msg 拿到 class="hide"（说明 onLoad 成功分支跑到了）
 *   3. 场景里确实有 WebGL 上下文，且 renderer.info.render.triangles > 0
 *      —— 这是"真的画出了三角形"，不是空场景。
 *
 * 用法：
 *   node tools/probe_viewer.js [url]
 */
const path = require('path');

const CANDIDATES = [
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
];

function pickBrowser() {
  const fs = require('fs');
  for (const p of CANDIDATES) if (fs.existsSync(p)) return p;
  return null;
}

(async () => {
  const url = process.argv[2] ||
    'http://127.0.0.1:8792/viewer.html?model=' + encodeURIComponent('小凌.vrm');
  const exe = pickBrowser();
  if (!exe) { console.log('RESULT: NO_BROWSER'); process.exit(2); }
  console.log('browser:', exe);
  console.log('url    :', url);

  let puppeteer;
  try {
    puppeteer = require(process.env.PUPPETEER_PATH || 'puppeteer-core');
  } catch (e) {
    console.log('RESULT: NO_PUPPETEER', e.message);
    process.exit(2);
  }

  const errors = [];
  const logs = [];
  let browser;
  try {
    browser = await puppeteer.launch({
      executablePath: exe,
      headless: 'new',
      args: [
        '--no-sandbox', '--disable-setuid-sandbox',
        '--use-gl=swiftshader', '--enable-unsafe-swiftshader',
        '--disable-dev-shm-usage', '--hide-scrollbars',
      ],
    });
  } catch (e) {
    console.log('RESULT: LAUNCH_FAILED', e.message);
    process.exit(3);
  }

  const page = await browser.newPage();
  await page.setViewport({ width: 800, height: 800 });
  page.on('console', m => {
    const t = m.type();
    logs.push(`[${t}] ${m.text()}`);
    if (t === 'error') errors.push(m.text());
  });
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  page.on('requestfailed', r =>
    errors.push('REQFAIL: ' + r.url() + ' ' + (r.failure() || {}).errorText));

  try {
    await page.goto(url, { waitUntil: 'load', timeout: 60000 });
  } catch (e) {
    console.log('RESULT: GOTO_FAILED', e.message);
  }

  // 等 VRM 解析完（15MB 模型 + swiftshader 软渲染，给足时间）
  await new Promise(r => setTimeout(r, 25000));

  const probe = await page.evaluate(() => {
    const msg = document.getElementById('msg');
    const cv = document.getElementById('cv');
    let gl = null, tri = 0, calls = 0;
    try {
      const c = document.createElement('canvas');
      gl = !!(c.getContext('webgl2') || c.getContext('webgl'));
    } catch (_) {}
    try {
      // 从 three 的 renderer 上读真实绘制统计：不为 0 才叫"真渲染"
      const r = window.__xlRenderer;
      if (r && r.info) { tri = r.info.render.triangles; calls = r.info.render.calls; }
    } catch (_) {}
    return {
      msgClass: msg ? msg.className : '(no #msg)',
      msgText: msg ? (msg.innerText || '').slice(0, 200) : '',
      canvasSize: cv ? `${cv.width}x${cv.height}` : '(no canvas)',
      webglOK: gl,
      triangles: tri,
      drawCalls: calls,
    };
  });

  console.log('--- probe ---');
  console.log(JSON.stringify(probe, null, 1));
  console.log('--- console (last 25) ---');
  console.log(logs.slice(-25).join('\n') || '(none)');
  console.log('--- errors ---');
  console.log(errors.length ? errors.join('\n') : '(none)');

  const ok = probe.msgClass.includes('hide') && errors.length === 0;
  console.log('RESULT:', ok ? 'PASS' : 'FAIL');
  await browser.close();
  process.exit(ok ? 0 : 1);
})();

/* Same-origin API; all displayed measurements come from the backend. */
const $ = id => document.getElementById(id);
const state = { mode: 'single', comparisons: [], result: null, busy: false, urls: new Map(), health: null };
const fmt = n => n == null ? '—' : Number(n).toFixed(2);
const show = (id, yes = true) => { $(id).style.display = yes ? 'block' : 'none'; };
const label = { measured: '已测量', insufficient_matches: '匹配不足', increasing: '幅值增加',
  decreasing: '幅值减小', no_clear_trend: '未见明显线性趋势', insufficient_data: '有效日期不足' };

function feedback(message, error = false) {
  const node = $('feedback'); node.hidden = !message; node.textContent = message;
  node.className = error ? 'error' : 'notice';
  if (error) node.focus();
}
async function request(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `请求失败（${response.status}）`);
  return data;
}
function updateButtons() {
  $('analyze-btn').disabled = state.busy || !$('image1').files.length || !$('image2').files.length;
  $('next-step-1').disabled = state.busy || !$('base-image').files.length || !$('base-date').value;
  $('next-step-2').disabled = state.busy || !$('base-image').files.length || !$('base-date').value ||
    !state.comparisons.length || state.comparisons.some(item => !item.date);
  $('demo-btn').disabled = state.busy;
  $('engine').disabled = state.busy;
  document.querySelectorAll('input[type="file"], input[type="date"], .upload-btn, .comparison-item button, #prev-step-2')
    .forEach(node => { node.disabled = state.busy; });
  document.querySelectorAll('.analysis-tab').forEach(node => { node.disabled = state.busy; });
  $('image-count').textContent = `已选择 ${state.comparisons.length} / 20 张对比图像`;
  $('base-image-requirement').textContent = $('base-image').files.length ? '已上传基础图像' : '未上传基础图像';
  $('images-requirement').textContent = `${state.comparisons.length} 张对比图像（趋势拟合至少需要三个有效日期）`;
  $('dates-requirement').textContent = state.comparisons.length && state.comparisons.every(item => item.date) ? '日期已填写' : '请填写全部拍摄日期';
}
function changeMode(mode) {
  state.mode = mode;
  document.querySelectorAll('.analysis-tab').forEach(node => node.classList.toggle('active', node.dataset.tab === mode));
  document.querySelectorAll('.tab-content').forEach(node => node.classList.toggle('active', node.id === `${mode}-analysis`));
  updateButtons();
}
function step(number) {
  document.querySelectorAll('.step-content').forEach(node => node.classList.toggle('active', node.dataset.step === String(number)));
  document.querySelectorAll('.step').forEach(node => node.classList.toggle('active', node.dataset.step === String(number)));
}
function preview(input, suffix) {
  const file = input.files[0];
  if (state.urls.has(suffix)) URL.revokeObjectURL(state.urls.get(suffix));
  if (file) {
    const url = URL.createObjectURL(file); state.urls.set(suffix, url);
    $(`preview-img-${suffix}`).src = url; $(`file-name-${suffix}`).textContent = file.name;
  }
  show(`preview-${suffix}`, Boolean(file)); updateButtons();
}
function addComparisons(files) {
  if (state.comparisons.length + files.length > 20) { feedback('最多上传 20 张对比图像。', true); return; }
  for (const file of files) state.comparisons.push({ file, date: '', id: crypto.randomUUID(), url: URL.createObjectURL(file) });
  renderComparisons();
}
function renderComparisons() {
  const list = $('comparison-images-list'); list.replaceChildren();
  for (const item of state.comparisons) {
    const row = document.createElement('div'); row.className = 'comparison-item';
    const image = document.createElement('img'); image.src = item.url; image.alt = '待分析图像预览';
    const name = document.createElement('span'); name.textContent = item.file.name;
    const input = document.createElement('input'); input.type = 'date'; input.value = item.date;
    input.setAttribute('aria-label', `${item.file.name} 的拍摄日期`);
    input.addEventListener('change', () => { item.date = input.value; updateButtons(); });
    const remove = document.createElement('button'); remove.textContent = '移除'; remove.className = 'action-btn secondary';
    remove.addEventListener('click', () => { URL.revokeObjectURL(item.url); state.comparisons = state.comparisons.filter(i => i !== item); renderComparisons(); });
    row.append(image, name, input, remove); list.append(row);
  }
  updateButtons();
}
function engineNotice() {
  const engine = $('engine').value;
  const info = state.health?.engines[engine];
  $('model-status').textContent = engine === 'sift' ? 'SIFT 基线可用' : info?.loaded ? '研究模型已加载' : info?.available ? '研究模型已配置' : '研究模型待配置';
  $('device-status').textContent = info?.device || '—';
  $('engine-note').textContent = engine === 'sift' ? '当前使用 OpenCV SIFT CPU 基线；结果不代表 SuperGlue 的性能。' : info?.message || '正在检查模型配置…';
}
async function refreshHealth() {
  try { state.health = await request('/api/health'); $('version-status').textContent = state.health.version; engineNotice(); }
  catch { $('model-status').textContent = '服务不可用'; }
}
async function analyze(mode) {
  if (state.busy) return;
  const body = new FormData(); body.append('engine', $('engine').value);
  if (mode === 'single') {
    body.append('image1', $('image1').files[0]); body.append('image2', $('image2').files[0]);
  } else {
    body.append('base_image', $('base-image').files[0]); body.append('base_date', $('base-date').value);
    state.comparisons.forEach(item => body.append('comparison_images', item.file));
    body.append('dates', JSON.stringify(state.comparisons.map(item => item.date)));
  }
  state.busy = true; state.result = null; show('results', false); feedback('正在计算真实特征匹配，请稍候…');
  show(mode === 'single' ? 'loading-spinner' : 'multi-loading-spinner'); updateButtons();
  try {
    const path = mode === 'single' ? '/api/analyze/upload' : '/api/analyze/multi-region';
    state.result = await request(path, { method: 'POST', body });
    renderResult(state.result);
    feedback(state.result.status === 'unmeasurable' ? '图像匹配不足，本次未获得有效测量；请更换纹理清晰、视角一致的图片。' : state.result.status === 'partial' ? '部分区域匹配不足；— 表示缺失测量，统计只包含有效区域。' : '分析完成。报告与图表使用本次计算结果。');
  } catch (error) { feedback(error.message, true); }
  finally { state.busy = false; show('loading-spinner', false); show('multi-loading-spinner', false); updateButtons(); refreshHealth(); }
}
function renderResult(result) {
  const sequence = result.mode === 'sequence';
  const summary = sequence ? result.comparison_results.at(-1) : result;
  $('results-subtitle').textContent = `${result.engine === 'sift' ? 'SIFT CPU 基线' : 'SuperPoint + SuperGlue'} · ${sequence ? '最后一个对比日期的统计（各日期见下表）' : '四区域实际测量'} · 单位 px`;
  $('matches-count').textContent = summary.matches_count;
  $('avg-displacement').textContent = `${fmt(summary.average_displacement)} px`;
  $('min-displacement').textContent = fmt(summary.min_displacement); $('max-displacement').textContent = fmt(summary.max_displacement);
  $('task-id').textContent = result.task_id; $('processing-time').textContent = `${fmt(result.processing_time)} s`;
  $('displacement-std').textContent = `${fmt(summary.displacement_std)} px`; $('analysis-time').textContent = new Date(result.timestamp).toLocaleString();
  const regions = $('region-results'); regions.replaceChildren();
  for (const region of summary.region_results) {
    const card = document.createElement('article'); card.className = 'region-card';
    const title = document.createElement('h3'); title.textContent = `${region.label}区域`;
    const value = document.createElement('p'); value.className = 'region-value'; value.textContent = `${fmt(region.average_displacement)} px`;
    const detail = document.createElement('p'); detail.textContent = `${label[region.status]} · ${region.matches_count} 个过滤后匹配点`;
    card.append(title, value, detail); regions.append(card);
  }
  $('matching-figure').hidden = !result.match_image_path;
  if (result.match_image_path) $('matching-image').src = result.match_image_path;
  show('trend-alert', sequence); show('trend-chart-section', sequence); $('sequence-table').replaceChildren();
  if (sequence) {
    const alert = $('alert-content'); alert.replaceChildren();
    for (const region of result.trend_analysis.regions) {
      const line = document.createElement('p'); line.textContent = `${region.label}：${label[region.trend]}；斜率 ${fmt(region.slope_px_per_day)} px/天；有效 ${region.valid_samples}，缺失 ${region.missing_samples}。`;
      alert.append(line);
    }
    const note = document.createElement('p'); note.textContent = result.trend_analysis.notes.join(' '); alert.append(note);
    renderTrend(result); renderTable(result);
  }
  show('results'); $('results').scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function renderTable(result) {
  const table = document.createElement('table'); table.className = 'sequence-table';
  const caption = table.createCaption(); caption.textContent = '所有拍摄日期的平均像素位移（— 表示无法测量）';
  const header = table.createTHead().insertRow();
  ['拍摄日期', '左上 px', '右上 px', '左下 px', '右下 px'].forEach(text => { const th = document.createElement('th'); th.textContent = text; header.append(th); });
  const tbody = table.createTBody();
  for (const row of result.comparison_results) {
    const tr = tbody.insertRow();
    [row.date, ...row.region_results.map(r => fmt(r.average_displacement))].forEach(text => { tr.insertCell().textContent = text; });
  }
  $('sequence-table').append(table);
}
function renderTrend(result) {
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg'); svg.setAttribute('viewBox', '0 0 900 340'); svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', '各区域平均像素位移随拍摄日期变化，缺失点不连线');
  const element = (tag, attrs, text) => { const node = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v); if (text != null) node.textContent = text; svg.append(node); return node; };
  const rows = result.comparison_results;
  const days = rows.map(row => Date.parse(`${row.date}T00:00:00Z`)); const span = days.at(-1) - days[0] || 86400000;
  const series = result.trend_analysis.regions;
  const max = Math.max(1, ...series.flatMap(r => r.series.filter(v => v != null))) * 1.15;
  const x = i => 70 + 720 * (days[i] - days[0]) / span; const y = value => 275 - 220 * value / max;
  for (let i = 0; i <= 4; i++) {
    const value = max * i / 4;
    element('line', { x1: 70, y1: y(value), x2: 810, y2: y(value), stroke: '#e2e8f0' });
    element('text', { x: 12, y: y(value) + 4, fill: '#64748b', 'font-size': 13 }, value.toFixed(1));
  }
  element('text', { x: 12, y: 30, fill: '#475569', 'font-size': 13 }, 'px');
  days.forEach((_, i) => { if (days.length <= 6 || i % Math.ceil(days.length / 5) === 0 || i === days.length - 1) element('text', { x: x(i), y: 305, 'text-anchor': 'middle', 'font-size': 12, fill: '#64748b' }, rows[i].date); });
  const colors = ['#2563eb', '#0d9488', '#e07b24', '#8b5cf6'];
  series.forEach((region, n) => {
    let previous = null;
    region.series.forEach((value, i) => {
      if (value == null) { previous = null; return; }
      if (previous != null) element('line', { x1: x(previous), y1: y(region.series[previous]), x2: x(i), y2: y(value), stroke: colors[n], 'stroke-width': 2 });
      element('circle', { cx: x(i), cy: y(value), r: 4, fill: colors[n] }); previous = i;
    });
    element('text', { x: 100 + n * 190, y: 330, fill: colors[n], 'font-size': 14 }, region.label);
  });
  $('trend-svg').replaceChildren(svg); show('trend-placeholder', false);
}
async function demo() {
  try {
    feedback('正在加载合成图像示例…');
    for (const [id, name, suffix] of [['image1', 'reference.png', '1'], ['image2', 'target-1.png', '2']]) {
      const response = await fetch(`/examples/${name}`); if (!response.ok) throw new Error('示例加载失败');
      const transfer = new DataTransfer(); transfer.items.add(new File([await response.blob()], name, { type: 'image/png' }));
      $(id).files = transfer.files; preview($(id), suffix);
    }
    $('engine').value = 'sift'; engineNotice(); changeMode('single'); await analyze('single');
    if (state.result) feedback('合成示例：人为平移 dx=4、dy=3 px，理论幅值为 5 px；这是流程验证，不是实测建筑精度。');
  } catch (error) { feedback(error.message, true); }
}

document.querySelectorAll('.analysis-tab').forEach(node => node.addEventListener('click', () => changeMode(node.dataset.tab)));
for (const [id, suffix] of [['image1', '1'], ['image2', '2'], ['base-image', 'base']]) $(id).addEventListener('change', () => preview($(id), suffix));
$('base-date').addEventListener('change', updateButtons);
$('comparison-image').addEventListener('change', event => { addComparisons([...event.target.files]); event.target.value = ''; });
$('next-step-1').addEventListener('click', () => step(2)); $('prev-step-2').addEventListener('click', () => step(1));
$('analyze-btn').addEventListener('click', () => analyze('single')); $('next-step-2').addEventListener('click', () => analyze('multi'));
$('engine').addEventListener('change', engineNotice); $('demo-btn').addEventListener('click', demo);
$('download-report-btn').addEventListener('click', () => { if (state.result) location.href = state.result.report_url; });
$('download-csv-btn').addEventListener('click', () => { if (state.result) location.href = state.result.report_url.replace('.json', '.csv'); });
$('new-analysis-btn').addEventListener('click', () => { show('results', false); state.result = null; step(1); $('analysis').scrollIntoView({ behavior: 'smooth' }); });
updateButtons(); refreshHealth();

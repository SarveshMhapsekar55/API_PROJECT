/* ============================================================
   AGROSCAN FRONTEND LOGIC
   Talks to the FastAPI backend:
     POST /api/crop/analyze  -> crop + disease diagnosis
     POST /api/soil/assess   -> soil questionnaire result
   ============================================================ */

const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const safe = (v, d = '—') => (v === undefined || v === null || v === '') ? d : v;

let API_BASE = 'http://127.0.0.1:8000';
let selectedImage = null;
let previewUrl = null;
let lastReport = null;
let lastSoil = null;
let history_ = [];

/* ------------------------------------------------------------
   SETTINGS (persisted in this browser)
   ------------------------------------------------------------ */
function loadSettings() {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem('agroscan_settings') || '{}'); } catch { saved = {}; }
  API_BASE = saved.apiBase || API_BASE;
  const lang = saved.defaultLanguage || 'English';
  $('apiBaseInput').value = API_BASE;
  $('defaultLanguage').value = lang;
  $('language').value = lang;
}
$('saveSettingsBtn').onclick = () => {
  const apiBase = $('apiBaseInput').value.trim() || 'http://127.0.0.1:8000';
  const defaultLanguage = $('defaultLanguage').value;
  localStorage.setItem('agroscan_settings', JSON.stringify({ apiBase, defaultLanguage }));
  API_BASE = apiBase;
  $('language').value = defaultLanguage;
  $('settingsStatus').textContent = 'Settings saved.';
  $('settingsStatus').classList.remove('error');
  toast('Settings saved');
};

/* ------------------------------------------------------------
   TOAST
   ------------------------------------------------------------ */
let toastTimer = null;
function toast(msg) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 2400);
}

/* ------------------------------------------------------------
   SIDEBAR NAVIGATION
   ------------------------------------------------------------ */
const PAGE_META = {
  scan: ['AI POWERED AGRICULTURE', 'Crop Scan'],
  diagnosis: ['STEP 2 · AI REPORT', 'AI Diagnosis'],
  soil: ['OPTIONAL', 'Soil Assessment'],
  report: ['FINAL', 'Complete Report'],
  history: ['THIS SESSION', 'Scan History'],
  settings: ['PREFERENCES', 'Settings']
};

function switchSection(name) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active-section'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.target === name));
  const target = $(name);
  if (target) target.classList.add('active-section');
  const meta = PAGE_META[name];
  if (meta) { $('pageEyebrow').textContent = meta[0]; $('pageTitle').textContent = meta[1]; }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

document.querySelectorAll('.nav-item').forEach(btn => {
  btn.onclick = () => switchSection(btn.dataset.target);
});

$('heroScanBtn').onclick = () => $('uploadBox').scrollIntoView({ behavior: 'smooth', block: 'center' });
$('newScanBtn2').onclick = () => switchSection('scan');
$('goSoilBtn').onclick = () => switchSection('soil');
$('finalSoilLink').onclick = e => { e.preventDefault(); switchSection('soil'); };

/* ------------------------------------------------------------
   IMAGE UPLOAD + PREVIEW
   ------------------------------------------------------------ */
const uploadBox = $('uploadBox');
uploadBox.addEventListener('click', e => {
  if (!e.target.closest('#previewChange')) $('imageInput').click();
});
$('previewChange').addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); $('imageInput').click(); });
$('imageInput').addEventListener('change', () => pick($('imageInput').files[0]));

uploadBox.addEventListener('dragover', e => { e.preventDefault(); uploadBox.classList.add('drag'); });
uploadBox.addEventListener('dragleave', () => uploadBox.classList.remove('drag'));
uploadBox.addEventListener('drop', e => {
  e.preventDefault();
  uploadBox.classList.remove('drag');
  const f = e.dataTransfer.files[0];
  if (f) {
    pick(f);
    const dt = new DataTransfer();
    dt.items.add(f);
    $('imageInput').files = dt.files;
  }
});

function pick(f) {
  if (!f || !f.type || !f.type.startsWith('image/')) {
    setScanStatus('Please select a valid image file.', true);
    return;
  }
  selectedImage = f;
  previewUrl = URL.createObjectURL(f);
  $('previewImage').src = previewUrl;
  $('previewImage').style.display = 'block';
  $('uploadEmpty').classList.add('hidden');
  $('previewMeta').classList.remove('hidden');
  $('previewName').textContent = f.name;
  $('previewSize').textContent = Math.round(f.size / 1024) + ' KB';
  setScanStatus('');
}

function setScanStatus(msg, isError) {
  const el = $('scanStatus');
  el.textContent = msg || '';
  el.classList.toggle('error', !!isError);
}

/* ------------------------------------------------------------
   CROP SCAN SUBMISSION
   ------------------------------------------------------------ */
$('scanForm').addEventListener('submit', async e => {
  e.preventDefault();
  const location = $('location').value.trim();

  if (!selectedImage) return setScanStatus('Please choose a leaf image first.', true);
  if (!location) return setScanStatus('Please enter the crop location.', true);

  const fd = new FormData();
  fd.append('image', selectedImage, selectedImage.name);
  fd.append('location', location);
  fd.append('language', $('language').value);

  const btn = $('scanBtn');
  btn.disabled = true;
  btn.textContent = 'Analyzing your leaf…';
  setScanStatus('');

  try {
    const res = await fetch(`${API_BASE}/api/crop/analyze`, { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok || data.status !== 'success') {
      throw new Error(data.message || data.detail || 'Crop analysis failed.');
    }
    lastSoil = null;
    handleCropResult(data);
  } catch (err) {
    setScanStatus('Analysis failed: ' + err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Analyze Crop with AI →';
  }
});

function handleCropResult(data) {
  lastReport = data;
  renderDiagnosis(data);
  addHistoryEntry(data);
  updateFinalReport();
  updateWeatherPill(data);
  switchSection('diagnosis');
}

function updateWeatherPill(data) {
  const w = data.weather_risk || data.weather || {};
  const l = data.location_information || {};
  if (l.matched_location) {
    $('weatherPill').textContent = `📍 ${l.matched_location} · ${safe(w.condition, '—')} · ${w.temperature != null ? w.temperature + '°C' : '—'}`;
  }
}

/* ------------------------------------------------------------
   RENDER DIAGNOSIS
   ------------------------------------------------------------ */
function severityScoreOf(h) {
  if (typeof h.severity_score === 'number') return h.severity_score;
  const s = String(h.severity || '').toLowerCase();
  if (s.includes('healthy')) return 5;
  if (s.includes('moderate')) return 55;
  if (s.includes('high')) return 85;
  return 55;
}

function severityClass(score) {
  if (score <= 25) return 'low';
  if (score <= 60) return 'moderate';
  return 'high';
}

function severityText(score) {
  if (score <= 20) return 'Plant appears healthy based on the detected class.';
  if (score <= 45) return 'Lower disease concern. Continue regular monitoring.';
  if (score <= 70) return 'This condition requires attention and monitoring.';
  return 'Higher disease concern. Early action is recommended.';
}

function renderDiagnosis(d) {
  const a = d.ai_analysis || {};
  const h = d.health_assessment || {};
  const w = d.weather_risk || d.weather || {};
  const l = d.location_information || {};
  const req = d.request_information || {};

  $('diagnosisEmpty').classList.add('hidden');
  $('diagnosisContent').classList.remove('hidden');
  $('diagnosisSubtitle').textContent = `Analysis completed for ${safe(req.location, 'your location')}.`;

  $('reportImage').src = previewUrl;
  $('reportFile').textContent = safe(req.filename);
  $('reportLoc').textContent = '📍 ' + safe(req.location);

  $('crop').textContent = safe(a.crop);
  $('disease').textContent = safe(a.disease);
  $('confidence').textContent = a.confidence != null ? a.confidence + '%' : '—';
  $('confidenceBar').style.width = Math.min(Number(a.confidence || 0), 100) + '%';
  $('classesBadge').textContent = safe(a.classification_classes, 14) + ' classes';

  const score = severityScoreOf(h);
  $('sevScore').textContent = Math.round(score);
  const badge = $('severityBadge');
  badge.textContent = safe(h.severity);
  badge.className = 'severity-badge ' + severityClass(score);
  $('sevText').textContent = severityText(score);
  $('gaugeNeedle').style.transform = `rotate(${-90 + Math.min(Math.max(score, 0), 100) * 1.8}deg)`;

  $('matchedLocation').textContent = l.matched_location
    ? `📍 ${l.matched_location}${l.area ? ', ' + l.area : ''}${l.country ? ', ' + l.country : ''}`
    : `Weather for ${safe(req.location)}`;
  $('temp').textContent = w.temperature != null ? w.temperature + '°C' : '—';
  $('hum').textContent = w.humidity != null ? w.humidity + '%' : '—';
  $('rain').textContent = w.rain_probability != null ? w.rain_probability + '%' : '—';
  $('condition').textContent = safe(w.condition);
  $('riskLevel').textContent = w.risk_level ? w.risk_level + ' risk' : 'Risk not available';
  $('riskMsg').textContent = safe(w.risk_message, 'Current weather-based disease risk information.');
  $('coords').textContent = (l.latitude != null && l.longitude != null)
    ? `${Number(l.latitude).toFixed(4)}, ${Number(l.longitude).toFixed(4)}`
    : '—';
  $('elevation').textContent = l.elevation != null ? `Elevation ${l.elevation} m` : '';

  const symptoms = h.symptoms_detected || [];
  $('symptoms').innerHTML = symptoms.length
    ? symptoms.map(s => `<li>${esc(s)}</li>`).join('')
    : '<li>Assessment information not available.</li>';

  $('stage').textContent = safe(h.disease_stage);
  $('affected').textContent = safe(h.affected_area);
  $('treatment').textContent = safe(d.treatment_window);

  $('metaFile').textContent = safe(req.filename);
  $('metaLocation').textContent = safe(req.location);
  $('metaTime').textContent = new Date().toLocaleString();

  const icons = ['🧹', '🌬️', '🚿', '👀', '🌱', '🧤'];
  const actions = d.recommended_action || [];
  $('actions').innerHTML = actions.map((x, i) => `<div><span>${icons[i % icons.length]}</span> ${esc(x)}</div>`).join('');
}

/* ------------------------------------------------------------
   SOIL ASSESSMENT SUBMISSION
   ------------------------------------------------------------ */
$('soilForm').addEventListener('submit', async e => {
  e.preventDefault();
  const fields = ['soil_moisture', 'drainage', 'watering_frequency', 'plant_growth'];
  const fd = new FormData();
  for (const name of fields) {
    const checked = document.querySelector(`input[name="${name}"]:checked`);
    if (!checked) {
      $('soilStatus').textContent = 'Please answer all four questions before submitting.';
      $('soilStatus').classList.add('error');
      return;
    }
    fd.append(name, checked.value);
  }

  const btn = $('soilSubmitBtn');
  btn.disabled = true;
  btn.textContent = 'Assessing your soil…';
  $('soilStatus').textContent = '';
  $('soilStatus').classList.remove('error');

  try {
    const res = await fetch(`${API_BASE}/api/soil/assess`, { method: 'POST', body: fd });
    const text = await res.text();
    let data = {};
    try { data = JSON.parse(text); } catch { /* ignore */ }
    if (!res.ok || data.status !== 'success') {
      const detail = Array.isArray(data.detail) ? data.detail.map(x => x.msg).join(', ') : (data.message || 'Soil assessment failed.');
      throw new Error(detail);
    }
    lastSoil = data.soil_assessment || {};
    if (history_.length) history_[0].soil = lastSoil;
    renderSoilResult();
    updateFinalReport();
    $('soilForm').classList.add('hidden');
    $('soilResult').classList.remove('hidden');
    $('soilResult').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (err) {
    $('soilStatus').textContent = 'Soil assessment failed: ' + err.message;
    $('soilStatus').classList.add('error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generate Soil Assessment ✓';
  }
});

function renderSoilResult() {
  const s = lastSoil || {};
  const score = safe(s.health_score ?? s.score, 0);
  $('soilRing').style.setProperty('--score', score + '%');
  $('soilScoreNum').textContent = score;
  $('soilCondition').textContent = safe(s.condition);
  $('soilExplanation').textContent = safe(s.explanation);
  $('soilAdvice').innerHTML = (s.recommendations || []).map(r => `<li>${esc(r)}</li>`).join('');
}

$('retakeSoilBtn').addEventListener('click', () => {
  $('soilForm').reset();
  $('soilForm').classList.remove('hidden');
  $('soilResult').classList.add('hidden');
  $('soilStatus').textContent = '';
  $('soilForm').scrollIntoView({ behavior: 'smooth', block: 'start' });
});

/* ------------------------------------------------------------
   FINAL COMBINED REPORT
   ------------------------------------------------------------ */
function updateFinalReport() {
  if (!lastReport) {
    $('reportEmpty').classList.remove('hidden');
    $('finalReport').classList.add('hidden');
    return;
  }
  $('reportEmpty').classList.add('hidden');
  $('finalReport').classList.remove('hidden');

  const a = lastReport.ai_analysis || {};
  const h = lastReport.health_assessment || {};
  const w = lastReport.weather_risk || lastReport.weather || {};
  const l = lastReport.location_information || {};

  $('finalCrop').textContent = safe(a.crop);
  $('finalDisease').textContent = safe(a.disease);
  $('finalSeverity').textContent = safe(h.severity);

  $('finalWeather').textContent = w.temperature != null
    ? `Currently ${safe(w.condition, 'unknown conditions')}, ${w.temperature}°C with ${safe(w.humidity, '—')}% humidity near ${safe(l.matched_location, 'your location')}. Disease-weather risk: ${safe(w.risk_level, 'unavailable')}${w.risk_message ? ' — ' + w.risk_message : ''}.`
    : 'Weather information is not available for this scan.';

  if (lastSoil) {
    $('finalSoil').innerHTML = `${esc(lastSoil.condition)} (${esc(safe(lastSoil.health_score ?? lastSoil.score, 0))}/100). ${esc(lastSoil.explanation)}`;
  } else {
    $('finalSoil').innerHTML = 'Soil not assessed yet. <a href="#" id="finalSoilLink2">Assess soil →</a>';
    const link = $('finalSoilLink2');
    if (link) link.onclick = e => { e.preventDefault(); switchSection('soil'); };
  }

  const items = (lastReport.recommended_action || []).map(x => `<li>${esc(x)}</li>`);
  if (lastSoil && lastSoil.recommendations) {
    lastSoil.recommendations.forEach(r => items.push(`<li>🧪 Soil: ${esc(r)}</li>`));
  }
  $('finalActions').innerHTML = items.join('');
}

/* ------------------------------------------------------------
   HISTORY
   ------------------------------------------------------------ */
function addHistoryEntry(data) {
  history_.unshift({
    id: Date.now(),
    time: new Date(),
    report: data,
    soil: null,
    thumb: previewUrl
  });
  renderHistory();
}

function renderHistory() {
  if (!history_.length) {
    $('historyEmpty').classList.remove('hidden');
    $('historyList').classList.add('hidden');
    return;
  }
  $('historyEmpty').classList.add('hidden');
  $('historyList').classList.remove('hidden');
  $('historyList').innerHTML = history_.map(entry => {
    const a = entry.report.ai_analysis || {};
    const h = entry.report.health_assessment || {};
    return `<div class="history-card">
      <div class="hist-thumb"><img src="${entry.thumb}" alt="Scanned leaf"></div>
      <b>${esc(a.crop)} — ${esc(a.disease)}</b>
      <small>${esc(h.severity)} · ${entry.time.toLocaleString()}</small>
      <button type="button" class="secondary-btn" data-id="${entry.id}">View report</button>
    </div>`;
  }).join('');

  $('historyList').querySelectorAll('button[data-id]').forEach(btn => {
    btn.onclick = () => {
      const entry = history_.find(x => x.id === Number(btn.dataset.id));
      if (!entry) return;
      lastReport = entry.report;
      lastSoil = entry.soil;
      previewUrl = entry.thumb;
      renderDiagnosis(entry.report);
      updateFinalReport();
      switchSection('diagnosis');
    };
  });
}

/* ------------------------------------------------------------
   VOICE GUIDANCE (English / Hindi) + STOP
   ------------------------------------------------------------ */
function buildSpeechText(lang, includeSoil) {
  if (!lastReport) return '';
  const a = lastReport.ai_analysis || {};
  const h = lastReport.health_assessment || {};
  const w = lastReport.weather_risk || lastReport.weather || {};
  const l = lastReport.location_information || {};
  const soil = includeSoil ? lastSoil : null;

  if (lang === 'hi') {
    let text = `AgroScan रिपोर्ट। पौधे की पहचान ${a.crop || 'उपलब्ध नहीं'} है। बीमारी या स्थिति ${a.disease || 'उपलब्ध नहीं'} है। ` +
      `AI विश्वास स्तर ${a.confidence ?? 'उपलब्ध नहीं'} प्रतिशत है। बीमारी की गंभीरता ${h.severity || 'उपलब्ध नहीं'} है। ` +
      `प्रभावित क्षेत्र ${h.affected_area || 'उपलब्ध नहीं'}। उपचार के लिए सुझाव: ${lastReport.treatment_window || 'जल्दी कार्रवाई की सलाह'}। ` +
      `स्थान ${l.matched_location || lastReport.request_information?.location || 'उपलब्ध नहीं'}। ` +
      `तापमान ${w.temperature ?? 'उपलब्ध नहीं'} डिग्री सेल्सियस, नमी ${w.humidity ?? 'उपलब्ध नहीं'} प्रतिशत है। `;
    if (h.symptoms_detected?.length) text += 'देखे गए लक्षण: ' + h.symptoms_detected.join(', ') + '। ';
    if (lastReport.recommended_action?.length) text += 'सुझाए गए कदम: ' + lastReport.recommended_action.join(', ') + '। ';
    if (soil) text += `मिट्टी की स्थिति ${soil.condition || 'उपलब्ध नहीं'} है, स्कोर ${soil.score ?? 'उपलब्ध नहीं'} है। ${soil.explanation || ''}`;
    return text;
  }

  let text = `AgroScan crop health report. The identified crop is ${a.crop || 'not available'}. The detected disease or condition is ${a.disease || 'not available'}. ` +
    `AI confidence is ${a.confidence ?? 'not available'} percent. Disease severity is ${h.severity || 'not available'}. ` +
    `Affected area: ${h.affected_area || 'not available'}. Treatment window: ${lastReport.treatment_window || 'early action recommended'}. ` +
    `Location: ${l.matched_location || lastReport.request_information?.location || 'not available'}. ` +
    `Temperature is ${w.temperature ?? 'not available'} degrees Celsius. Humidity is ${w.humidity ?? 'not available'} percent. `;
  if (h.symptoms_detected?.length) text += 'Detected symptoms: ' + h.symptoms_detected.join(', ') + '. ';
  if (lastReport.recommended_action?.length) text += 'Recommended actions: ' + lastReport.recommended_action.join(', ') + '. ';
  if (soil) text += `Soil assessment is ${soil.condition || 'not available'} with a score of ${soil.score ?? 'not available'} out of 100. ${soil.explanation || ''}`;
  return text;
}

function speak(lang, includeSoil) {
  if (!('speechSynthesis' in window)) { toast('Voice guidance is not supported by this browser.'); return; }
  if (!lastReport) { toast('Run a crop scan first.'); return; }
  speechSynthesis.cancel();
  const text = buildSpeechText(lang, includeSoil);
  const u = new SpeechSynthesisUtterance(text);
  u.lang = lang === 'hi' ? 'hi-IN' : 'en-IN';
  u.rate = 0.92;
  speechSynthesis.speak(u);
}
function stopSpeech() { if ('speechSynthesis' in window) speechSynthesis.cancel(); }

$('voiceEn').onclick = () => speak('en', false);
$('voiceHi').onclick = () => speak('hi', false);
$('voiceStop').onclick = stopSpeech;
$('voiceFullEn').onclick = () => speak('en', true);
$('voiceFullHi').onclick = () => speak('hi', true);
$('voiceFullStop').onclick = stopSpeech;

/* ------------------------------------------------------------
   INIT
   ------------------------------------------------------------ */
loadSettings();
updateFinalReport();
renderHistory();

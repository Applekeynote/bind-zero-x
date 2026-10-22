'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
// User-supplied demo assets: never measurement or independent ground truth.
const photos = [
  {
    "file": "open-boxes-group",
    "label": "Open boxes group"
  },
  {
    "file": "open-boxes-trio",
    "label": "Open boxes trio"
  },
  {
    "file": "flat-jewel",
    "label": "Jewel sheets"
  },
  {
    "file": "flat-pastel",
    "label": "Pastel sheets"
  },
  {
    "file": "flat-primary",
    "label": "Primary sheets"
  },
  {
    "file": "flat-brown-spread",
    "label": "Brown sheets spread"
  },
  {
    "file": "flat-brown-pile",
    "label": "Brown sheets pile"
  },
  {
    "file": "flat-brown-five",
    "label": "Brown sheets five"
  },
  {
    "file": "flat-brown-three",
    "label": "Brown sheets three"
  }
].map((p, index) => ({ ...p, index, url: `/assets/photos/${p.file}.png`, width: 1448, height: 1086, type: 'PNG' }));
const ui = { session: null, runtime: null, sessions: [], page: 'overview', view: 'PHOTOS', camera: null, csrf: null, urls: [], photo: photos[2], selectedImage: null };
const worlds = { LAYER_ONLY: ['Layer slip only', 'LAYER SLIP ONLY', '▱'], LAYER_AND_ROPE: ['Layer slip + rope shift', 'LAYER SLIP + ROPE SHIFT', '⌁'] };
const views = { SIDE: 'Side', TOP: 'Top', ROPE_PATH: 'Rope path', KNOT_CLOSEUP: 'Knot close-up' };
const actions = { REORDER: 'Reorder the layers', REPOSITION_TWINE: 'Reposition the twine', RE_TIE: 'Review the knot', SPLIT_2: 'Split into two bundles', KEEP: 'Keep the current arrangement', ABSTAIN: 'Pause for more evidence' };
const signatures = { rope_moved: 'Rope moved', rope_still: 'Rope stayed still', layer_moves: 'Layer moved', layer_still: 'Layer stayed still', '?': 'Unable to determine' };
function escapeHTML(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]); }
function toast(message) { $('#toast').textContent = message; $('#toast').hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => $('#toast').hidden = true, 4500); }
async function api(path, data) {
  const response = await fetch('/api/console/' + path, { method: data === undefined ? 'GET' : 'POST', headers: data === undefined ? {} : { 'Content-Type': 'application/json', 'X-CSRF-Token': ui.csrf }, body: data === undefined ? undefined : JSON.stringify(data) });
  let result; try { result = await response.json(); } catch { throw new Error('Unable to read the server response.'); }
  if (response.status === 401) { location.replace('/'); throw new Error('Sign in to continue.'); }
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : `Request failed (${response.status}).`);
  return result;
}
function friendlyError(error) {
  return ({ OPENCV5_RUNTIME_REQUIRED: 'OpenCV 5 is required to analyze a capture.', VERSION_CONFLICT: 'This session changed. Reopen it from History.', EVIDENCE_UNAVAILABLE: 'An archived file is missing or has changed.', VIEW_BUDGET_EXHAUSTED_OR_TERMINAL: 'This observation session is complete.', MODEL_FALSIFIED_BY_OBSERVATION: 'The observation does not match the current model.', REUSED_IMAGE_NOT_NEW_EVIDENCE: 'Choose a new frame for this observation.', CONSOLE_SESSION_REQUIRED: 'Reload the page to reconnect.' })[error.message] || error.message;
}
function dateText(value) { return value ? new Intl.DateTimeFormat('en-GB', { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : '—'; }
function downloadJSON(value, filename) { const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' })); const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
function stopCamera() { ui.camera?.getTracks().forEach(track => track.stop()); ui.camera = null; }
function showModal(title, body) { stopCamera(); $('#modal-eyebrow').textContent = title; $('#modal-content').innerHTML = body; $('#modal').setAttribute('aria-label', $('.modal-title')?.textContent || title); if (!$('#modal').open) $('#modal').showModal(); }
function closeModal() { stopCamera(); $('#modal').close(); }
function showError(error, root = $('#modal-content')) { $('.error-message', root)?.remove(); const el = document.createElement('p'); el.className = 'error-message'; el.setAttribute('role', 'alert'); el.textContent = friendlyError(error); root.append(el); }
async function busy(button, job) { const original = button.textContent; button.disabled = true; button.textContent = 'Working…'; try { await job(); } catch (error) { if ($('#modal').open) showError(error); else toast(friendlyError(error)); } finally { button.disabled = false; button.textContent = original; } }
function idSuffix() { return [...crypto.getRandomValues(new Uint8Array(12))].map(v => v.toString(16).padStart(2, '0')).join(''); }
function base64(bytes) { let binary = ''; for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192)); return btoa(binary); }
async function sha256(bytes) { if (crypto.subtle) return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(n => n.toString(16).padStart(2, '0')).join(''); return (await api('digest', { bytes_b64: base64(bytes) })).sha256; }
function isPNG(bytes) { return [137, 80, 78, 71, 13, 10, 26, 10].every((b, i) => bytes[i] === b); }
async function fileBase64(file) { if (!file || file.size > 2500000) throw new Error('Choose four PNG files, up to 2.5 MB each.'); const bytes = new Uint8Array(await file.arrayBuffer()); if (!isPNG(bytes)) throw new Error(`${file.name} must be a PNG.`); return base64(bytes); }
function renderPhotoStrip() { $('#photo-strip').innerHTML = photos.map(p => `<button class="photo-thumb ${ui.photo?.index === p.index ? 'selected' : ''}" data-photo-index="${p.index}" aria-label="Open ${escapeHTML(p.label)}" aria-pressed="${ui.photo?.index === p.index}"><img src="${p.url}" alt="${escapeHTML(p.label)}" loading="lazy"><span>${String(p.index + 1).padStart(2, '0')}</span></button>`).join(''); }
function renderScene() {
  const captured = ui.session?.initial_capture_origin === 'SERVER_CAPTURED_PNG';
  const photoView = ui.view === 'PHOTOS' && (ui.photo || captured || ui.selectedImage);
  $('#scene').classList.toggle('photo-scene', Boolean(photoView));
  if (photoView) {
    const url = ui.photo?.url || ui.selectedImage || `/api/console/sessions/${encodeURIComponent(ui.session.session_id)}/frame0`;
    $('#scene-art').innerHTML = `<img class="observation-photo" src="${escapeHTML(url)}" alt="${escapeHTML(ui.photo?.label || 'Captured observation frame')}">`;
  } else $('#scene-art').innerHTML = pixelGuide(ui.view === 'TOP' ? 'TOP' : 'SIDE');
  $('#scene-view-label').textContent = photoView ? 'PHOTO VIEW' : (ui.view === 'TOP' ? 'TOP GUIDE' : 'SIDE GUIDE');
  $('.scene-demo').textContent = photoView ? (ui.photo ? (ui.photo.local ? 'YOUR PHOTO' : 'DEMO PHOTO') : 'CAPTURED FRAME') : 'PIXEL GUIDE';
  $('#scene-caption').textContent = photoView ? ui.photo?.label || 'Frame 0' : 'ROI GUIDE';
  $$('.segmented button').forEach(b => b.classList.toggle('selected', b.dataset.view === ui.view));
  renderPhotoStrip();
}
function setMetric(index, label, value, tag, note) {
  const card = $$('.metric-card')[index]; $('.metric-label', card).textContent = label;
  $('.metric-value', card).innerHTML = value; $('.metric-value', card).className = 'metric-value';
  $('.metric-tag', card).textContent = tag; $('.metric-bottom>span:last-child', card).textContent = note;
}
function renderWorlds(list) { $('#world-count').textContent = String(list.length).padStart(2, '0'); $('#world-list').innerHTML = list.length ? list.map((world, index) => { const data = worlds[world] || [world, world, '◇']; return `<div class="world-row"><span class="world-icon">${data[2]}</span><div class="world-info"><strong>${String(index + 1).padStart(2, '0')} &nbsp;${escapeHTML(data[0])}</strong><small>${escapeHTML(data[1])}</small></div><span class="world-status">${list.length > 1 ? 'OPEN' : 'CANDIDATE'}</span></div>`; }).join('') : '<div class="photo-empty"><span>◇</span><p>Start an observation to explore possible worlds.</p></div>'; }
function renderSession() {
  const s = ui.session;
  renderWorlds(s?.possible_worlds || []);
  $('#export-button').disabled = !s; $('#proof-button').disabled = !s;
  if (!s) {
    const p = ui.photo || photos[2];
    $('#mode-tag').textContent = 'DEMO LIBRARY'; $('#scene-session').textContent = p.index === undefined ? 'YOUR PHOTO' : `PHOTO ${String(p.index + 1).padStart(2, '0')}`;
    $('#view-status').textContent = p.index === undefined ? '● YOUR PHOTO' : `● PHOTO ${String(p.index + 1).padStart(2, '0')} / ${String(photos.length).padStart(2, '0')}`;
    $('#observation-state').textContent = p.label; $('#evidence-source').textContent = p.local ? 'YOUR PHOTO' : 'DEMO PHOTO COLLECTION';
    $('#snapshot-title').innerHTML = 'Frame details <span>AT A GLANCE</span>';
    setMetric(0, 'Image size', `${p.width}<span>× ${p.height} px</span>`, p.type, 'Original resolution');
    setMetric(1, 'Collection', `${String(photos.length).padStart(2, '0')}<span>photos</span>`, 'LIBRARY', 'Ready to explore');
    setMetric(2, 'Selected frame', p.index === undefined ? 'NEW' : `${String(p.index + 1).padStart(2, '0')}<span>/ ${String(photos.length).padStart(2, '0')}</span>`, p.local ? 'PHOTO' : 'DEMO', p.label);
    $('#disposition-tag').textContent = 'READY TO EXPLORE'; $('#next-title').textContent = 'Every stack has a story.';
    $('#next-description').textContent = 'Pick a photo, inspect the layers, and start your next observation.';
    $('#method-label').textContent = 'Current collection'; $('#next-method').textContent = `Cardboard / ${photos.length} photos`;
    $('#budget-label').textContent = 'Next step'; $('#remaining-views').textContent = 'Add a paired capture';
    $('#quest-action').textContent = 'Start an observation →'; $('#trace-proof').textContent = 'CERTIFICATE —';
    $('#trace-list').innerHTML = `<div class="trace-entry"><span class="trace-time">PHOTO</span><i></i><div>${escapeHTML(p.label)}<small>${p.width} × ${p.height} px · ${p.type}</small></div></div><div class="trace-entry"><span class="trace-time">READY</span><i></i><div>Your collection is ready.<small>Choose New observation to continue.</small></div></div>`;
    $('#observe-step').className = 'quest-step current'; $('#plan-step').className = 'quest-step';
    renderScene(); return;
  }
  const synthetic = s.mode === 'SYNTHETIC', observing = s.disposition === 'REQUEST_NONCONTACT_VIEW', direct = s.disposition === 'DIRECT_ACTION';
  $('#mode-tag').textContent = synthetic ? 'SYNTHETIC DEMO' : 'CAPTURED SESSION';
  $('#scene-session').textContent = s.session_id; $('#view-status').textContent = synthetic ? '● DEMO' : '● CAPTURED';
  $('#observation-state').textContent = synthetic ? 'Demo session' : 'Original frames archived';
  $('#snapshot-title').innerHTML = 'Observation clues <span>EVIDENCE SNAPSHOT</span>';
  const m = s.measurement || s.image_measurement_research_only;
  $('#evidence-source').textContent = synthetic ? 'SYNTHETIC INPUT' : 'CAPTURED INPUT';
  setMetric(0, 'Relative layer motion', `${m ? Number(m.max_footprint_drift_mm).toFixed(2) : '—'}<span>mm</span>`, m ? (synthetic ? 'SIMULATED' : 'MEASURED') : 'PENDING', m?.opencv_version ? `OpenCV ${m.opencv_version}` : 'Saved measurement');
  const ropeStep = [...s.steps].reverse().find(step => step.view === 'ROPE_PATH' && ['rope_still', 'rope_moved'].includes(step.signature));
  setMetric(1, 'Rope movement', ropeStep ? (ropeStep.signature === 'rope_still' ? 'STILL' : 'MOVED') : 'UNKNOWN', ropeStep ? 'REPORTED' : 'PENDING', ropeStep ? 'Manual observation' : 'Inspect the rope path');
  setMetric(2, 'Knot state', 'UNKNOWN', 'PENDING', 'Add a close-up view');
  $('#disposition-tag').textContent = observing ? 'NEXT OBSERVATION' : direct ? 'MODEL CANDIDATE' : 'PAUSED';
  $('#next-title').textContent = observing ? `Take a closer look at the ${(views[s.next_view] || s.next_view).toLowerCase()}.` : direct ? actions[s.modeled_recommendation] || s.modeled_recommendation : 'Pause for more evidence.';
  $('#next-description').textContent = observing ? 'Record what you can see from the selected viewpoint.' : direct ? 'The current model has narrowed down the next move.' : 'There is not enough evidence to select a next move.';
  $('#method-label').textContent = 'Observation'; $('#budget-label').textContent = 'Views remaining';
  $('#next-method').textContent = observing ? views[s.next_view] || s.next_view : 'Complete';
  $('#remaining-views').textContent = `${Math.max(0, s.view_budget - s.steps.length)} / ${s.view_budget}`;
  $('#quest-action').textContent = observing ? 'Record observation →' : 'View reasoning →';
  $('#observe-step').className = 'quest-step ' + (observing ? 'current' : 'done'); $('#plan-step').className = 'quest-step ' + (observing ? '' : 'current');
  $('#trace-proof').textContent = 'CERTIFICATE ' + s.witness.certificate_hash.slice(0, 12).toUpperCase();
  const entries = [{ time: 'START', title: synthetic ? 'Demo session started' : 'Original PNGs archived', note: synthetic ? 'SYNTHETIC INPUT' : 'SERVER_CAPTURED_PNG' }, ...s.steps.map(step => ({ time: `VIEW ${String(step.seq).padStart(2, '0')}`, title: `${views[step.view] || step.view}: ${signatures[step.signature] || step.signature}`, note: `${step.source || 'HUMAN_REPORTED'} · Worlds ${step.worlds_before.length} → ${step.worlds_after.length}` })), { time: 'PCIG', title: observing ? `Next: ${views[s.next_view] || s.next_view}` : direct ? actions[s.modeled_recommendation] || s.modeled_recommendation : 'Awaiting more evidence', note: s.disposition }];
  $('#trace-list').innerHTML = entries.map(e => `<div class="trace-entry"><span class="trace-time">${escapeHTML(e.time)}</span><i></i><div>${escapeHTML(e.title)}<small>${escapeHTML(e.note)}</small></div></div>`).join('');
  renderScene();
}
function selectPhoto(index) { ui.photo = photos[index]; ui.session = null; ui.selectedImage = null; ui.view = 'PHOTOS'; renderSession(); }
async function importPhoto(file) {
  if (!file) return;
  if (!file.type.startsWith('image/') || file.size > 25_000_000) throw new Error('Choose an image up to 25 MB.');
  const url = URL.createObjectURL(file), image = new Image();
  try { image.src = url; await image.decode(); } catch { URL.revokeObjectURL(url); throw new Error('This image format is not supported. Choose a JPEG or PNG.'); }
  if (ui.photo?.local) URL.revokeObjectURL(ui.photo.url);
  ui.photo = { label: 'Your photo', filename: file.name, url, width: image.naturalWidth, height: image.naturalHeight, type: file.type.split('/')[1].toUpperCase(), local: true };
  ui.urls.push(url); ui.session = null; ui.selectedImage = null; ui.view = 'PHOTOS';
  renderSession(); await navigate('overview'); closeModal(); toast('Photo added to your board.');
}
function photoModal() {
  showModal('ADD A PHOTO', '<h2 class="modal-title">Bring your stack into view.</h2><p class="modal-intro">Choose a photo or take a new one.</p><label class="photo-pick">▧<strong>Photo library</strong><span>JPEG, PNG, or a supported image</span><input type="file" id="library-photo" accept="image/*"></label><label class="photo-pick camera-pick">⌖<strong>Take a photo</strong><span>Use your phone camera</span><input type="file" id="camera-photo" accept="image/*" capture="environment"></label>');
  for (const id of ['library-photo', 'camera-photo']) $('#' + id).onchange = async e => { try { await importPhoto(e.target.files[0]); } catch (error) { showError(error); } };
}
async function refreshSessions() { ui.sessions = await api('sessions'); $('#history-count').textContent = String(ui.sessions.length).padStart(2, '0'); if (ui.page === 'history') renderHistory(); }
function displaySessionLabel(s) { return /[\u3000-\u9fff]/.test(s.label) ? (s.mode === 'SYNTHETIC' ? 'Cardboard bundle / Demo' : s.session_id) : s.label; }
function renderHistory() { $('#history-list').innerHTML = ui.sessions.length ? ui.sessions.map((s, i) => `<button class="history-row" data-session-index="${i}"><span class="world-icon">${s.error ? '!' : '▤'}</span><span><strong>${escapeHTML(displaySessionLabel(s))}</strong><small>${escapeHTML(s.session_id)} · ${dateText(s.created_at)}</small></span><span class="history-end">${s.error ? escapeHTML(s.error) : `${s.mode === 'SYNTHETIC' ? 'Demo' : 'Captured PNG'} · ${s.steps.length} ${s.steps.length === 1 ? 'view' : 'views'}`}<br>${s.error ? 'Unavailable' : escapeHTML(s.disposition)} ↗</span></button>`).join('') : '<div class="empty-state"><div class="empty-icon">▤</div>No saved sessions yet.<br>Start a new observation.</div>'; }
async function navigate(page) {
  if(ui.runtime?.role==='judge'&&page==='evidence')page='overview';
  ui.page = page;
  const labels = { overview: ['Observation console', 'A closer look. A clearer next move.'], history: ['Session history', 'Pick up where your last observation left off.'], evidence: ['Evidence archive', 'Your frames, receipts, and session records.'], guide: ['Field guide', 'From the first frame to the next move.'] };
  $('#page-title').innerHTML = `${labels[page][0]}<span class="heading-cursor">_</span>`; $('#page-description').textContent = labels[page][1]; $('#breadcrumb').textContent = page === 'overview' ? 'Console' : labels[page][0];
  $$('.page').forEach(p => p.hidden = p.id !== page + '-page'); $$('.nav-item').forEach(b => { b.classList.toggle('active', b.dataset.page === page); if (b.dataset.page === page) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current'); });
  try { if (page === 'history') await refreshSessions(); if (page === 'evidence') await renderAudit(); } catch (error) { toast(friendlyError(error)); }
  window.scrollTo({ top: 0, behavior: 'instant' });
}
async function renderAudit() { const audit = await api('audit'); const failures = audit.session_validation_failures.length + (audit.archive.missing_or_corrupt_receipts || []).length; const orphans = (audit.archive.orphan_candidates_REVIEW_BEFORE_DELETE || []).length; $('#audit-summary').innerHTML = `<div>Sessions<strong>${audit.session_count}</strong></div><div>Integrity issues<strong>${failures}</strong></div><div>Unlinked files<strong>${orphans}</strong></div>`; $('#audit-content').innerHTML = `<p>Archive status: <strong>${escapeHTML(audit.status)}</strong></p><details><summary>View audit record</summary><pre>${escapeHTML(JSON.stringify(audit, null, 2))}</pre></details>`; }
async function startDemo(button) { await busy(button, async () => { ui.session = await api('demo', { label: 'Cardboard bundle / Demo' }); ui.photo = null; ui.selectedImage = null; ui.view = 'SIDE'; await refreshSessions(); renderSession(); await navigate('overview'); closeModal(); toast('Demo started. Record your next observation.'); }); }
function newSessionModal() { showModal('START A NEW QUEST', '<h2 class="modal-title">Make your next observation.</h2><button class="choice-card" id="open-photo"><span>▧</span><span><strong>Explore a photo</strong><small>Camera or photo library</small></span><span>→</span></button><button class="choice-card" id="open-upload"><span>⊞</span><span><strong>Analyze paired frames</strong><small>Two PNG frames, two ROI masks, and a configuration</small></span><span>→</span></button><button class="choice-card" id="start-demo"><span>▣</span><span><strong>Launch the demo</strong><small>Explore the observation loop with synthetic inputs</small></span><span>→</span></button>'); $('#open-photo').onclick = photoModal; if(ui.runtime?.role==='judge')$('#open-upload').hidden=true; else $('#open-upload').onclick = () => uploadModal(false); $('#start-demo').onclick = e => startDemo(e.currentTarget); }
function observationModal() {
  const s = ui.session; if (!s || s.disposition !== 'REQUEST_NONCONTACT_VIEW') return proofModal();
  showModal('RECORD AN OBSERVATION', `<h2 class="modal-title">${escapeHTML(views[s.next_view] || s.next_view)}</h2><p class="modal-intro">View ${s.steps.length + 1} of ${s.view_budget} · ${escapeHTML(s.session_id)}</p><form id="observe-form"><div class="observation-options">${s.observation_options.map((sig, i) => `<label><input type="radio" name="signature" value="${escapeHTML(sig)}" required ${i === 0 ? 'checked' : ''}>${escapeHTML(signatures[sig] || sig)}</label>`).join('')}</div>${s.mode !== 'SYNTHETIC' ? '<label class="field">New observation PNG<input type="file" id="observation-file" accept="image/png" required></label>' : ''}<div class="modal-actions">${s.mode !== 'SYNTHETIC' ? '<button class="button secondary" id="image-followup" type="button">Analyze a new capture</button>' : ''}<button class="button primary" type="submit">Save observation →</button></div></form>`);
  $('#image-followup')?.addEventListener('click', () => uploadModal(true));
  $('#observe-form').onsubmit = e => { e.preventDefault(); busy($('button[type=submit]', e.currentTarget), async () => { let bytes; if (s.mode === 'SYNTHETIC') bytes = new TextEncoder().encode(`SYNTHETIC-MANUAL-EVENT:${s.session_id}:${idSuffix()}`); else { const file = $('#observation-file').files[0]; if (!file || file.size > 2500000) throw new Error('Choose a PNG up to 2.5 MB.'); bytes = new Uint8Array(await file.arrayBuffer()); if (!isPNG(bytes)) throw new Error('Choose a PNG image.'); } const result = await api(`sessions/${encodeURIComponent(s.session_id)}/observe`, { expected_version: s.version, view: s.next_view, signature: $('input[name=signature]:checked').value, capture_sha256: await sha256(bytes) }); ui.session = result; await refreshSessions(); renderSession(); closeModal(); toast('Observation saved.'); }); };
}
function proofModal() { const s = ui.session; if (!s) return newSessionModal(); const w = s.witness; showModal('PCIG / DECISION WITNESS', `<h2 class="modal-title">The reasoning behind the move.</h2><div class="proof-stats"><div>Prior regret<strong>${w.regret_no_observation.toFixed(2)}</strong></div><div>Risk + observation cost<strong>${w.risk_after_observation === null ? '—' : w.risk_after_observation.toFixed(2)}</strong></div></div><p class="tiny">Certificate SHA256</p><pre class="code-block">${escapeHTML(w.certificate_hash)}</pre><details><summary>Worlds, losses, and observation costs</summary><pre class="code-block">${escapeHTML(JSON.stringify(JSON.parse(w.certificate_payload), null, 2))}</pre></details><div class="modal-actions"><button class="button secondary" id="proof-export">Export evidence JSON ↓</button></div>`); $('#proof-export').onclick = exportCurrent; }
async function exportCurrent() { if (!ui.session) return; try { downloadJSON(await api(`sessions/${encodeURIComponent(ui.session.session_id)}/export`), ui.session.session_id + '-trace.json'); toast('Evidence JSON downloaded.'); } catch (error) { toast(friendlyError(error)); } }
function runtimeModal() { const r = ui.runtime; showModal('SYSTEM / RUNTIME', `<h2 class="modal-title">Your field lab.</h2>${[['Version', 'BIND ZERO-X ' + (r?.version || '—')], ['OpenCV', r?.opencv_version || '—'], ['Capture analysis', r?.opencv5 ? 'READY' : 'UNAVAILABLE'], ['Storage', 'SQLite + PNG archive'], ['Access',r?.role==='judge'?'Judge password':'Password + authenticator'], ['Session',r?.role==='judge'?'1 hour / 15 min idle':'8 hours / 15 min idle'], ['AWS execution', r?.aws_execution_record ? 'Tokyo CloudShell / Synthetic' : 'No execution record']].map(row => `<div class="runtime-row"><span>${row[0]}</span><strong>${escapeHTML(row[1])}</strong></div>`).join('')}`); }
function phoneModal() { showModal('CONNECT YOUR PHONE', `<h2 class="modal-title">Take the lab with you.</h2>${ui.runtime?.mobile_url ? '<p class="modal-intro">Connect to the same Wi-Fi, trust your local CA certificate on your phone, then open this HTTPS address and sign in with MFA.</p><label class="field">Phone link<input id="phone-link" readonly value="' + escapeHTML(ui.runtime.mobile_url) + '"></label><button class="button primary" id="copy-phone-link">Copy link ↗</button>' : '<p class="modal-intro">On this PC, start mobile mode:</p><pre class="code-block">.\\Start.ps1 -Mobile</pre><p class="modal-intro">Then open Connect phone to get your Wi-Fi link.</p>'}`); $('#phone-link')?.addEventListener('focus', e => e.target.select()); $('#copy-phone-link')?.addEventListener('click', async () => { try { await navigator.clipboard.writeText(ui.runtime.mobile_url); toast('Phone link copied.'); } catch { $('#phone-link').select(); } }); }
function configTemplate() { downloadJSON({ session_id: 'RESEARCH-CHANGE-ME', observation_id: 'OBS-CHANGE-ME', calibration: { scale_mm_per_px: 0.8, plane_id: 'REPLACE_WITH_REAL_PLANE', calibration_id: 'REPLACE_WITH_CALIBRATION_ID', verified: false, frozen: true, sigma_scale_mm_per_px: 0 }, roi_manifest: { operator_verified: false, frame0_sha256: 'REPLACE_WITH_SHA256_OF_DECODED_GRAYSCALE_PIXELS', layers: { upper: { layer_label: 'upper', source_id: 'UPPER-LAYER', mask_sha256: 'REPLACE_WITH_SHA256_OF_DECODED_MASK_PIXELS' }, lower: { layer_label: 'lower', source_id: 'LOWER-LAYER', mask_sha256: 'REPLACE_WITH_SHA256_OF_DECODED_MASK_PIXELS' } } }, worlds: ['LAYER_ONLY', 'LAYER_AND_ROPE'], losses: { REORDER: { LAYER_ONLY: 0, LAYER_AND_ROPE: 6 }, REPOSITION_TWINE: { LAYER_ONLY: 5, LAYER_AND_ROPE: 2 }, ABSTAIN: { LAYER_ONLY: 2, LAYER_AND_ROPE: 2 } }, view_signatures: { ROPE_PATH: { LAYER_ONLY: 'rope_still', LAYER_AND_ROPE: 'rope_moved' } }, view_costs: { ROPE_PATH: .25 } }, 'bind-zero-config-DRAFT.json'); }
function uploadModal(followup = false) {
  showModal('CAPTURE / PAIRED FRAMES', `<h2 class="modal-title">${followup ? 'Add the next capture.' : 'Follow the motion.'}</h2><p class="modal-intro">Two frames, two layer masks. PNG · up to 2.5 MB and 3 million pixels per image.</p><form id="upload-form"><div class="form-grid">${[['frame0', 'First frame · t0'], ['frame1', 'Next frame · t1'], ['upper_mask', 'Upper layer mask'], ['lower_mask', 'Lower layer mask']].map(([name, label]) => `<label class="field">${label}<input type="file" name="${name}" accept="image/png" required></label>`).join('')}</div><label class="field">Calibration, ROI, and model configuration<input type="file" name="config" accept=".json,application/json" required></label><button type="button" class="text-button" id="config-template">Download configuration template ↓</button><div class="modal-actions"><button type="submit" class="button primary">${followup ? 'Analyze next capture' : 'Archive & analyze'} →</button></div></form>`);
  $('#config-template').onclick = configTemplate;
  $('#upload-form').onsubmit = e => { e.preventDefault(); const form = e.currentTarget; busy($('button[type=submit]', form), async () => { if (!ui.runtime?.opencv5) throw new Error('OPENCV5_RUNTIME_REQUIRED'); const configFile = form.elements.config.files[0]; if (!configFile || configFile.size > 200000) throw new Error('Choose a configuration JSON up to 200 KB.'); let config; try { config = JSON.parse(await configFile.text()); } catch { throw new Error('The configuration is not valid JSON.'); } const images = {}; for (const name of ['frame0', 'frame1', 'upper_mask', 'lower_mask']) images[name + '_png_b64'] = await fileBase64(form.elements[name].files[0]); let payload = { ...config, ...images }; if (followup) { const s = ui.session; payload = { ...images, calibration: config.calibration, roi_manifest: config.roi_manifest, observation_id: s.observation_id, session_id: s.session_id, expected_version: s.version, view: s.next_view }; } const result = await api(followup ? 'reobserve-image' : 'capture', payload); if (ui.selectedImage) URL.revokeObjectURL(ui.selectedImage); ui.selectedImage = URL.createObjectURL(form.elements.frame0.files[0]); ui.urls.push(ui.selectedImage); ui.photo = null; ui.view = 'PHOTOS'; ui.session = result; renderSession(); await refreshSessions(); await navigate('overview'); closeModal(); toast('Frames archived. Analysis saved.'); }); };
}
function toggleExpanded(expanded) { $('#scene').classList.toggle('view-expanded', expanded); $('#expand-view').setAttribute('aria-expanded', String(expanded)); if (expanded) $('#collapse-view').focus(); else $('#expand-view').focus(); }
$$('.nav-item').forEach(button => button.onclick = () => navigate(button.dataset.page));
$$('.segmented button').forEach(button => button.onclick = () => { ui.view = button.dataset.view; if (ui.view === 'PHOTOS' && ui.session?.mode === 'SYNTHETIC') selectPhoto(1); else renderScene(); });
$('#photo-strip').onclick = e => { const button = e.target.closest('[data-photo-index]'); if (button) selectPhoto(Number(button.dataset.photoIndex)); };
$('#new-session').onclick = newSessionModal;
$('#capture-button').onclick = photoModal;
$('#quest-action').onclick = () => ui.session ? (ui.session.disposition === 'REQUEST_NONCONTACT_VIEW' ? observationModal() : proofModal()) : newSessionModal();
$('#proof-button').onclick = proofModal; $('#export-button').onclick = exportCurrent;
$('#settings-button').onclick = runtimeModal; $('#mode-info').onclick = runtimeModal; $('#phone-button').onclick = phoneModal;
$('#help-button').onclick = () => navigate('guide'); $('#guide-demo').onclick = e => startDemo(e.currentTarget);
$('#guide-photo').onclick = () => { selectPhoto(1); navigate('overview'); };
$('#guide-history').onclick = () => navigate('history'); $('#download-config').onclick = configTemplate;
$('#close-modal').onclick = closeModal; $('#modal').addEventListener('close', stopCamera);
$('#modal').addEventListener('click', e => { if (e.target === $('#modal')) { const rect = $('#modal').getBoundingClientRect(); if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) closeModal(); } });
$('#refresh-history').onclick = e => busy(e.currentTarget, refreshSessions); $('#refresh-audit').onclick = e => busy(e.currentTarget, renderAudit);
$('#history-list').onclick = async e => { const button = e.target.closest('[data-session-index]'); if (!button) return; const session = ui.sessions[Number(button.dataset.sessionIndex)]; try { ui.session = await api('sessions/' + encodeURIComponent(session.session_id)); ui.photo = null; ui.selectedImage = null; ui.view = ui.session.mode === 'SYNTHETIC' ? 'SIDE' : 'PHOTOS'; renderSession(); await navigate('overview'); toast('Session opened.'); } catch (error) { toast(friendlyError(error)); } };
$('#expand-view').onclick = () => toggleExpanded(!$('#scene').classList.contains('view-expanded')); $('#collapse-view').onclick = () => toggleExpanded(false);
document.addEventListener('keydown', e => { if (e.key === 'Escape' && $('#scene').classList.contains('view-expanded')) toggleExpanded(false); if (e.key.toLowerCase() === 'n' && !e.ctrlKey && !e.metaKey && !e.altKey && !$('#modal').open && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) newSessionModal(); });
window.addEventListener('beforeunload', () => { stopCamera(); ui.urls.forEach(url => URL.revokeObjectURL(url)); });
async function init() { renderSession(); try { const access = await (await fetch('/auth/session')).json(); if (!access.authenticated) return location.replace('/'); ui.csrf = access.csrf; ui.runtime = await api('runtime'); if(ui.runtime.role==='judge'){$('[data-page="evidence"]').hidden=true;$('.workspace small').textContent='JUDGE / '+ui.runtime.username;} document.dispatchEvent(new Event('console-ready')); await refreshSessions(); if (!ui.runtime.mobile_url) $('#phone-button').textContent = 'Phone setup ↗'; } catch (error) { toast(friendlyError(error)); } }
init();

function pixelGuide(view) {
  // Code-native pixel art: stacked cardboard, paper twine, and separate ROI guides.
  if (view === 'TOP') return `<svg viewBox="0 0 500 280" role="img" aria-label="Pixel illustration of a cardboard bundle from above" shape-rendering="crispEdges"><path fill="#1c2d30" d="M85 63h330v169H85z"/><path fill="#94764f" d="M80 47h324v170H80z"/><path fill="#c89d66" d="M86 42h312v166H86z"/><path fill="#deb783" d="M94 48h296v149H94z"/><path fill="#e7c694" d="M101 55h282v10H101z"/><path fill="#bb925e" d="M117 87h40v4h-40zM300 166h64v4h-64zM155 174h65v4h-65z"/><path fill="#556d5a" d="M232 42h13v166h-13zM86 115h312v13H86z"/><path fill="#b7c6a3" d="M235 42h5v166h-5zM86 118h312v5H86z"/><path d="M219 108h31v29h-31z" fill="#718466"/><path d="M211 101h17v10h-17zM250 130h17v10h-17z" fill="#c5d0af"/><path d="M68 32h343v191H68z" fill="none" stroke="#91c8a8" stroke-width="2" stroke-dasharray="7 6"/><path d="M60 41V25h18M403 25h17v17M60 214v18h18M403 232h17v-18" stroke="#a5d9b5" stroke-width="3" fill="none"/></svg>`;
  let layers = '';
  const colors = ['#a68150', '#d2aa73', '#b99562', '#e0bb87', '#b38b59', '#d7b17b'];
  for (let i = 0; i < 6; i++) {
    const x = 92 + [8, -5, 4, -9, 1, 11][i], y = 200 - i * 18;
    layers += `<path d="M${x} ${y}l199 22 103-53-199-22z" fill="${colors[i]}"/><path d="M${x} ${y}l199 22v12l-199-22z" fill="${i % 2 ? '#d2b07d' : '#b18e5b'}"/><path d="M${x + 199} ${y + 22}l103-53v12l-103 53z" fill="#94784e"/><path d="M${x + 5} ${y + 7}l190 21" stroke="#6f6548" stroke-width="2" stroke-dasharray="3 4"/>`;
  }
  return `<svg viewBox="0 0 500 280" role="img" aria-label="Pixel illustration of six tied cardboard layers" shape-rendering="crispEdges"><path d="M78 233l214 24 130-67-211-21z" fill="#172d30" opacity=".7"/><path d="M62 245h365" stroke="#4a6459" stroke-width="1"/><path d="M83 242v7M125 242v7M167 242v7M209 242v7M251 242v7M293 242v7M335 242v7M377 242v7M419 242v7" stroke="#557267"/>${layers}<path d="M103 104l199 22 103-53-199-22z" fill="#cda66f"/><path d="M110 103l191 20 94-48-189-20z" fill="#dcbc89"/><path d="M130 103l169 17 71-35" stroke="#e6c99c" stroke-width="3" fill="none"/><path d="M123 101l167 18 99-48" stroke="#8d7955" stroke-width="2" opacity=".5" fill="none"/><path d="M178 66l11-6 105 59v110l-10 5V126z" fill="#55735e"/><path d="M182 64l5-2 103 60v109l-5 2V125z" fill="#b7c6a3"/><path d="M120 114l108-55 13 2-109 60v105l-12-2z" fill="#536e57"/><path d="M124 115l109-55 5 1-109 58v107l-5-1z" fill="#a7b698"/><path d="M218 85h20v9h-20zM213 90h9v8h-9zM236 80h14v9h-14zM221 87h18v12h-18z" fill="#75846a"/><path d="M216 87h13v4h-13zM232 83h14v4h-14z" fill="#ced3af"/><path d="M88 91l213 24 105-55" fill="none" stroke="#9dd7b4" stroke-width="2" stroke-dasharray="5 5"/><path d="M88 91v47l213 24v-47M301 162l105-55V60" fill="none" stroke="#9dd7b4" stroke-width="2" stroke-dasharray="5 5"/><path d="M82 185l214 24 108-55v47l-108 56-214-24z" fill="none" stroke="#dfbd7b" stroke-width="2" stroke-dasharray="5 5"/><path d="M78 104V85h20M392 50h20v18M72 218v21h19M394 210h20v-18" fill="none" stroke="#b6cfb1" stroke-width="3"/><path d="M317 153h35v-16h29M96 211H62v-15H44" stroke="#9fbe9e" fill="none" stroke-width="1"/><path d="M349 135h5v5h-5zM60 194h5v5h-5z" fill="#bbd2ad"/><path d="M430 102h12v3h-12zM435 97h3v13h-3zM54 158h8v2h-8zM57 155h2v8h-2z" fill="#5c8370"/></svg>`;
}
async function authAction(path) { const response = await fetch(path, {method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':ui.csrf},body:'{}'}); if(!response.ok) throw new Error('Unable to update session.'); }
$('#logout-button').onclick = async () => { try { await authAction('/auth/logout'); location.replace('/'); } catch(error) { toast(error.message); } };
$('#revoke-button').onclick = async () => { try { await authAction('/auth/revoke-others'); toast('Other device sessions signed out.'); } catch(error) { toast(error.message); } };

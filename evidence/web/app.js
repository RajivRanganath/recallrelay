'use strict';
const $ = (id) => document.getElementById(id);
let image = null;
let previewUrl = null;
let uploadGeneration = 0;
let busy = false;
const labels = {eligible: 'Identifiers match', excluded: 'Outside this campaign', needs_information: 'A detail needs attention'};

async function request(path, body) {
  const response = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? {} : {'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(8000)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The request could not be completed.');
  return data;
}
function invalidate() {
  $('confirmed').checked = false;
  $('result').hidden = true;
  $('message').textContent = '';
}
function releasePhoto(clearInput = true) {
  uploadGeneration += 1;
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = null;
  image = null;
  $('photo').removeAttribute('src');
  $('photo-preview').hidden = true;
  $('remove-photo').hidden = true;
  $('suggest-image').hidden = true;
  $('fixture-help').hidden = true;
  if (clearInput) $('upload').value = '';
}
function lock(value) {
  busy = value;
  for (const id of ['assess', 'load-sample', 'upload', 'remove-photo', 'model', 'batch', 'confirmed', 'sample', 'suggest-image']) $(id).disabled = value;
}
$('model').addEventListener('input', invalidate);
$('batch').addEventListener('input', invalidate);
$('sample').addEventListener('change', () => {
  invalidate();
  $('message').textContent = 'Select “Use sample” to load this example.';
});
$('load-sample').addEventListener('click', async () => {
  if (busy) return;
  invalidate();
  releasePhoto();
  lock(true);
  $('model').value = '';
  $('batch').value = '';
  $('sample-preview').hidden = true;
  $('message').textContent = 'Loading synthetic proposal…';
  try {
    const data = await request('/demo/extraction', {sample_id: $('sample').value});
    $('model').value = data.model || '';
    $('batch').value = data.batch || '';
    $('sample-model').textContent = `MODEL ${data.model || 'UNREADABLE'}`;
    $('sample-batch').textContent = `BATCH ${data.batch || '????'}`;
    $('sample-preview').hidden = false;
    $('proposal-note').textContent = `Mock assistant · ${data.notice}`;
    $('message').textContent = data.clarification || 'Sample loaded. Check and confirm the suggested values.';
  } catch (error) { $('message').textContent = error.message; }
  finally { lock(false); }
});
$('upload').addEventListener('change', async () => {
  const file = $('upload').files[0];
  releasePhoto(false);
  invalidate();
  $('model').value = '';
  $('batch').value = '';
  $('sample-preview').hidden = true;
  $('proposal-note').textContent = 'Typed entry · No extraction is running.';
  if (!file) return;
  if (!['image/png', 'image/jpeg'].includes(file.type) || file.size === 0 || file.size > 2 * 1024 * 1024) {
    $('upload').value = '';
    $('message').textContent = 'Choose a PNG or JPEG between 1 byte and 2 MiB.';
    return;
  }
  const generation = uploadGeneration;
  lock(true);
  $('message').textContent = 'Preparing local preview…';
  try {
    const encoded = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(',')[1]);
      reader.onerror = () => reject(new Error('The photo could not be read.'));
      reader.readAsDataURL(file);
    });
    if (generation !== uploadGeneration) return;
    previewUrl = URL.createObjectURL(file);
    $('photo').src = previewUrl;
    $('photo-preview').hidden = false;
    $('remove-photo').hidden = false;
    $('suggest-image').hidden = false;
    $('fixture-help').hidden = false;
    image = {image_base64: encoded, mime_type: file.type};
    $('proposal-note').textContent = 'Photo selected · No extraction is running. Enter and confirm the identifiers yourself.';
    $('message').textContent = 'Read the label and enter the identifiers. Leave unclear values blank.';
  } catch (error) { $('message').textContent = error.message; }
  finally { lock(false); }
});
$('suggest-image').addEventListener('click', async () => {
  if (busy || !image) return;
  invalidate();
  $('model').value = '';
  $('batch').value = '';
  lock(true);
  $('message').textContent = 'Looking up the known synthetic fixture…';
  try {
    const data = await request('/demo/image-extraction', image);
    $('model').value = data.model || '';
    $('batch').value = data.batch || '';
    $('proposal-note').textContent = `Mock fixture adapter · ${data.notice} Confidence values are authored test inputs, not measured probabilities.`;
    $('message').textContent = data.clarification || 'Mock suggestions loaded. Check both fields and confirm before assessment.';
  } catch (error) {
    $('proposal-note').textContent = 'No extraction result · Typed entry remains available.';
    $('message').textContent = error.message;
  } finally { lock(false); }
});
$('remove-photo').addEventListener('click', () => {
  releasePhoto(); invalidate();
  $('proposal-note').textContent = 'Typed entry · No AI provider is connected.';
});
$('assessment-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (busy || !$('confirmed').checked) return;
  lock(true);
  $('result').hidden = true;
  $('message').textContent = 'Checking confirmed identifiers…';
  try {
    const data = await request('/demo/assessments', {label: {
      image_base64: image?.image_base64 || null, mime_type: image?.mime_type || null,
      confirmed_model: $('model').value, confirmed_batch: $('batch').value
    }});
    $('result-mode').textContent = 'Manual · confirmed text + deterministic rules';
    $('decision').textContent = labels[data.decision];
    $('reason').textContent = data.reason;
    $('clarification').hidden = !data.clarification;
    $('clarification').textContent = data.clarification || '';
    $('assessment-id').textContent = `Saved locally · ${data.assessment_id}`;
    $('result').hidden = false;
    $('message').textContent = '';
    $('result').focus();
  } catch (error) { $('message').textContent = error.message; }
  finally { lock(false); }
});
$('refresh-status').addEventListener('click', async () => {
  $('refresh-status').disabled = true;
  $('resolution').textContent = 'Reading resolution service…';
  try {
    const data = await request('/demo/resolution-status');
    const mode = data.mode === 'mock' ? 'MOCK · canned status, no money moved' : 'PAYPAL SANDBOX · test environment';
    $('resolution').textContent = `${mode}\n${data.status.replaceAll('_', ' ')}\n${data.brief}\nSeparate merchant record; not proof of a handoff from this assessment.`;
  } catch (error) { $('resolution').textContent = `Status unavailable. ${error.message}`; }
  finally { $('refresh-status').disabled = false; }
});

'use strict';
const $ = (id) => document.getElementById(id);
const statusLabels = {
  needs_information: 'More information needed', excluded: 'Outside this campaign',
  manual_required: 'Remedy confirmation needed', awaiting_approval: 'Awaiting merchant approval',
  pending: 'Refund pending', refunded: 'Refunded', failed: 'Refund failed'
};
const decisionLabels = {eligible: 'Identifiers match', excluded: 'Outside this campaign', needs_information: 'A detail needs attention'};
const state = {busy: false, saved: null, detail: null, customer: null, sent: null, image: null, preview: null, view: 'label', readError: false, wasPending: false};
// Reported by the two services and the launcher at startup; labels never claim a mode that is not running.
const modes = {ai: false, aiBrief: false, sandbox: false, loseFirst: false};
const money = (amount, currency = 'USD') => `${(amount / 100).toFixed(2)} ${currency}`;

async function request(role, path, body) {
  const response = await fetch(path === undefined ? `/api/${role}` : `/api/${role}${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? {} : {'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(50000)
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || 'The request could not be confirmed. Refresh case status before retrying.');
    error.status = response.status;
    throw error;
  }
  return data;
}

function message(id, text = '', error = false) {
  $(id).textContent = text;
  $(id).classList.toggle('error', error);
}
function facts(id, rows) {
  $(id).replaceChildren(...rows.flatMap(([name, value]) => {
    const term = document.createElement('dt');
    const description = document.createElement('dd');
    term.textContent = name;
    description.textContent = String(value ?? 'Not available');
    return [term, description];
  }));
}
function actions() {
  $('send-review').disabled = state.busy || !state.saved || state.sent === state.saved.assessment_id;
  $('suggest').disabled = state.busy || !state.image;
  for (const id of ['confirm-remedy', 'approve', 'reconcile', 'write-brief']) $(id).disabled = state.busy || state.readError;
}
function busy(value) {
  state.busy = value;
  for (const element of document.querySelectorAll('button, input, select')) element.disabled = value;
  $('main').setAttribute('aria-busy', String(value));
  actions();
}
async function run(id, work) {
  if (state.busy) return;
  busy(true);
  message(id);
  try { await work(); }
  catch (error) { message(id, error.message, true); }
  finally { busy(false); }
}

function applyModes() {
  const payments = modes.sandbox ? 'PayPal sandbox refunds' : 'fake payments';
  $('mode-chip').textContent = `${modes.ai ? 'Live AI label reading' : 'Mock label reading'} · ${modes.aiBrief ? 'AI brief' : 'template brief'} · ${payments}`;
  $('footer-modes').textContent = `Fictional products and cases only. ${modes.ai ? 'AI label suggestions' : 'Mock extraction'} · ${modes.aiBrief ? 'validated AI briefs' : 'template briefs'} · ${modes.sandbox ? 'PayPal sandbox, simulated funds, no live money' : 'fake payments'}.`;
  $('suggest').textContent = modes.ai ? 'Read label with AI' : 'Suggest fixture text';
  $('upload-help').textContent = modes.ai
    ? 'PNG or JPEG, up to 2 MiB. The photo goes to the configured model for a suggestion and is not saved. You confirm every identifier.'
    : 'PNG or JPEG, up to 2 MiB. Photos are not saved. Fixture suggestions recognize only known repository images; other photos use typed entry.';
  $('write-brief').textContent = modes.aiBrief ? 'Draft AI brief' : 'Generate template brief';
  $('approval-title').textContent = $('approve').textContent = modes.sandbox ? 'Approve sandbox refund' : 'Approve fake refund';
  $('approval-mode').textContent = modes.sandbox
    ? 'Before sending, PayPal is asked for the payment state, refunded balance and open disputes. The refund is then read back from PayPal before this case says refunded.'
    : 'Fake adapter: no request leaves this computer.';
  if (modes.sandbox) $('session-order').textContent = 'One PayPal sandbox order. Simulated funds · one unit.';
}
function renderAssessment() {
  const saved = state.saved;
  $('assessment-result').hidden = !saved;
  if (!saved) return actions();
  $('decision').textContent = decisionLabels[saved.decision] || saved.decision;
  $('reason').textContent = saved.reason;
  $('clarification').textContent = saved.clarification || '';
  $('saved-id').textContent = `Saved assessment · ${saved.assessment_id}`;
  actions();
}
function renderCase() {
  const detail = state.detail;
  $('review-empty').hidden = Boolean(detail);
  $('review-content').hidden = !detail;
  $('status-empty').hidden = Boolean(detail);
  $('status-content').hidden = !detail;
  $('case-stage').textContent = detail ? `${statusLabels[detail.resolution.status] || detail.resolution.status} · case-demo-1` : 'Ready for label check · case-demo-1';
  if (!detail) return;
  const {resolution, assessment, order, binding} = detail;
  const title = statusLabels[resolution.status] || resolution.status;
  // A case that has not reached the payment adapter still reports 'mock'; the session's adapter decides the wording.
  const fake = resolution.mode === 'mock' && !modes.sandbox;
  $('review-status').textContent = `${title}. ${fake ? 'Fake payments: no money moves.' : 'PayPal sandbox: no live money.'}`;
  facts('evidence-facts', [['Decision', decisionLabels[assessment.decision] || assessment.decision],
    ['Model', assessment.model || 'Not confirmed'], ['Batch', assessment.batch || 'Not confirmed'],
    ['Reason', assessment.reason], ['Assessment', assessment.assessment_id],
    ['Sources', assessment.evidence.map((e) => `${e.source_id}: ${e.field} = ${e.value}`).join('; ') || 'None cited']]);
  facts('order-facts', [['Order', order.order_id], ['Paid', money(order.paid_minor, binding.currency)],
    ['Already refunded', money(order.previously_refunded_minor, binding.currency)], ['Purchase age', `${order.age_days} days`], ['Units', order.quantity]]);
  const locked = ['pending', 'refunded', 'failed'].includes(resolution.status);
  $('remedy-text').textContent = detail.remedy_conditions_met
    ? 'The merchant confirmed the campaign’s remedy conditions are met.'
    : 'Not confirmed. Check the campaign’s remedy conditions yourself before confirming.';
  $('confirm-remedy').hidden = detail.remedy_conditions_met || locked || assessment.decision !== 'eligible';
  $('approval').hidden = resolution.status !== 'awaiting_approval';
  $('refund-amount').textContent = money(binding.amount_minor, binding.currency);
  $('typed-amount').placeholder = (binding.amount_minor / 100).toFixed(2);
  $('review-outcome').hidden = !locked && !['excluded', 'needs_information'].includes(resolution.status);
  $('review-outcome-title').textContent = title;
  $('review-outcome-text').textContent = resolution.brief;
  $('outcome-mode').textContent = fake ? 'Mock · fake payments, no money moved' : 'PayPal sandbox · simulated funds';
  $('outcome-title').textContent = title;
  $('outcome-text').textContent = resolution.brief;
  facts('status-facts', [['Case', resolution.case_id], ['Assessment', assessment.assessment_id],
    ['Refund amount', money(resolution.proposed_amount_minor, binding.currency)],
    ['Operation', resolution.operation_id || 'Not created'], ['Refund', resolution.refund_id || 'Not created']]);
  const same = state.customer && state.customer.case_id === resolution.case_id
    && state.customer.operation_id === resolution.operation_id && state.customer.status === resolution.status
    && state.customer.refund_id === resolution.refund_id;
  $('customer-status').textContent = same
    ? `Customer status: ${statusLabels[state.customer.status] || state.customer.status}. Same case, operation and refund as merchant review.`
    : 'Customer status could not yet be matched. Refresh case to read both views again.';
  $('snapshot-note').textContent = state.saved && state.saved.assessment_id !== assessment.assessment_id
    ? 'The label check has a newer saved assessment. This merchant outcome belongs to the submitted assessment shown above.'
    : 'This outcome belongs to the submitted assessment shown above. Editing a label does not change an existing merchant decision.';
  $('reconcile').hidden = resolution.status !== 'pending';
  state.wasPending = state.wasPending || resolution.status === 'pending';
  const recovery = resolution.status === 'pending'
    ? `${modes.loseFirst ? 'Fault injection for this demo: the refund request was accepted, then its acknowledgement was deliberately discarded. ' : ''}The outcome is unknown, so nothing is retried automatically and no second refund is created. “Check pending refund again” re-sends the same operation ID, which the payment provider treats as the same request.`
    : resolution.status === 'refunded' && state.wasPending
      ? 'Recovered from an unknown outcome: the same operation ID was sent again, the provider returned the one existing refund, and its read-back matched the approved amount. No duplicate refund was created.'
      : '';
  $('recovery-note').textContent = recovery;
  $('recovery-note').hidden = !recovery;
  actions();
}

async function refreshCase() {
  try {
    const detail = await request('merchant', '/v1/cases/case-demo-1');
    if (state.detail?.assessment.assessment_id !== detail.assessment.assessment_id
        || state.detail?.resolution.status !== detail.resolution.status
        || state.detail?.remedy_conditions_met !== detail.remedy_conditions_met) $('brief-result').hidden = true;
    state.detail = detail;
    state.sent = detail.assessment.assessment_id;
    state.readError = false;
    state.customer = null;
    message('status-message');
    try { state.customer = await request('customer', '/demo/resolution-status'); }
    catch (error) { message('status-message', `Merchant record loaded. Customer status unavailable: ${error.message}`, true); }
  } catch (error) {
    if (error.status !== 404) {
      state.readError = true;
      actions();
      throw error;
    }
    state.detail = null;
    state.customer = null;
    state.sent = null;
    state.readError = false;
  }
  renderCase();
}
function view(focus = false) {
  const target = location.hash.slice(1);
  state.view = ['label', 'review', 'status'].includes(target) ? target : 'label';
  for (const name of ['label', 'review', 'status']) {
    $(`view-${name}`).hidden = name !== state.view;
    if (name === state.view) $(`nav-${name}`).setAttribute('aria-current', 'step');
    else $(`nav-${name}`).removeAttribute('aria-current');
  }
  if (focus) $(`${state.view === 'label' ? 'label' : state.view === 'review' ? 'review' : 'status'}-title`).focus();
}
window.addEventListener('hashchange', () => {
  view(true);
  if (state.view !== 'label') run('app-message', refreshCase);
});
$('refresh').addEventListener('click', () => run('app-message', refreshCase));
// Hosted demo only: every visitor shares one fictional case, so anyone may start a fresh session.
$('reset-demo').addEventListener('click', () => run('app-message', async () => {
  const response = await fetch('/api/session/reset', {method: 'POST', signal: AbortSignal.timeout(50000)});
  if (!response.ok) throw new Error('The demo could not be reset. Try again.');
  message('app-message', 'Starting a fresh demo session…');
  setTimeout(() => { location.hash = 'label'; location.reload(); }, 3000);
}));

function invalidate() {
  state.saved = null;
  $('confirmed').checked = false;
  message('label-message');
  renderAssessment();
}
function clearPhoto() {
  if (state.preview) URL.revokeObjectURL(state.preview);
  state.preview = null;
  state.image = null;
  $('photo').removeAttribute('src');
  $('photo-preview').hidden = true;
  $('suggest').hidden = true;
  $('remove-photo').hidden = true;
}
$('model').addEventListener('input', invalidate);
$('batch').addEventListener('input', invalidate);
$('sample').addEventListener('change', invalidate);
$('use-sample').addEventListener('click', () => run('label-message', async () => {
  invalidate(); clearPhoto(); $('upload').value = '';
  $('model').value = ''; $('batch').value = '';
  const data = await request('customer', '/demo/extraction', {sample_id: $('sample').value});
  $('model').value = data.model || ''; $('batch').value = data.batch || '';
  $('sample-model').textContent = `MODEL ${data.model || 'UNREADABLE'}`;
  $('sample-batch').textContent = `BATCH ${data.batch || '????'}`;
  $('sample-preview').hidden = false;
  $('proposal-note').textContent = `Mock example · ${data.notice}`;
  message('label-message', data.clarification || 'Check the suggested values against the example, then confirm.');
}));
$('upload').addEventListener('change', () => run('label-message', async () => {
  const file = $('upload').files[0];
  invalidate(); clearPhoto();
  $('model').value = ''; $('batch').value = '';
  $('sample-preview').hidden = true;
  $('proposal-note').textContent = 'Typed entry. No extraction is running.';
  if (!file) return;
  if (!['image/png', 'image/jpeg'].includes(file.type) || !file.size || file.size > 2 * 1024 * 1024) {
    $('upload').value = '';
    throw new Error('Choose a PNG or JPEG between 1 byte and 2 MiB.');
  }
  const encoded = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = () => reject(new Error('The photo could not be read.'));
    reader.readAsDataURL(file);
  });
  state.image = {image_base64: encoded, mime_type: file.type};
  state.preview = URL.createObjectURL(file);
  $('photo').src = state.preview;
  $('photo-preview').hidden = false;
  $('suggest').hidden = false;
  $('remove-photo').hidden = false;
  message('label-message', modes.ai ? 'Read and confirm the label yourself, or ask the model for a suggestion.' : 'Read and confirm the label, or request a known-fixture suggestion.');
}));
$('remove-photo').addEventListener('click', () => {
  if (state.busy) return;
  clearPhoto(); $('upload').value = ''; invalidate();
  $('proposal-note').textContent = 'Typed entry. No extraction is running.';
});
$('suggest').addEventListener('click', () => run('label-message', async () => {
  if (!state.image) return;
  invalidate(); $('model').value = ''; $('batch').value = '';
  const data = await request('customer', '/demo/image-extraction', state.image);
  $('model').value = data.model || ''; $('batch').value = data.batch || '';
  const read = ['model', 'batch'].map((field) => data.uncertain_fields.includes(field)
    ? `${field} uncertain, left blank`
    : `${field} ${data[field]}${typeof data.confidence[field] === 'number' ? ` (self-reported ${data.confidence[field].toFixed(2)})` : ''}`).join(' · ');
  $('proposal-note').textContent = data.mode === 'ai'
    ? `AI suggestion from ${data.source?.served_model || 'the configured model'} · ${read}. ${data.notice}`
    : `Mock fixture suggestion · ${data.notice}`;
  message('label-message', data.clarification || 'Check the suggestion against the photo, then confirm.');
}));
$('label-form').addEventListener('submit', (event) => {
  event.preventDefault();
  if (!$('confirmed').checked) return;
  run('label-message', async () => {
    state.saved = null; renderAssessment();
    state.saved = await request('customer', '/demo/assessments', {label: {
      image_base64: state.image?.image_base64 || null, mime_type: state.image?.mime_type || null,
      confirmed_model: $('model').value, confirmed_batch: $('batch').value
    }});
    renderAssessment();
    message('label-message', 'Assessment saved. Send it for merchant review when ready.');
  });
});
$('send-review').addEventListener('click', () => run('label-message', async () => {
  if (!state.saved) return;
  await request('customer', '/demo/handoff', {assessment_id: state.saved.assessment_id});
  state.sent = state.saved.assessment_id;
  await refreshCase();
  location.hash = 'review'; view(true);
}));
$('confirm-remedy').addEventListener('click', () => run('review-message', async () => {
  await request('merchant', '/v1/cases/case-demo-1/remedy-conditions', {});
  await refreshCase();
  $('typed-amount').focus();
}));
$('write-brief').addEventListener('click', () => run('review-message', async () => {
  const brief = await request('merchant', '/v1/cases/case-demo-1/brief', {});
  $('brief-mode').textContent = brief.label;
  $('brief-text').textContent = brief.text;
  $('brief-steps').replaceChildren(...brief.missing_steps.map((text) => {
    const item = document.createElement('li'); item.textContent = text; return item;
  }));
  $('brief-citations').textContent = `Sources: ${brief.citations.join(', ')}`;
  $('brief-note').textContent = brief.source === 'ai'
    ? `Drafted by ${brief.served_model || brief.provider}. Shown only because code found every number, identifier and citation in the case records. Advisory: approval stays with the merchant.`
    : brief.fallback_reason === 'no_provider'
      ? 'Template brief. No AI provider is connected in this session. Approval stays with the merchant.'
      : `The AI draft was not shown (${brief.fallback_detail || brief.fallback_reason}); this is the deterministic template instead. Approval stays with the merchant.`;
  $('brief-result').hidden = false;
}));
$('approval-form').addEventListener('submit', (event) => {
  event.preventDefault();
  run('review-message', async () => {
    const {binding} = state.detail;
    const typed = $('typed-amount').value.trim();
    const [whole, fraction = ''] = typed.split('.');
    if (!/^\d+(?:\.\d{1,2})?$/.test(typed) || Number(whole) * 100 + Number(fraction.padEnd(2, '0')) !== binding.amount_minor)
      throw new Error('Type the exact refund amount shown above.');
    const approver = $('approver').value.trim();
    if (!approver) throw new Error('Enter your name to approve.');
    try {
      await request('merchant', '/v1/cases/case-demo-1/approve', {
        assessment_id: binding.assessment_id, campaign_version: binding.campaign_version,
        capture_id: binding.capture_id, amount_minor: binding.amount_minor, approved_by: approver
      });
    } catch (error) {
      // A lost response can follow acceptance. Read the same operation before
      // allowing another action; never silently repeat an approval or refund.
      await refreshCase();
      throw error;
    }
    $('typed-amount').value = '';
    await refreshCase();
    location.hash = 'status'; view(true);
  });
});
$('reconcile').addEventListener('click', () => run('status-message', async () => {
  await request('merchant', '/v1/cases/case-demo-1/reconcile', {});
  await refreshCase();
}));

view();
run('app-message', async () => {
  const [customer, merchant, session] = await Promise.all([request('customer', '/health'), request('merchant', '/health'), request('session')]);
  if (!customer.handoff_enabled || !['mock', 'ai'].includes(customer.extraction_mode) || !['mock', 'sandbox'].includes(merchant.mode))
    throw new Error('This workspace requires the integrated launcher.');
  Object.assign(modes, {ai: customer.extraction_mode === 'ai', aiBrief: merchant.brief === 'ai',
    sandbox: merchant.mode === 'sandbox', loseFirst: session.lose_first_refund_response === true});
  applyModes();
  $('reset-demo').hidden = session.hosted !== true;
  try {
    state.saved = await request('customer', '/v1/assessments/case-demo-1');
    $('model').value = state.saved.model || ''; $('batch').value = state.saved.batch || '';
    $('confirmed').checked = true;
    renderAssessment();
  } catch (error) { if (error.status !== 404) throw error; }
  await refreshCase();
});
// Passive reads only. Approval, remedy confirmation and reconciliation always
// require a click; switching views never performs a payment operation.
setInterval(() => {
  if (state.view === 'status' && state.detail?.resolution.status === 'pending' && !state.busy && !document.hidden)
    run('status-message', refreshCase);
}, 5000);
window.addEventListener('pagehide', () => { if (state.preview) URL.revokeObjectURL(state.preview); });

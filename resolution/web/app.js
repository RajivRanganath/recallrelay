'use strict';
const $ = (id) => document.getElementById(id);
const statusLabels = {
  needs_information: 'Needs information', awaiting_approval: 'Awaiting your approval', pending: 'Refund pending',
  refunded: 'Refunded', failed: 'Refund failed', manual_required: 'Manual handling required', excluded: 'Excluded from campaign'
};
let selected = null;
let detail = null;
let busy = false;

async function request(path, method = 'GET', body) {
  const response = await fetch(path, {
    method,
    headers: body === undefined ? {} : {'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(8000)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The request could not be completed.');
  return data;
}
const money = (minor, currency) => `${(minor / 100).toFixed(2)} ${currency}`;
function facts(list, rows) {
  list.replaceChildren();
  for (const [name, value] of rows) {
    const dt = document.createElement('dt');
    const dd = document.createElement('dd');
    dt.textContent = name;
    dd.textContent = value;
    list.append(dt, dd);
  }
}
function lock(value) {
  busy = value;
  for (const id of ['load-demo', 'confirm-remedy', 'typed-amount', 'approver', 'approve', 'reconcile']) $(id).disabled = value;
}
async function run(work) {
  if (busy) return;
  lock(true);
  $('message').textContent = '';
  try { await work(); } catch (error) { $('message').textContent = error.message; } finally { lock(false); }
}

async function loadList() {
  const {cases} = await request('/v1/cases');
  const list = $('case-list');
  list.replaceChildren();
  for (const item of cases) {
    const li = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'secondary case-button';
    button.textContent = `${item.case_id} · ${statusLabels[item.status] || item.status}`;
    if (item.case_id === selected) button.setAttribute('aria-current', 'true');
    button.addEventListener('click', () => run(() => open(item.case_id)));
    li.append(button);
    list.append(li);
  }
  $('list-message').textContent = cases.length ? '' : 'No cases yet.';
}

async function open(caseId) {
  selected = caseId;
  detail = await request(`/v1/cases/${encodeURIComponent(caseId)}`);
  render();
  await loadList();
}

function render() {
  const {resolution, assessment, order, binding} = detail;
  $('detail').hidden = false;
  $('detail-title').textContent = resolution.case_id;
  $('status-line').textContent = `${statusLabels[resolution.status] || resolution.status} · mode: ${resolution.mode}`;
  $('brief').textContent = resolution.brief;
  facts($('assessment'), [
    ['Decision', assessment.decision], ['Model', assessment.model || 'not confirmed'], ['Batch', assessment.batch || 'not confirmed'],
    ['Reason', assessment.reason], ['Assessment mode', assessment.mode],
    ['Evidence', assessment.evidence.map((e) => `${e.source_id}: ${e.field} = ${e.value}`).join('; ') || 'none cited']
  ]);
  facts($('order'), [
    ['Order', order.order_id], ['Paid', money(order.paid_minor, binding.currency)],
    ['Already refunded', money(order.previously_refunded_minor, binding.currency)],
    ['Purchase age', `${order.age_days} days`], ['Units', String(order.quantity)]
  ]);
  const locked = ['pending', 'refunded', 'failed'].includes(resolution.status);
  $('remedy-text').textContent = detail.remedy_conditions_met
    ? 'You confirmed the remedy conditions are met.'
    : 'Not yet confirmed. Confirm only after checking the campaign’s remedy conditions yourself.';
  $('confirm-remedy').hidden = detail.remedy_conditions_met || locked || assessment.decision !== 'eligible';
  $('approval').hidden = resolution.status !== 'awaiting_approval';
  $('amount').textContent = money(binding.amount_minor, binding.currency);
  $('typed-amount').value = '';
  $('outcome').hidden = !locked;
  if (locked) {
    $('outcome-mode').textContent = resolution.mode === 'sandbox' ? 'PayPal sandbox' : 'Mock · fake PayPal, no money moved';
    $('outcome-title').textContent = statusLabels[resolution.status];
    $('outcome-text').textContent = resolution.brief;
    $('outcome-ids').textContent = `Operation ${resolution.operation_id || 'none'} · refund ${resolution.refund_id || 'none yet'}`;
    $('reconcile').hidden = resolution.status !== 'pending';
  }
}

$('load-demo').addEventListener('click', () => run(async () => {
  await request('/v1/demo/case', 'POST');
  await open('case-demo-1');
}));
$('confirm-remedy').addEventListener('click', () => run(async () => {
  await request(`/v1/cases/${encodeURIComponent(selected)}/remedy-conditions`, 'POST');
  await open(selected);
}));
$('approval-form').addEventListener('submit', (event) => {
  event.preventDefault();
  run(async () => {
    const {binding} = detail;
    if (Number($('typed-amount').value) !== binding.amount_minor / 100 || !$('typed-amount').value.trim()) throw new Error('The typed amount must match the refund amount exactly.');
    const approver = $('approver').value.trim();
    if (!approver) throw new Error('Enter your name to approve.');
    await request(`/v1/cases/${encodeURIComponent(selected)}/approve`, 'POST', {
      assessment_id: binding.assessment_id, campaign_version: binding.campaign_version,
      capture_id: binding.capture_id, amount_minor: binding.amount_minor, approved_by: approver
    });
    await open(selected);
    $('outcome').focus();
  });
});
$('reconcile').addEventListener('click', () => run(async () => {
  await request(`/v1/cases/${encodeURIComponent(selected)}/reconcile`, 'POST');
  await open(selected);
}));

(async () => {
  try {
    const health = await request('/health');
    const mock = health.mode !== 'sandbox';
    $('mode-banner').textContent = mock
      ? 'Mock payments: refunds use a fake PayPal and no money moves. Fictional brand, products and orders only.'
      : 'PayPal sandbox mode. Fictional brand and orders only; no live money.';
    $('footer-mode').textContent = mock ? 'fake PayPal (mock)' : 'PayPal sandbox';
    await loadList();
  } catch (error) { $('message').textContent = error.message; }
})();

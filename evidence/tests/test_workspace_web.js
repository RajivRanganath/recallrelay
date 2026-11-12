'use strict';
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = readFileSync(path.join(__dirname, '../workspace/app.js'), 'utf8');
const turn = () => new Promise(setImmediate);
const ok = (data) => ({ok: true, status: 200, json: async () => structuredClone(data)});
const missing = () => ({ok: false, status: 404, json: async () => ({error: 'Not found'})});
function detail(status = 'awaiting_approval') {
  return {
    resolution: {case_id: 'case-demo-1', status, mode: 'mock', brief: 'Synthetic record', proposed_amount_minor: 4000, operation_id: null, refund_id: null},
    assessment: {assessment_id: 'saved-1', decision: 'eligible', model: 'LAMP-100', batch: 'B101', reason: 'Matched', evidence: []},
    order: {order_id: 'order-demo-1', paid_minor: 4000, previously_refunded_minor: 0, age_days: 30, quantity: 1},
    binding: {assessment_id: 'saved-1', campaign_version: 1, capture_id: 'capture-demo-NOT-PAYPAL', amount_minor: 4000, currency: 'USD'},
    remedy_conditions_met: status !== 'manual_required'
  };
}
// DOM doubles cover state transitions; actual browser QA is recorded separately.
async function app(initial = detail(), handlers = {}) {
  const elements = new Map();
  const node = () => ({value: '', checked: false, disabled: false, hidden: true, textContent: '', listeners: {},
    attrs: {}, classes: new Set(), children: [],
    classList: {toggle() {}},
    addEventListener(name, work) { this.listeners[name] = work; },
    setAttribute(name, value) { this.attrs[name] = value; }, removeAttribute(name) { delete this.attrs[name]; },
    replaceChildren(...children) { this.children = children; }, focus() {}});
  const element = (id) => { if (!elements.has(id)) elements.set(id, node()); return elements.get(id); };
  const calls = [];
  const events = {};
  let hash = '#review';
  const location = {get hash() { return hash; }, set hash(value) { hash = value.startsWith('#') ? value : '#' + value; }};
  let current = initial;
  const context = vm.createContext({
    document: {getElementById: element, createElement: node, querySelectorAll: () => [...elements.values()], hidden: false},
    window: {addEventListener(name, work) { events[name] = work; }}, location,
    AbortSignal: {timeout() {}}, setInterval(work) { events.interval = work; }, setTimeout(work) { events.timeout = work; }, URL,
    fetch: async (url, options) => {
      calls.push({url, method: options.method, body: options.body && JSON.parse(options.body)});
      if (handlers[url]) return handlers[url](options, () => current, (value) => { current = value; });
      if (url === '/api/customer/health') return ok({handoff_enabled: true, extraction_mode: 'mock'});
      if (url === '/api/merchant/health') return ok({mode: 'mock', brief: 'template'});
      if (url === '/api/session') return ok({lose_first_refund_response: false});
      if (url === '/api/customer/v1/assessments/case-demo-1') return current ? ok(current.assessment) : missing();
      if (url === '/api/merchant/v1/cases/case-demo-1') return current ? ok(current) : missing();
      if (url === '/api/customer/demo/resolution-status') return current ? ok(current.resolution) : missing();
      throw new Error('Unexpected request: ' + url);
    }
  });
  vm.runInContext(source, context);
  await turn(); await turn();
  return {element, calls, events, location, setDetail(value) { current = value; }};
}
test('restores the submitted case without posting or selecting a second app', async () => {
  const ui = await app();
  assert.equal(ui.element('view-review').hidden, false);
  assert.equal(ui.element('review-content').hidden, false);
  assert.equal(ui.element('send-review').disabled, true);
  assert.ok(ui.calls.every((call) => call.method === 'GET' && call.url.startsWith('/api/')));
  assert.match(ui.element('customer-status').textContent, /Same case, operation and refund/);
});
test('an identifier edit invalidates confirmation and prevents handoff', async () => {
  const ui = await app();
  ui.element('batch').listeners.input();
  assert.equal(ui.element('confirmed').checked, false);
  assert.equal(ui.element('assessment-result').hidden, true);
  assert.equal(ui.element('send-review').disabled, true);
  await ui.element('send-review').listeners.click();
  assert.equal(ui.calls.some((call) => call.method === 'POST'), false);
});
test('wrong typed amount sends no approval; exact amount binds saved assessment', async () => {
  const ui = await app(detail(), {'/api/merchant/v1/cases/case-demo-1/approve': (_options, get, set) => {
    const done = structuredClone(get()); done.resolution.status = 'refunded';
    done.resolution.operation_id = 'op-1'; done.resolution.refund_id = 'fake-1'; set(done);
    return ok(done.resolution);
  }});
  ui.element('typed-amount').value = '39.99'; ui.element('approver').value = 'Synthetic reviewer';
  await ui.element('approval-form').listeners.submit({preventDefault() {}});
  await turn(); await turn();
  assert.equal(ui.calls.some((call) => call.method === 'POST'), false);
  assert.match(ui.element('review-message').textContent, /exact refund amount/);
  ui.element('typed-amount').value = '40.00';
  await ui.element('approval-form').listeners.submit({preventDefault() {}});
  await turn(); await turn();
  assert.deepEqual(ui.calls.filter((call) => call.method === 'POST'), [{
    url: '/api/merchant/v1/cases/case-demo-1/approve', method: 'POST', body: {
      assessment_id: 'saved-1', campaign_version: 1, capture_id: 'capture-demo-NOT-PAYPAL', amount_minor: 4000, approved_by: 'Synthetic reviewer'
    }
  }]);
  assert.equal(ui.location.hash, '#status');
  assert.equal(ui.element('outcome-title').textContent, 'Refunded');
});
test('navigation and pending polling only read; reconciliation remains explicit', async () => {
  const ui = await app(detail('pending'));
  ui.location.hash = '#status'; ui.events.hashchange();
  await turn(); await turn();
  ui.events.interval(); await turn(); await turn();
  assert.equal(ui.calls.some((call) => call.method === 'POST'), false);
  assert.equal(ui.element('reconcile').hidden, false);
  assert.equal(ui.element('approval').hidden, true);
});
test('a remedy change invalidates the previously generated brief', async () => {
  const ui = await app(detail('manual_required'), {
    '/api/merchant/v1/cases/case-demo-1/brief': () => ok({label: 'Template', text: 'Conditions missing', missing_steps: [], citations: ['review']}),
    '/api/merchant/v1/cases/case-demo-1/remedy-conditions': (_options, _get, set) => { set(detail()); return ok({}); }
  });
  await ui.element('write-brief').listeners.click();
  assert.equal(ui.element('brief-result').hidden, false);
  await ui.element('confirm-remedy').listeners.click();
  assert.equal(ui.element('brief-result').hidden, true);
  assert.equal(ui.element('approval').hidden, false);
});
test('lost approval response reads the accepted operation without automatic retry', async () => {
  const ui = await app(detail(), {'/api/merchant/v1/cases/case-demo-1/approve': (_options, get, set) => {
    const pending = structuredClone(get()); pending.resolution.status = 'pending'; pending.resolution.operation_id = 'op-1'; set(pending);
    throw new Error('Response lost; refresh status');
  }});
  ui.element('typed-amount').value = '40.00'; ui.element('approver').value = 'Synthetic reviewer';
  await ui.element('approval-form').listeners.submit({preventDefault() {}});
  await turn(); await turn();
  assert.equal(ui.calls.filter((call) => call.method === 'POST').length, 1);
  assert.equal(ui.element('approval').hidden, true);
  assert.equal(ui.element('outcome-title').textContent, 'Refund pending');
  assert.match(ui.element('review-message').textContent, /Response lost/);
});
const live = {
  '/api/customer/health': () => ok({handoff_enabled: true, extraction_mode: 'ai'}),
  '/api/merchant/health': () => ok({mode: 'sandbox', brief: 'ai'}),
  '/api/session': () => ok({lose_first_refund_response: true})
};
test('labels follow the modes the services report, never a fixed claim', async () => {
  const mock = await app();
  assert.match(mock.element('mode-chip').textContent, /Mock label reading · template brief · fake payments/);
  assert.equal(mock.element('approve').textContent, 'Approve fake refund');
  const ui = await app(detail(), live);
  assert.match(ui.element('mode-chip').textContent, /Live AI label reading · AI brief · PayPal sandbox refunds/);
  assert.equal(ui.element('approve').textContent, 'Approve sandbox refund');
  assert.equal(ui.element('suggest').textContent, 'Read label with AI');
  assert.match(ui.element('footer-modes').textContent, /no live money/);
  // A sandbox case that has not reached PayPal yet must not be described as fake payments.
  assert.match(ui.element('review-status').textContent, /PayPal sandbox: no live money/);
  assert.equal(ui.element('outcome-mode').textContent, 'PayPal sandbox · simulated funds');
  const fake = await app(detail());
  assert.match(fake.element('review-status').textContent, /Fake payments: no money moves/);
});
test('the reset control appears only on the hosted demo and asks the gateway for a fresh session', async () => {
  const local = await app();
  assert.equal(local.element('reset-demo').hidden, true);
  const ui = await app(detail(), {'/api/session': () => ok({lose_first_refund_response: false, hosted: true}),
    '/api/session/reset': () => ok({reset: true})});
  assert.equal(ui.element('reset-demo').hidden, false);
  await ui.element('reset-demo').listeners.click();
  assert.deepEqual(ui.calls.filter((call) => call.method === 'POST').map((call) => call.url), ['/api/session/reset']);
  assert.match(ui.element('app-message').textContent, /fresh demo session/);
  assert.equal(typeof ui.events.timeout, 'function');
});
test('a rejected AI draft is disclosed and replaced by the template', async () => {
  const ui = await app(detail(), {...live,
    '/api/merchant/v1/cases/case-demo-1/brief': () => ok({source: 'template', label: 'Template text, no AI involved', text: 'T',
      missing_steps: [], citations: ['order'], fallback_reason: 'invalid_output', fallback_detail: 'Number not in the supplied records'})});
  await ui.element('write-brief').listeners.click();
  assert.equal(ui.element('brief-mode').textContent, 'Template text, no AI involved');
  assert.match(ui.element('brief-note').textContent, /AI draft was not shown \(Number not in the supplied records\)/);
});
test('a lost refund acknowledgement is explained, then recovery reports one refund', async () => {
  const pending = detail('pending'); pending.resolution.mode = 'sandbox'; pending.resolution.operation_id = 'op-1';
  const ui = await app(pending, {...live,
    '/api/merchant/v1/cases/case-demo-1/reconcile': (options, get, set) => {
      const done = detail('refunded'); done.resolution.mode = 'sandbox';
      done.resolution.operation_id = 'op-1'; done.resolution.refund_id = 'REFUND-1'; set(done);
      return ok(done.resolution);
    }});
  assert.equal(ui.element('recovery-note').hidden, false);
  assert.match(ui.element('recovery-note').textContent, /deliberately discarded.*no second refund/);
  await ui.element('reconcile').listeners.click();
  assert.match(ui.element('recovery-note').textContent, /Recovered.*No duplicate refund/);
  assert.equal(ui.calls.filter((call) => call.url.endsWith('/reconcile')).length, 1);
});

'use strict';
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const html = readFileSync(path.join(__dirname, '../evals/review_page.html'), 'utf8');
const source = html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];

// DOM doubles exercise record serialization/state; rendered QA is separate.
function page() {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      value: '', disabled: true, required: false, checked: false, textContent: '', listeners: {},
      dataset: {}, addEventListener(name, handler) { this.listeners[name] = handler; }
    });
    return elements.get(id);
  };
  const packet = {packet_sha256: 'synthetic-packet-fingerprint', cases: [
    {sample_id: 'label-001', image_sha256: 'synthetic-image-fingerprint'}
  ]};
  element('packet').textContent = JSON.stringify(packet);
  const choices = ['model', 'batch'].map(field => {
    const select = element(`label-001-${field}-state`);
    select.dataset.value = `label-001-${field}-value`;
    return select;
  });
  const form = element('review-form');
  form.valid = true;
  form.reportValidity = () => form.valid;
  form.querySelectorAll = () => choices;
  let blob = null;
  let downloads = 0;
  vm.runInNewContext(source, {
    document: {getElementById: element, createElement() { return {click() { downloads++; }}; }},
    Blob, URL: {createObjectURL(value) { blob = value; return 'blob:synthetic'; }, revokeObjectURL() {}},
    setTimeout(callback) { callback(); }
  });
  return {element, choices, form, get blob() { return blob; }, get downloads() { return downloads; },
    choose(field, status) {
      const select = element(`label-001-${field}-state`);
      select.value = status;
      select.listeners.change();
    }, submit() { form.listeners.submit({preventDefault() {}}); }};
}

test('download binds entered values to the packet without prefilled references or network', async () => {
  const ui = page();
  assert.equal(ui.element('label-001-model-value').value, '');
  ui.element('attest').checked = true;
  ui.element('reviewer').value = ' automated-unit-test-only-not-human ';
  ui.choose('model', 'readable');
  assert.equal(ui.element('label-001-model-value').disabled, false);
  assert.equal(ui.element('label-001-model-value').required, true);
  ui.element('label-001-model-value').value = ' LAMP-100 ';
  ui.choose('batch', 'unreadable');
  ui.submit();
  assert.equal(ui.downloads, 1);
  const record = JSON.parse(await ui.blob.text());
  assert.equal(record.packet_sha256, 'synthetic-packet-fingerprint');
  assert.equal(record.reviewer, 'automated-unit-test-only-not-human');
  assert.equal(record.cases[0].image_sha256, 'synthetic-image-fingerprint');
  assert.deepEqual(record.cases[0].model, {status: 'readable', value: 'LAMP-100'});
  assert.deepEqual(record.cases[0].batch, {status: 'unreadable', value: null});
  assert.equal(record.human_validated, undefined);
  assert.equal(record.holdout, undefined);
});

test('changing to conflicting clears a stale readable value before export', async () => {
  const ui = page();
  ui.element('attest').checked = true;
  ui.element('reviewer').value = 'automated-unit-test-only-not-human';
  ui.choose('model', 'missing');
  ui.choose('batch', 'readable');
  ui.element('label-001-batch-value').value = 'B101';
  ui.choose('batch', 'conflicting');
  assert.equal(ui.element('label-001-batch-value').value, '');
  assert.equal(ui.element('label-001-batch-value').disabled, true);
  assert.equal(ui.element('label-001-batch-value').required, false);
  ui.submit();
  assert.deepEqual(JSON.parse(await ui.blob.text()).cases[0].batch, {status: 'conflicting', value: null});
  assert.match(ui.element('progress').textContent, /^2 \/ 2 fields/);
});

test('invalid forms and whitespace-only readable values produce no download', () => {
  const ui = page();
  ui.form.valid = false;
  ui.submit();
  assert.equal(ui.downloads, 0);
  ui.form.valid = true;
  ui.element('attest').checked = true;
  ui.element('reviewer').value = 'automated-unit-test-only-not-human';
  ui.choose('model', 'readable');
  ui.element('label-001-model-value').value = '   ';
  ui.choose('batch', 'missing');
  ui.submit();
  assert.equal(ui.downloads, 0);
  assert.match(ui.element('message').textContent, /nonblank/);
});

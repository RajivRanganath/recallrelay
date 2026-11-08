'use strict';
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return {promise, resolve};
}
const turn = () => new Promise(setImmediate);
const response = (data) => ({ok: true, json: async () => data});
// DOM doubles test async state; they do not replace browser QA.
function app() {
  const elements = new Map();
  const element = (id) => {
    if (!elements.has(id)) elements.set(id, {
      value: '', checked: false, disabled: false, hidden: true, textContent: '', files: [], listeners: {},
      addEventListener(name, handler) { this.listeners[name] = handler; },
      removeAttribute(name) { delete this[name]; }, focus() {}
    });
    return elements.get(id);
  };
  const health = deferred();
  const sample = deferred();
  const calls = [];
  class Reader {
    readAsDataURL() { this.result = 'data:image/png;base64,c3ludGhldGlj'; this.onload(); }
  }
  vm.runInNewContext(source, {
    document: {getElementById: element}, FileReader: Reader,
    URL: {createObjectURL: () => 'blob:synthetic', revokeObjectURL() {}},
    AbortSignal: {timeout() {}},
    fetch: async (url) => {
      calls.push(url);
      if (url === '/health') return health.promise;
      if (url === '/demo/extraction') return sample.promise;
      throw new Error('Unexpected request: ' + url);
    }
  });
  return {element, health, sample, calls};
}
async function upload(ui) {
  ui.element('upload').files = [{type: 'image/png', size: 16}];
  await ui.element('upload').listeners.change();
}
test('late health enables suggestions for an already prepared photo', async () => {
  for (const mode of ['mock', 'ai']) {
    const ui = app();
    await upload(ui);
    assert.equal(ui.element('suggest-image').disabled, true);
    ui.health.resolve(response({extraction_mode: mode}));
    await turn();
    assert.equal(ui.element('suggest-image').disabled, false);
    assert.equal(ui.element('suggest-image').textContent,
      mode === 'ai' ? 'Read label with AI' : 'Suggest from fixture image (mock)');
    assert.deepEqual(ui.calls, ['/health']);
  }
});
test('late AI configuration preserves loaded sample provenance', async () => {
  const ui = app();
  ui.sample.resolve(response({model: 'LAMP-100', batch: 'B101', notice: 'Synthetic sample.'}));
  await ui.element('load-sample').listeners.click();
  const note = ui.element('proposal-note').textContent;
  assert.match(note, /^Mock assistant/);
  ui.health.resolve(response({extraction_mode: 'ai'}));
  await turn();
  assert.equal(ui.element('proposal-note').textContent, note);
  assert.equal(ui.element('confirmed').checked, false);
});
test('configuration completion cannot unlock an operation still busy', async () => {
  const ui = app();
  const loading = ui.element('load-sample').listeners.click();
  ui.health.resolve(response({extraction_mode: 'ai'}));
  await turn();
  assert.equal(ui.element('model').disabled, true);
  assert.equal(ui.element('suggest-image').disabled, true);
  ui.sample.resolve(response({model: 'LAMP-100', batch: 'B101', notice: 'Synthetic sample.'}));
  await loading;
  assert.equal(ui.element('model').disabled, false);
});
test('invalid health keeps extraction disabled and typed entry usable', async () => {
  const ui = app();
  await upload(ui);
  ui.health.resolve(response({extraction_mode: 'unexpected'}));
  await turn();
  assert.equal(ui.element('suggest-image').disabled, true);
  assert.equal(ui.element('model').disabled, false);
  assert.match(ui.element('extraction-status').textContent, /unavailable/i);
  assert.deepEqual(ui.calls, ['/health']);
});

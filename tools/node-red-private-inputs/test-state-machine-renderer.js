// Exercise the dependency that pins Handlebars, without a flow or device connection.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const { createRequire } = require('node:module');
const { pathToFileURL } = require('node:url');
const path = require('node:path');
const app = createRequire(path.resolve('node-red/config/package.json'));
const stateMachine = createRequire(app.resolve('state-machine-cat'));
// The node invokes the ESM CLI. require.resolve selects a separate CJS wrapper.
const rendererUrl = new URL('../../src/index.mjs', pathToFileURL(app.resolve('state-machine-cat')));

test('state-machine renderer resolves patched Handlebars', () => {
    assert.equal(stateMachine('handlebars/package.json').version, '4.7.10');
});

test('the bundled precompiled DOT templates retain transitions and labels', async () => {
    const { render } = await import(rendererUrl);
    const dot = render('idle => active: start; active => idle: stop;', { outputType: 'dot' });
    assert.match(dot, /digraph/);
    assert.match(dot, /"idle" -> "active"/);
    assert.match(dot, /start/);
    assert.match(dot, /stop/);
});

test('the bundled state-machine text template retains round-trip semantics', async () => {
    const { render } = await import(rendererUrl);
    const source = 'idle => active: start; active => idle: stop;';
    const rendered = render(source, { outputType: 'smcat' });
    assert.deepEqual(render(rendered, { outputType: 'json' }), render(source, { outputType: 'json' }));
});

test('renderer still rejects invalid state-machine input', async () => {
    const { render } = await import(rendererUrl);
    assert.throws(() => render('idle => ;', { outputType: 'dot' }), /Expected/);
});

// Exercise the HA node's resolved JSONata dependency without a running flow or devices.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const { createRequire } = require('node:module');
const path = require('node:path');
const fs = require('node:fs');
const app = createRequire(path.resolve('node-red/config/package.json'));
const ha = createRequire(app.resolve('node-red-contrib-home-assistant-websocket/package.json'));
const jsonata = ha('jsonata');
const { setRED } = ha('./dist/globals');
const JSONataService = ha('./dist/common/services/JSONataService').default;

setRED({ util: {
    prepareJSONataExpression: expression => jsonata(expression),
    evaluateJSONataExpression: (expression, message, callback) => {
        expression.evaluate(message).then(value => callback(null, value), callback);
    },
} });

test('the HA node resolves the patched JSONata release', () => {
    assert.equal(ha('jsonata/package.json').version, '2.2.2');
});

test('prototype properties are unavailable to expression lookup', async () => {
    assert.equal(await jsonata('$lookup({}, "__proto__")').evaluate({}), undefined);
    assert.equal(await jsonata('$lookup({}, "constructor")').evaluate({}), undefined);
});

test('crafted function lookup cannot construct even a harmless function', async () => {
    // Regression for GHSA-2943-5xfg-gq5f. The attempted body only returns a number.
    const expression = '($hasOwnProperty := $spread($string); $__proto__ := $constructor; $constructor("return 7")())';
    await assert.rejects(() => jsonata(expression).evaluate({}));
});

test('normal transformations, dates and asynchronous bindings retain their results', async () => {
    assert.equal(await jsonata('$sum(payload.values)').evaluate({ payload: { values: [2, 3, 5] } }), 10);
    assert.equal(await jsonata('$toMillis("2026-01-01T00:00:00Z")').evaluate({}), 1767225600000);
    const expression = jsonata('$double(payload)');
    expression.assign('double', async value => value * 2);
    assert.equal(await expression.evaluate({ payload: 4 }), 8);
});

test('the actual HA service preserves entity and previous-state bindings', async () => {
    const service = new JSONataService({ node: {} });
    const result = await service.evaluate('{"current": $entity().state, "previous": $prevEntity().state, "payload": payload}', {
        entity: { state: 'on' }, prevEntity: { state: 'off' }, message: { payload: 9 },
    });
    // Patched JSONata deliberately constructs objects without inherited properties.
    const expected = Object.assign(Object.create(null), { current: 'on', previous: 'off', payload: 9 });
    assert.deepEqual(result, expected);
});

test('the actual HA service preserves entity lookup and output-data bindings', async () => {
    const states = { 'sensor.fixture': { state: '12' } };
    const service = new JSONataService({ node: {}, homeAssistant: {
        websocket: { getState: id => states[id], getStates: () => states },
    } });
    assert.equal(await service.evaluate('$number($entities("sensor.fixture").state) + $outputData("amount")', { amount: 3 }), 15);
});

test('the actual HA service still rejects malformed expressions', async () => {
    const service = new JSONataService({ node: {} });
    await assert.rejects(() => service.evaluate('payload['));
});

test('JSONata expressions explicitly typed in the public flows still parse', () => {
    let count = 0;
    function visit(value) {
        if (!value || typeof value !== 'object') return;
        if (Array.isArray(value)) { value.forEach(visit); return; }
        for (const [key, type] of Object.entries(value)) {
            if (type !== 'jsonata') continue;
            const field = { tot: 'to', vt: 'v' }[key] ||
                (key.endsWith('Type') ? key.slice(0, -4) : key.endsWith('type') ? key.slice(0, -4) : null);
            if (field && typeof value[field] === 'string' && value[field].trim()) {
                jsonata(value[field]);
                count++;
            }
        }
        Object.values(value).forEach(visit);
    }
    visit(JSON.parse(fs.readFileSync('node-red/config/flows.json', 'utf8')));
    assert.ok(count > 0, 'the fixture must exercise real public flow expressions');
});

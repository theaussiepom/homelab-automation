'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {createRequire} = require('node:module');
const path = require('node:path');
const app = createRequire(path.resolve(__dirname, '../../node-red/config/package.json'));
const influx = createRequire(app.resolve('node-red-contrib-influxdb/package.json'));
const lodash = influx('lodash');

function outputNode(version, client) {
    const registered = {};
    const RED = {_: key => key, nodes: {
        registerType(name, constructor) { registered[name] = constructor; },
        getNode() { return {influxdbVersion: version, client}; },
        createNode(node) {
            node.handlers = {};
            node.on = (event, handler) => { node.handlers[event] = handler; };
            node.error = error => { throw new Error(String(error)); };
        },
    }};
    influx('./influxdb.js')(RED);
    return new registered['influxdb out']({influxdb: 'fixture', measurement: 'reading', precision: 'ms', org: 'fixture', bucket: 'fixture'});
}
function input(node, message) {
    return new Promise((resolve, reject) => node.handlers.input(message, () => {}, error => error ? reject(error) : resolve()));
}

test('InfluxDB resolves patched Lodash', () => {
    assert.equal(lodash.VERSION, '4.18.1');
});
test('template imports reject a default-parameter key', () => {
    // Harmless regression: compilation must reject the key, without executing code.
    assert.throws(() => lodash.template('fixture', {imports: {'value=1': undefined}}), /Invalid.*imports/i);
});
test('array-wrapped prototype path cannot delete a custom prototype property', () => {
    const prototype = {fixture: true};
    const object = Object.create(prototype);
    lodash.unset(object, [['__proto__'], 'fixture']);
    assert.equal(prototype.fixture, true);
});
test('actual InfluxDB v1 node preserves fields, tags, integer conversion and timestamps', async () => {
    let captured;
    const node = outputNode('1.x', {writePoints: async (points, options) => { captured = {points, options}; }});
    const payload = [[{value: '7i', time: 1234, active: true}, {room: 'fixture'}], [{value: 2}, {room: 'other'}]];
    const original = structuredClone(payload);
    await input(node, {payload});
    assert.deepEqual(captured, {points: [
        {measurement: 'reading', fields: {value: 7, active: true}, tags: {room: 'fixture'}, timestamp: 1234},
        {measurement: 'reading', fields: {value: 2}, tags: {room: 'other'}},
    ], options: {precision: 'ms'}});
    assert.deepEqual(payload, original);
});
test('actual InfluxDB v1 node accepts plain objects and scalar payloads', async () => {
    const writes = [];
    const node = outputNode('1.x', {writePoints: async points => writes.push(points)});
    await input(node, {payload: {value: '3i'}});
    await input(node, {payload: 4});
    assert.deepEqual(writes, [[{measurement: 'reading', fields: {value: 3}}], [{measurement: 'reading', fields: {value: 4}}]]);
});
test('actual InfluxDB v2 node serializes typed fields through its real Point class', async () => {
    const points = [];
    const node = outputNode('2.0', {getWriteApi: () => ({writePoint: point => points.push(point.toLineProtocol()), flush: async () => {}})});
    await input(node, {payload: [{value: '7i', active: true, time: '1234'}, {room: 'fixture'}]});
    assert.deepEqual(points, ['reading,room=fixture active=T,value=7i 1234']);
});

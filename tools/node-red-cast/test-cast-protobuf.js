// Exercise the actual Cast protocol adapter without sockets or device commands.
const assert = require('node:assert/strict');
const { test, before } = require('node:test');
const { createRequire } = require('node:module');
const path = require('node:path');
const app = createRequire(path.resolve(process.env.CAST_FIXTURE_ROOT || 'node-red/config', 'package.json'));
const cast = app('castv2/lib/proto');
const Client = app('castv2/lib/client');
const castRequire = createRequire(app.resolve('castv2/package.json'));

before(async () => {
    for (let i = 0; i < 200; i++) {
        try { cast.AuthChallenge.serialize({}); return; }
        catch (error) {
            if (error.message !== 'extension not loaded yet') throw error;
            await new Promise(resolve => setTimeout(resolve, 10));
        }
    }
    throw new Error('Cast schema did not load');
});

test('Cast resolves the reviewed patched protobuf version', () => {
    assert.equal(castRequire('protobufjs/package.json').version, '7.6.6');
});

test('text messages retain the Cast v2 wire format', () => {
    const client = new Client();
    let packet;
    client.ps = { send: value => { packet = value; } };
    client.send('s', 'd', 'n', 'hi');
    assert.equal(packet.toString('hex'), '08001201731a016422016e280032026869');
    const value = cast.CastMessage.parse(packet);
    assert.equal(value.protocolVersion, 0);
    assert.equal(value.sourceId, 's');
    assert.equal(value.destinationId, 'd');
    assert.equal(value.namespace, 'n');
    assert.equal(value.payloadType, 0);
    assert.equal(value.payloadUtf8, 'hi');
});

test('binary messages retain bytes rather than stringifying them', () => {
    const client = new Client();
    let packet;
    client.ps = { send: value => { packet = value; } };
    client.send('s', 'd', 'n', Buffer.from([0, 128, 255]));
    assert.equal(packet.toString('hex'), '08001201731a016422016e28013a030080ff');
    const value = cast.CastMessage.parse(packet);
    assert.equal(value.payloadType, 1);
    assert.deepEqual(value.payloadBinary, Buffer.from([0, 128, 255]));
});

test('auth response and repeated CA byte fields round trip', () => {
    const value = { signature: Buffer.from([1, 2]), clientAuthCertificate: Buffer.from([3]),
        clientCa: [Buffer.from([4]), Buffer.from([5, 6])] };
    const parsed = cast.AuthResponse.parse(cast.AuthResponse.serialize(value));
    assert.deepEqual(parsed.signature, value.signature);
    assert.deepEqual(parsed.clientAuthCertificate, value.clientAuthCertificate);
    assert.deepEqual(parsed.clientCa, value.clientCa);
});

test('empty challenge and nested auth error are supported', () => {
    assert.equal(cast.AuthChallenge.serialize({}).length, 0);
    const packet = cast.DeviceAuthMessage.serialize({ error: { errorType: 1 } });
    assert.equal(cast.DeviceAuthMessage.parse(packet).error.errorType, 1);
});

test('truncated and missing-required-field messages are rejected', () => {
    assert.throws(() => cast.CastMessage.parse(Buffer.from([0x12, 0x05, 0x61])));
    assert.throws(() => cast.CastMessage.parse(Buffer.alloc(0)));
});

// Exercise the Cast node's actual TTS dependency; adapters never open a connection.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const { createRequire } = require('node:module');
const path = require('node:path');
const app = createRequire(path.resolve('node-red/config/package.json'));
const cast = createRequire(app.resolve('node-red-contrib-cast/package.json'));
const tts = cast('google-tts-api');
const ttsRequire = createRequire(cast.resolve('google-tts-api/package.json'));
const axios = ttsRequire('axios');

test('Cast TTS resolves the patched Axios 0.x release', () => {
    assert.equal(ttsRequire('axios/package.json').version, '0.34.0');
});

test('bodyless requests ignore inherited data', async () => {
    // GHSA-mmx7-hfxf-jppx: use a harmless marker and a local in-memory adapter.
    assert.equal(Object.hasOwn(Object.prototype, 'data'), false);
    Object.defineProperty(Object.prototype, 'data', {
        value: 'inherited-fixture', writable: true, configurable: true,
    });
    try {
        let sent;
        await axios.get('https://example.invalid/fixture', {adapter: async config => {
            sent = config.data;
            return {data: '', status: 200, statusText: 'OK', headers: {}, config};
        }});
        assert.equal(sent, undefined);
    } finally {
        delete Object.prototype.data;
    }
});

test('form serialization ignores an inherited visitor', () => {
    // GHSA-x97p-jq2g-jp4f: the synthetic visitor must never observe form fields.
    assert.equal(Object.hasOwn(Object.prototype, 'visitor'), false);
    let calls = 0;
    const fields = [];
    Object.defineProperty(Object.prototype, 'visitor', {
        configurable: true, writable: true,
        value(value, key, path, helpers) {
            calls++;
            return helpers.defaultVisitor.call(this, value, key, path);
        },
    });
    try {
        axios.toFormData({nested: {label: 'fixture'}}, {append: (key, value) => fields.push([key, value])});
        assert.equal(calls, 0);
        assert.deepEqual(fields, [['nested[label]', 'fixture']]);
    } finally {
        delete Object.prototype.visitor;
    }
});

test('the URL API used by Cast preserves language, text and slow mode', () => {
    const url = new URL(tts.getAudioUrl('Fixture speech', {lang: 'en', slow: true}));
    assert.equal(url.protocol, 'https:');
    assert.equal(url.searchParams.get('q'), 'Fixture speech');
    assert.equal(url.searchParams.get('tl'), 'en');
    assert.equal(url.searchParams.get('ttsspeed'), '0.24');
    const parts = tts.getAllAudioUrls('A fixture sentence. '.repeat(30), {lang: 'en'});
    assert.ok(parts.length > 1);
    assert.ok(parts.every(part => part.shortText.length <= 200));
});

test('TTS request serialization and audio response parsing retain their contract', async () => {
    const prior = axios.defaults.adapter;
    let sent;
    axios.defaults.adapter = async config => {
        sent = config;
        return {data: ")]}'\n" + JSON.stringify([['wrb.fr', 'jQ1olc', JSON.stringify(['Zml4dHVyZQ=='])]]),
            status: 200, statusText: 'OK', headers: {}, config};
    };
    try {
        assert.equal(await tts.getAudioBase64('Fixture speech', {host: 'https://example.invalid', timeout: 4321}), 'Zml4dHVyZQ==');
        assert.equal(sent.method, 'post');
        assert.equal(sent.baseURL, 'https://example.invalid');
        assert.equal(sent.url, '/_/TranslateWebserverUi/data/batchexecute');
        assert.equal(sent.timeout, 4321);
        const request = JSON.parse(decodeURIComponent(sent.data.slice('f.req='.length)));
        assert.equal(JSON.parse(request[0][0][1])[0], 'Fixture speech');
    } finally {
        axios.defaults.adapter = prior;
    }
});

test('TTS still propagates a transport failure', async () => {
    const prior = axios.defaults.adapter;
    axios.defaults.adapter = async () => { throw new Error('synthetic_transport_failure'); };
    try {
        await assert.rejects(() => tts.getAudioBase64('Fixture', {host: 'https://example.invalid'}), /synthetic_transport_failure/);
    } finally {
        axios.defaults.adapter = prior;
    }
});

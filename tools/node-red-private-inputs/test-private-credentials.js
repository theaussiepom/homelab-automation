const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');
const { test } = require('node:test');
const { requirePrivateCredentials } = require('../../node-red/config/private-inputs');

function fixture(t) {
    const mask = process.umask();
    t.after(() => process.umask(mask));
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'nodered-private-credentials-'));
    t.after(() => fs.rmSync(root, {recursive: true, force: true}));
    return path.join(root, 'flows_cred.json');
}

test('missing credentials stop startup without creating a file', t => {
    const file = fixture(t);
    assert.throws(() => requirePrivateCredentials(file), /Restore the private/);
    assert.equal(fs.existsSync(file), false);
});
for (const value of ['{}', '{"$":"synthetic-encrypted-fixture"}']) {
    test('existing credential object remains byte-for-byte unchanged: '+value.length, t => {
        const file = fixture(t);
        fs.writeFileSync(file, value, {mode: 0o600});
        requirePrivateCredentials(file);
        assert.equal(fs.readFileSync(file, 'utf8'), value);
        assert.equal(fs.statSync(file).mode & 0o777, 0o600);
    });
}
for (const value of ['[]', 'null', 'synthetic-private-value']) {
    test('invalid credential store refuses without leaking content: '+value.length, t => {
        const file = fixture(t);
        fs.writeFileSync(file, value);
        assert.throws(() => requirePrivateCredentials(file), error =>
            error.message === 'Restore the private Node-RED credential store before startup');
        assert.equal(fs.readFileSync(file, 'utf8'), value);
    });
}
test('directory and symbolic link cannot replace private credential file', t => {
    const file = fixture(t);
    fs.mkdirSync(file);
    assert.throws(() => requirePrivateCredentials(file), /Restore the private/);
    const target = file + '.json';
    fs.writeFileSync(target, '{}');
    const link = file + '.link';
    fs.symlinkSync(target, link);
    assert.throws(() => requirePrivateCredentials(link), /Restore the private/);
});

for (const mode of [0o644, 0o640, 0o660]) {
    test('permissive credentials refuse without changing mode: ' + mode.toString(8), t => {
        const file = fixture(t);
        fs.writeFileSync(file, '{}', {mode: 0o600});
        fs.chmodSync(file, mode);
        assert.throws(() => requirePrivateCredentials(file), /Restore the private/);
        assert.equal(fs.statSync(file).mode & 0o777, mode);
    });
}
test('credential directory must restrict traversal to its owner', t => {
    const file = fixture(t);
    fs.writeFileSync(file, '{}', {mode: 0o600});
    fs.chmodSync(path.dirname(file), 0o755);
    assert.throws(() => requirePrivateCredentials(file), /Restore the private/);
    assert.equal(fs.statSync(path.dirname(file)).mode & 0o777, 0o755);
});
test('private startup preserves restrictive modes on subsequent atomic writes', t => {
    const file = fixture(t);
    fs.writeFileSync(file, '{}', {mode: 0o600});
    process.umask(0o022);
    requirePrivateCredentials(file);
    const temporary = file + '.temporary';
    fs.writeFileSync(temporary, '{"$":"synthetic-next-version"}');
    fs.renameSync(temporary, file);
    assert.equal(fs.statSync(file).mode & 0o777, 0o600);
});

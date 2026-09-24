const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'static', 'js', 'fresh-account-form.js'), 'utf8');

function field(value, name = '') {
    const listeners = new Map();
    return {
        value,
        name,
        addEventListener(name, callback) { listeners.set(name, callback); },
        emit(name) { listeners.get(name)?.(); },
    };
}

test('account fields start blank and browser-restored values are cleared', () => {
    const email = field('saved@example.com');
    const password = field('saved-password');
    const timeouts = [];
    const listeners = new Map();
    const document = {
        activeElement: null,
        querySelector() { return {hasAttribute() { return false; }, querySelectorAll() { return [email, password]; }}; },
    };
    const window = {
        addEventListener(name, callback) { listeners.set(name, callback); },
        setTimeout(callback) { timeouts.push(callback); },
    };

    vm.runInNewContext(source, {document, window});
    assert.equal(email.value, '');
    assert.equal(password.value, '');

    email.value = 'restored@example.com';
    password.value = 'restored-password';
    listeners.get('pageshow')();
    assert.equal(email.value, '');
    assert.equal(password.value, '');

    email.value = 'late-autofill@example.com';
    timeouts.shift()();
    assert.equal(email.value, '');

    document.activeElement = email;
    email.emit('keydown');
    email.value = 'typed@example.com';
    email.emit('input');
    password.value = 'late-autofill';
    password.emit('focus');
    assert.equal(email.value, 'typed@example.com');
    assert.equal(password.value, '');
});

test('validation error keeps the submitted email but clears the password', () => {
    const email = field('entered@example.com', 'new_email');
    const password = field('saved-password', 'current_password');
    const listeners = new Map();
    const document = {
        activeElement: null,
        querySelector() {
            return {
                hasAttribute(name) { return name === 'data-preserve-restored-email'; },
                querySelectorAll() { return [email, password]; },
            };
        },
    };
    const window = {
        addEventListener(name, callback) { listeners.set(name, callback); },
        setTimeout() {},
    };

    vm.runInNewContext(source, {document, window});
    assert.equal(email.value, 'entered@example.com');
    assert.equal(password.value, '');

    password.value = 'restored-password';
    listeners.get('pageshow')();
    assert.equal(email.value, 'entered@example.com');
    assert.equal(password.value, '');
});

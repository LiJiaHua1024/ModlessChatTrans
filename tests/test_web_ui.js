const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/static/js/main.js', 'utf8');

function messageContext() {
    const node = () => ({querySelector: () => null});
    const context = vm.createContext({
        document: {getElementById: () => ({appendChild() {}, replaceChild() {}})},
        window: {eventSource: {}},
        checkIfAtBottom: () => true,
        trackProcessedMessage() {}, handleMessageScroll() {}, updateClearButtonVisibility() {},
        shouldFoldMessages: () => true,
        createMessageElement: () => ({element: node()}),
        createFoldingGroupElement: () => ({item: node()}),
        addToFoldingHistory() {}, updateFoldingLatest() {}, updateFoldingBadge() {},
        parseMinecraftText: text => text,
        updateRepeatBadge() {}, updateUserMessageMerge() {},
        isTranslating: false,
    });
    vm.runInContext(source.slice(0, source.indexOf('// 乱码效果管理器')), context);
    const start = source.indexOf('window.eventSource.onmessage = function(event)');
    const end = source.indexOf('window.eventSource.onerror', start);
    vm.runInContext(source.slice(start, end), context);
    return context;
}

for (const name of ['', 'Steve']) {
    const ctx = messageContext();
    for (const message of ['Restart in 10 seconds', 'Restart in 11 seconds', 'Restart in 10 seconds']) {
        ctx.window.eventSource.onmessage({data: JSON.stringify({name, message})});
    }
    assert.equal(ctx.foldingGroup.messages.length, 3, 'A/B/A must all remain visible in the group');
    assert.equal(ctx.pendingMessages, 0);
}
async function checkSendRequestOwnership() {
    const ctx = messageContext();
    const requests = [];
    const timers = [];
    Object.assign(ctx, {
        messageInput: {value: 'first'}, sendButton: {},
        translationIndicator: {classList: {add() {}, remove() {}}},
        isRageMode: false, translationRequestId: 0,
        setTimeout: callback => (timers.push(callback), timers.length),
        clearTimeout() {}, console,
        fetch: () => new Promise(resolve => requests.push(resolve)),
    });
    vm.runInContext(source.slice(source.indexOf('function sendMessage()'),
                                 source.indexOf('sendButton.addEventListener("click"')), ctx);
    ctx.sendMessage();
    ctx.window.eventSource.onmessage({data: JSON.stringify({
        name: '[INFO]', message: 'Other client finished', send_translation_complete: true,
    })});
    assert.equal(timers.length, 1, 'SSE must not schedule an unlock');
    timers[0](); // First request times out, allowing another request.
    ctx.messageInput.value = 'second';
    ctx.sendMessage();
    requests[0]({ok: true, json: async () => ({translated: 'first'})});
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(ctx.isTranslating, true, 'Late first response must not unlock second request');
    requests[1]({ok: true, json: async () => ({translated: 'second'})});
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(ctx.isTranslating, false);
}
checkSendRequestOwnership().then(() => console.log('Web UI regression checks passed'));

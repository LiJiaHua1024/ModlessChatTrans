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
console.log('Web UI regression checks passed');

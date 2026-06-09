// 将事件处理程序和初始化代码提取为可重用函数
var messageList = document.getElementById("message-list");
var scrollBottomBtn = document.getElementById("scroll-bottom-btn");
var isUserScrolling = false;
var isAtBottom = true;
var lastScrollTime = Date.now();
var pendingMessages = 0;

var lastEventId = null;
var reconnectDelay = 2000;
var reconnectTimer = null;
var lastHeartbeat = Date.now();
var heartbeatMonitorInterval = null;
var processedMessageIds = new Set();
var processedIdQueue = [];
var maxProcessedIds = 4000;
var translationTimeoutId = null;

// 消息过滤状态
var messageFilters = {
    user: true,
    system: true,
    error: true,
    info: true
};

// 消息合并状态
var lastMergeableMessageText = null;
var lastMergeableMessageElement = null;
var lastMergeableMessageCount = 1;
var lastMergeableMessageType = null;

var lastUserMessageText = null;
var lastUserMessageElement = null;
var lastUserMessageCount = 1;
var lastUserMessageSenders = [];

// Folding group state (for similar but not identical messages)
var foldingGroup = {
    messages: [],      // Array of message objects in the group
    element: null,     // The DOM element for the group
    type: null,        // Message type of the group
    elements: null     // DOM element references (item, bubble, history, latest, toggle)
};

// 乱码效果管理器
var obfuscatedElements = new Set();
var obfuscatedInterval;

// 随机字符池（用于乱码效果）
var obfuscatedChars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()[]{}|;:,.<>?';

// 启动乱码效果
function startObfuscatedEffect() {
    if (obfuscatedInterval) return; // 避免重复启动

    obfuscatedInterval = setInterval(function() {
        obfuscatedElements.forEach(function(element) {
            var originalText = element.getAttribute('data-original');
            if (!originalText) {
                originalText = element.textContent;
                element.setAttribute('data-original', originalText);
            }

            var scrambledText = '';
            for (var i = 0; i < originalText.length; i++) {
                if (originalText[i] === ' ') {
                    scrambledText += ' '; // 保持空格
                } else {
                    scrambledText += obfuscatedChars[Math.floor(Math.random() * obfuscatedChars.length)];
                }
            }
            element.textContent = scrambledText;
        });
    }, 50); // 每50ms更新一次
}

// 停止乱码效果
function stopObfuscatedEffect() {
    if (obfuscatedInterval) {
        clearInterval(obfuscatedInterval);
        obfuscatedInterval = null;
    }
}

// 添加乱码元素
function addObfuscatedElement(element) {
    obfuscatedElements.add(element);
    if (obfuscatedElements.size === 1) {
        startObfuscatedEffect();
    }
}

// 移除乱码元素
function removeObfuscatedElement(element) {
    obfuscatedElements.delete(element);
    if (obfuscatedElements.size === 0) {
        stopObfuscatedEffect();
    }
}

// Calculate similarity percentage using Levenshtein distance
function calculateSimilarity(str1, str2) {
    if (str1 === str2) return 100;

    var len1 = str1.length;
    var len2 = str2.length;
    var maxLen = Math.max(len1, len2);

    if (maxLen === 0) return 100;

    // Use two-row optimization for memory efficiency
    var prevRow = [];
    var currRow = [];

    for (var j = 0; j <= len2; j++) {
        prevRow[j] = j;
    }

    for (var i = 1; i <= len1; i++) {
        currRow[0] = i;
        for (var j = 1; j <= len2; j++) {
            var cost = str1[i - 1] === str2[j - 1] ? 0 : 1;
            currRow[j] = Math.min(
                prevRow[j] + 1,      // deletion
                currRow[j - 1] + 1,  // insertion
                prevRow[j - 1] + cost // substitution
            );
        }
        var temp = prevRow;
        prevRow = currRow;
        currRow = temp;
    }

    var distance = prevRow[len2];
    var similarity = ((maxLen - distance) / maxLen) * 100;
    return similarity;
}

var SIMILARITY_THRESHOLD = 80; // 80% similarity threshold

function shouldFoldMessages(currentType, prevType, currentText, prevText) {
    // Must be same type
    if (currentType !== prevType) return false;

    // Strategy A: Info and Error types - always fold if same type
    if (currentType === 'info' || currentType === 'error') {
        return true;
    }

    // Strategy B: System and Player types - use Levenshtein similarity
    if (currentType === 'system' || currentType === 'user') {
        var similarity = calculateSimilarity(currentText, prevText);
        return similarity > SIMILARITY_THRESHOLD;
    }

    return false;
}

// Minecraft格式化代码解析函数
function parseMinecraftText(text) {
    // 定义格式化代码映射
    var colorCodes = {
        '0': 'mc-color-0', '1': 'mc-color-1', '2': 'mc-color-2', '3': 'mc-color-3',
        '4': 'mc-color-4', '5': 'mc-color-5', '6': 'mc-color-6', '7': 'mc-color-7',
        '8': 'mc-color-8', '9': 'mc-color-9', 'a': 'mc-color-a', 'b': 'mc-color-b',
        'c': 'mc-color-c', 'd': 'mc-color-d', 'e': 'mc-color-e', 'f': 'mc-color-f'
    };

    var formatCodes = {
        'k': 'mc-obfuscated',
        'l': 'mc-bold',
        'm': 'mc-strikethrough',
        'n': 'mc-underline',
        'o': 'mc-italic'
    };

    // 转义HTML字符
    function escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // 将§替换为§符号（防止编码问题）
    text = text.replace(/\\u00A7/g, '§');

    // 分割文本并处理格式化代码
    var parts = text.split(/§([0-9a-fklmnor])/gi);
    var result = '';
    var currentClasses = [];

    for (var i = 0; i < parts.length; i++) {
        if (i % 2 === 0) {
            // 文本部分
            if (parts[i]) {
                if (currentClasses.length > 0) {
                    var hasObfuscated = currentClasses.indexOf('mc-obfuscated') !== -1;
                    var spanId = hasObfuscated ? 'obf-' + Math.random().toString(36).substr(2, 9) : '';
                    var idAttr = hasObfuscated ? ' id="' + spanId + '"' : '';

                    result += '<span class="' + currentClasses.join(' ') + '"' + idAttr + '>' + escapeHtml(parts[i]) + '</span>';

                    // 如果有乱码效果，在DOM加载后添加到管理器中
                    if (hasObfuscated) {
                        setTimeout(function(id) {
                            var element = document.getElementById(id);
                            if (element) {
                                addObfuscatedElement(element);
                            }
                        }, 0, spanId);
                    }
                } else {
                    result += escapeHtml(parts[i]);
                }
            }
        } else {
            // 格式化代码部分
            var code = parts[i].toLowerCase();

            if (code === 'r') {
                // 重置所有格式
                currentClasses = [];
            } else if (colorCodes[code]) {
                currentClasses = currentClasses.filter(function(cls) {
                    return !cls.startsWith('mc-color-');
                });
                currentClasses.push(colorCodes[code]);
            } else if (formatCodes[code]) {
                if (currentClasses.indexOf(formatCodes[code]) === -1) {
                    currentClasses.push(formatCodes[code]);
                }
            }
        }
    }

    return result;
}

function trackProcessedMessage(id) {
    if (id === null || id === undefined) return;
    if (processedMessageIds.has(id)) return;
    processedMessageIds.add(id);
    processedIdQueue.push(id);
    if (processedIdQueue.length > maxProcessedIds) {
        var removed = processedIdQueue.shift();
        processedMessageIds.delete(removed);
    }
}

function resetProcessedMessages() {
    processedMessageIds.clear();
    processedIdQueue = [];
}

// 更新重复消息徽章
function updateRepeatBadge(messageElement, count) {
    var bubble = messageElement.querySelector('.message-bubble');
    var badge = bubble.querySelector('.repeat-badge');
    if (!badge) {
        badge = document.createElement('div');
        badge.className = 'repeat-badge';
        bubble.appendChild(badge);
    }
    badge.textContent = 'x' + count;
    
    // 触发动画
    badge.style.animation = 'none';
    badge.offsetHeight; // 触发回流
    badge.style.animation = null;
}

// 更新玩家消息合并显示
function updateUserMessageMerge(messageElement, count, senders) {
    // 1. 更新徽章
    updateRepeatBadge(messageElement, count);
    
    // 2. 更新发送者列表
    var nameSpan = messageElement.querySelector('.message-name');
    if (!nameSpan) return;
    
    var container = nameSpan.querySelector('.sender-list-container');
    if (!container) {
        // 第一次合并，转换结构
        var firstName = nameSpan.innerHTML;
        nameSpan.innerHTML = '';
        
        container = document.createElement('div');
        container.className = 'sender-list-container';
        
        var listSpan = document.createElement('span');
        listSpan.className = 'sender-list';
        listSpan.innerHTML = firstName;
        
        container.appendChild(listSpan);
        nameSpan.appendChild(container);
    }
    
    var listSpan = container.querySelector('.sender-list');
    var fullText = senders.join(', ');
    listSpan.innerHTML = parseMinecraftText(fullText);
    
    // 3. 检查是否需要显示展开按钮
    // 如果文字被截断（溢出）或者发送者超过3个，显示按钮
    var isOverflowing = listSpan.scrollWidth > listSpan.clientWidth;
    var hasManySenders = senders.length > 3;
    
    var toggleBtn = container.querySelector('.sender-toggle-btn');
    if ((isOverflowing || hasManySenders) && !toggleBtn) {
        toggleBtn = document.createElement('div');
        toggleBtn.className = 'sender-toggle-btn';
        toggleBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>';

        toggleBtn.onclick = function(e) {            e.stopPropagation();
            var isExpanded = listSpan.classList.toggle('expanded');
            toggleBtn.classList.toggle('expanded');
            // 如果是在底部，展开可能需要滚动
            var wasAtBottom = checkIfAtBottom();
            if (wasAtBottom) {
                setTimeout(scrollToBottom, 50);
            }
        };
        
        container.appendChild(toggleBtn);
    }
}

// 重置合并状态
function resetMergingState() {
    lastMergeableMessageText = null;
    lastMergeableMessageElement = null;
    lastMergeableMessageCount = 1;
    lastMergeableMessageType = null;

    lastUserMessageText = null;
    lastUserMessageElement = null;
    lastUserMessageCount = 1;
    lastUserMessageSenders = [];

    // Reset folding group state
    foldingGroup = {
        messages: [],
        element: null,
        type: null,
        elements: null
    };
}

// Create a folding group wrapper element
function createFoldingGroupElement(messageType) {
    var groupItem = document.createElement('li');
    groupItem.className = 'folding-group';

    var groupBubble = document.createElement('div');
    groupBubble.className = 'message-bubble ' + messageType + ' folding-group-container';

    // History container (collapsed by default)
    var historyContainer = document.createElement('div');
    historyContainer.className = 'folding-history collapsed';

    // Latest message container
    var latestContainer = document.createElement('div');
    latestContainer.className = 'folding-latest';

    // NO toggle button - badge will be the toggle
    groupBubble.appendChild(historyContainer);
    groupBubble.appendChild(latestContainer);
    groupItem.appendChild(groupBubble);

    return {
        item: groupItem,
        bubble: groupBubble,
        history: historyContainer,
        latest: latestContainer
    };
}

// Toggle folding group expand/collapse
function toggleFoldingGroup(groupBubble) {
    var history = groupBubble.querySelector('.folding-history');

    var isCollapsed = history.classList.contains('collapsed');
    history.classList.toggle('collapsed');
    groupBubble.classList.toggle('expanded');

    // Scroll to bottom if was at bottom before expand
    if (isCollapsed) {
        var wasAtBottom = checkIfAtBottom();
        if (wasAtBottom) {
            setTimeout(scrollToBottom, 50);
        }
    }
}

// Create a flat history message item
function createHistoryMessageElement(messageData, messageType) {
    var container = document.createElement('div');
    container.className = 'folding-history-item';

    // Header row: name + time
    var headerRow = document.createElement('div');
    headerRow.className = 'folding-history-header';

    if (messageData.name) {
        var nameSpan = document.createElement('span');
        nameSpan.className = 'message-name';
        nameSpan.innerHTML = parseMinecraftText(messageData.name);
        headerRow.appendChild(nameSpan);
    }

    var timeSpan = document.createElement('span');
    timeSpan.className = 'folding-history-time';
    timeSpan.textContent = messageData.time;
    headerRow.appendChild(timeSpan);

    // Content row
    var textDiv = document.createElement('div');
    textDiv.className = 'folding-history-content';
    textDiv.innerHTML = parseMinecraftText(messageData.message);

    container.appendChild(headerRow);
    container.appendChild(textDiv);

    return container;
}

// Add a message to the folding group history (append = chronological order)
function addToFoldingHistory(groupElements, messageData, messageType) {
    var historyItem = createHistoryMessageElement(messageData, messageType);
    groupElements.history.appendChild(historyItem); // appendChild = oldest at top
}

// Update the latest message display in folding group
function updateFoldingLatest(groupElements, name, messageText, messageTime) {
    groupElements.latest.innerHTML = '';

    if (name) {
        var nameSpan = document.createElement('span');
        nameSpan.className = 'message-name';
        nameSpan.innerHTML = parseMinecraftText(name);
        groupElements.latest.appendChild(nameSpan);
    }

    var textDiv = document.createElement('div');
    textDiv.className = 'message-text';
    textDiv.innerHTML = parseMinecraftText(messageText);
    groupElements.latest.appendChild(textDiv);

    var timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = messageTime;
    groupElements.latest.appendChild(timeDiv);
}

// Update folding group count badge
function updateFoldingBadge(groupElements, count) {
    var badge = groupElements.bubble.querySelector('.folding-badge');
    if (!badge) {
        badge = document.createElement('div');
        badge.className = 'folding-badge';
        badge.onclick = function(e) {
            e.stopPropagation();
            toggleFoldingGroup(groupElements.bubble);
        };
        groupElements.bubble.appendChild(badge);
    }
    badge.textContent = '+' + count;

    // 触发动画（与相同消息徽章保持一致）
    badge.style.animation = 'none';
    badge.offsetHeight; // 触发回流
    badge.style.animation = null;
}

// 创建消息元素的通用函数
function createMessageElement(name, messageText, messageTime, duration, cacheHit, glossaryMatch, skipSrcLang, usage, original) {
    var newMessageItem = document.createElement("li");
    var bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'message-bubble';

    var messageType = '';

    if (!name) {
        messageType = 'system';
        bubbleDiv.classList.add(messageType);

        var textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        textDiv.innerHTML = parseMinecraftText(messageText);

        var timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = messageTime;

        // Store original text if available
        if (original) {
            textDiv.setAttribute('data-original', original);
            textDiv.setAttribute('data-showing', 'translation');
            bubbleDiv.setAttribute('data-has-original', 'true');
        }

        bubbleDiv.append(textDiv, timeDiv);
    } else {
        if (name === "[ERROR]") messageType = 'error';
        else if (name === "[INFO]") messageType = 'info';
        else messageType = 'user';

        bubbleDiv.classList.add(messageType);

        var nameSpan = document.createElement('span');
        nameSpan.className = 'message-name';
        nameSpan.innerHTML = parseMinecraftText(name);

        var textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        textDiv.innerHTML = parseMinecraftText(messageText);

        var timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = messageTime;

        // Store original text if available
        if (original) {
            textDiv.setAttribute('data-original', original);
            textDiv.setAttribute('data-showing', 'translation');
            bubbleDiv.setAttribute('data-has-original', 'true');
        }

        bubbleDiv.append(nameSpan, textDiv, timeDiv);
    }

    var hasBottomTags = (duration !== null && duration !== undefined && duration !== "" && duration !== 0) ||
                       (cacheHit === true) || (glossaryMatch === true) || (skipSrcLang === true) ||
                       (usage && (usage.total_tokens !== null && usage.total_tokens !== undefined && usage.total_tokens !== 0));

    if (hasBottomTags) {
        var bottomTagsContainer = document.createElement('div');
        bottomTagsContainer.className = 'bottom-tags-container';

        if (usage && (usage.total_tokens !== null && usage.total_tokens !== undefined && usage.total_tokens !== 0)) {
            var usageTag = document.createElement('div');
            usageTag.className = 'usage-tag';

            var usageIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            usageIcon.setAttribute('viewBox', '0 0 24 24');
            usageIcon.setAttribute('fill', 'none');
            usageIcon.setAttribute('stroke', 'currentColor');
            usageIcon.setAttribute('stroke-width', '2');
            usageIcon.setAttribute('stroke-linecap', 'round');
            usageIcon.setAttribute('stroke-linejoin', 'round');
            usageIcon.innerHTML = '<path d="M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0 -18 0" /><path d="M14.8 9a2 2 0 0 0 -1.8 -1h-2a2 2 0 0 0 0 4h2a2 2 0 0 1 0 4h-2a2 2 0 0 1 -1.8 -1" /><path d="M12 6v2" /><path d="M12 16v2" />';

            var usageTotal = document.createElement('span');
            usageTotal.className = 'usage-total';
            var totalTokens = usage.total_tokens || 0;
            usageTotal.textContent = totalTokens;

            var usageDetail = document.createElement('span');
            usageDetail.className = 'usage-detail';
            var promptTokens = usage.prompt_tokens || 0;
            var completionTokens = usage.completion_tokens || 0;
            usageDetail.textContent = `${promptTokens}+${completionTokens}=${totalTokens} tokens`;

            usageTag.appendChild(usageIcon);
            usageTag.appendChild(usageTotal);
            usageTag.appendChild(usageDetail);
            bottomTagsContainer.appendChild(usageTag);
        }

        if (duration !== null && duration !== undefined && duration !== "" && duration !== 0) {
            var durationTag = document.createElement('div');
            durationTag.className = 'duration-tag';

            var durationIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            durationIcon.setAttribute('viewBox', '0 0 24 24');
            durationIcon.setAttribute('fill', 'none');
            durationIcon.setAttribute('stroke', 'currentColor');
            durationIcon.setAttribute('stroke-width', '2.5');
            durationIcon.setAttribute('stroke-linecap', 'round');
            durationIcon.setAttribute('stroke-linejoin', 'round');
            durationIcon.innerHTML = '<circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline>';

            var durationText = document.createTextNode(duration.toString());

            durationTag.appendChild(durationIcon);
            durationTag.appendChild(durationText);
            bottomTagsContainer.appendChild(durationTag);
        }

        if (glossaryMatch === true) {
            var glossaryMatchTag = document.createElement('div');
            glossaryMatchTag.className = 'glossary-match-tag';

            var glossaryIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            glossaryIcon.setAttribute('viewBox', '0 0 24 24');
            glossaryIcon.setAttribute('fill', 'none');
            glossaryIcon.setAttribute('stroke', 'currentColor');
            glossaryIcon.setAttribute('stroke-width', '2.5');
            glossaryIcon.setAttribute('stroke-linecap', 'round');
            glossaryIcon.setAttribute('stroke-linejoin', 'round');
            glossaryIcon.innerHTML = '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>';

            var glossaryMatchText = document.createElement('span');
            glossaryMatchText.className = 'glossary-match-text';
            glossaryMatchText.textContent = 'glossary';

            glossaryMatchTag.appendChild(glossaryIcon);
            glossaryMatchTag.appendChild(glossaryMatchText);
            bottomTagsContainer.appendChild(glossaryMatchTag);
        }

        if (skipSrcLang === true) {
            var skipSrcLangTag = document.createElement('div');
            skipSrcLangTag.className = 'skip-src-lang-tag';

            var skipIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            skipIcon.setAttribute('viewBox', '0 0 24 24');
            skipIcon.setAttribute('fill', 'none');
            skipIcon.setAttribute('stroke', 'currentColor');
            skipIcon.setAttribute('stroke-width', '2.5');
            skipIcon.setAttribute('stroke-linecap', 'round');
            skipIcon.setAttribute('stroke-linejoin', 'round');
            skipIcon.innerHTML = '<circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line>';

            var skipSrcLangText = document.createElement('span');
            skipSrcLangText.className = 'skip-src-lang-text';
            skipSrcLangText.textContent = 'skipped';

            skipSrcLangTag.appendChild(skipIcon);
            skipSrcLangTag.appendChild(skipSrcLangText);
            bottomTagsContainer.appendChild(skipSrcLangTag);
        }

        if (cacheHit === true) {
            var cacheHitTag = document.createElement('div');
            cacheHitTag.className = 'cache-hit-tag';

            var cacheIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            cacheIcon.setAttribute('viewBox', '0 0 24 24');
            cacheIcon.setAttribute('fill', 'none');
            cacheIcon.setAttribute('stroke', 'currentColor');
            cacheIcon.setAttribute('stroke-width', '2.5');
            cacheIcon.setAttribute('stroke-linecap', 'round');
            cacheIcon.setAttribute('stroke-linejoin', 'round');
            cacheIcon.innerHTML = '<path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"></path>';

            var cacheHitText = document.createElement('span');
            cacheHitText.className = 'cache-hit-text';
            cacheHitText.textContent = 'cache hit';

            cacheHitTag.appendChild(cacheIcon);
            cacheHitTag.appendChild(cacheHitText);
            bottomTagsContainer.appendChild(cacheHitTag);
        }

        bubbleDiv.appendChild(bottomTagsContainer);
    }

    if (messageType && messageFilters.hasOwnProperty(messageType) && !messageFilters[messageType]) {
        bubbleDiv.classList.add('hidden');
    }

    newMessageItem.appendChild(bubbleDiv);
    return {
        element: newMessageItem,
        type: messageType
    };
}

function handleMessageScroll(wasAtBottom) {
    updateScrollButtonState();

    var userRecentlyScrolled = (Date.now() - lastScrollTime) < 300;

    if (wasAtBottom && !userRecentlyScrolled && pendingMessages === 0) {
        requestAnimationFrame(function() {
            scrollToBottom();
        });
    } else if (!wasAtBottom) {
        updateScrollButtonState();
    }
}

function cleanupEventSource() {
    if (window.eventSource) {
        window.eventSource.close();
        window.eventSource = null;
    }
}

function scheduleReconnect(immediate) {
    cleanupEventSource();

    if (reconnectTimer) return;

    var delay = immediate ? 0 : reconnectDelay;
    reconnectTimer = setTimeout(function() {
        reconnectTimer = null;
        initializeEventSource();
    }, delay);

    if (immediate) {
        reconnectDelay = 2000;
    } else {
        reconnectDelay = Math.min(reconnectDelay * 1.5, 15000);
    }
}

function startHeartbeatMonitor() {
    if (heartbeatMonitorInterval) return;
    heartbeatMonitorInterval = setInterval(function() {
        var now = Date.now();
        if (!window.eventSource) return;
        if (now - lastHeartbeat > 20000) {
            scheduleReconnect(true);
        }
    }, 5000);
}

function ensureEventSourceActive(forceReconnect) {
    if (forceReconnect) {
        scheduleReconnect(true);
        return;
    }
    if (!window.eventSource) {
        initializeEventSource();
    } else if (window.eventSource.readyState === EventSource.CLOSED) {
        scheduleReconnect(true);
    }
}

function handleServerClear() {
    obfuscatedElements.forEach(function(element) {
        removeObfuscatedElement(element);
    });
    obfuscatedElements.clear();
    resetProcessedMessages();
    resetMergingState();
    lastEventId = null;
    messageList.innerHTML = '';
    updateScrollButtonState();
}

function initializeEventSource() {
    cleanupEventSource();

    var streamUrl = "/stream";
    if (lastEventId !== null && lastEventId !== undefined) {
        streamUrl += (streamUrl.indexOf('?') === -1 ? '?' : '&') + 'last_event_id=' + encodeURIComponent(lastEventId);
    }

    try {
        window.eventSource = new EventSource(streamUrl);
    } catch (error) {
        scheduleReconnect();
        return;
    }

    window.eventSource.onopen = function() {
        lastHeartbeat = Date.now();
        reconnectDelay = 2000;
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
    };

    window.eventSource.onmessage = function(event) {
        lastHeartbeat = Date.now();
        var wasAtBottom = checkIfAtBottom();
        pendingMessages++;

        var jsonData;
        try {
            jsonData = JSON.parse(event.data);
        } catch (parseError) {
            pendingMessages--;
            return;
        }

        if (jsonData.clear) {
            handleServerClear();
            pendingMessages--;
            return;
        }

        if (event.lastEventId) {
            var idFromEvent = parseInt(event.lastEventId, 10);
            if (!isNaN(idFromEvent)) {
                lastEventId = idFromEvent;
            }
        }

        var messageId = null;
        if (typeof jsonData.id === "number") {
            messageId = jsonData.id;
        } else if (jsonData.id) {
            var parsed = parseInt(jsonData.id, 10);
            if (!isNaN(parsed)) {
                messageId = parsed;
            }
        }

        if (messageId !== null) {
            if (processedMessageIds.has(messageId)) {
                pendingMessages--;
                return;
            }
            trackProcessedMessage(messageId);
            lastEventId = messageId;
        }

        var name = jsonData.name;
        var messageText = jsonData.message;
        var messageTime = jsonData.time;
        var duration = jsonData.duration;
        var cacheHit = jsonData.cache_hit;
        var glossaryMatch = jsonData.glossary_match;
        var skipSrcLang = jsonData.skip_src_lang;
        var usage = jsonData.usage;
        var isPending = jsonData.pending === true;
        var original = jsonData.original;

        if (name === "[INFO]" && isTranslating) {
            setTimeout(resetTranslationUI, 500);
        }

        // Pending 占位消息：直接渲染加载骨架
        if (isPending) {
            var pendingItem = document.createElement('li');
            pendingItem.className = 'message-item message-pending';
            pendingItem.setAttribute('data-slot-id', messageId);

            var pendingBubble = document.createElement('div');
            var pendingType = !name ? 'system' : (name === "[ERROR]" ? 'error' : (name === "[INFO]" ? 'info' : 'user'));
            pendingBubble.className = 'message-bubble ' + pendingType + ' pending-bubble';

            // 应用过滤器：如果该类型被过滤掉，则隐藏 pending 气泡
            if (messageFilters.hasOwnProperty(pendingType) && !messageFilters[pendingType]) {
                pendingBubble.classList.add('hidden');
            }

            if (name) {
                var pendingName = document.createElement('div');
                pendingName.className = 'message-name';
                pendingName.innerHTML = parseMinecraftText(name);
                pendingBubble.appendChild(pendingName);
            }

            var pendingDots = document.createElement('div');
            pendingDots.className = 'pending-dots';
            pendingDots.innerHTML = '<span></span><span></span><span></span>';
            pendingBubble.appendChild(pendingDots);

            pendingItem.appendChild(pendingBubble);
            messageList.appendChild(pendingItem);
            pendingMessages--;
            handleMessageScroll(wasAtBottom);
            return;
        }

        // 检查是否为可合并的消息类型（System, Error, Info）
        var currentType = !name ? 'system' : (name === "[ERROR]" ? 'error' : (name === "[INFO]" ? 'info' : 'user'));

        // 玩家消息合并逻辑
        if (currentType === 'user') {
            if (lastUserMessageText === messageText && lastUserMessageElement) {
                lastUserMessageCount++;
                if (!lastUserMessageSenders.includes(name)) {
                    lastUserMessageSenders.push(name);
                }
                updateUserMessageMerge(lastUserMessageElement, lastUserMessageCount, lastUserMessageSenders);
                pendingMessages--;
                handleMessageScroll(wasAtBottom);
                return;
            }
            // 新的玩家消息，重置系统消息合并状态
            lastMergeableMessageText = null;
            lastMergeableMessageElement = null;
        } else {
            // 系统类消息合并逻辑
            if (currentType === lastMergeableMessageType &&
                lastMergeableMessageText === messageText && lastMergeableMessageElement) {
                lastMergeableMessageCount++;
                updateRepeatBadge(lastMergeableMessageElement, lastMergeableMessageCount);
                pendingMessages--;
                handleMessageScroll(wasAtBottom);
                return;
            }
            // 新的系统消息，重置玩家消息合并状态
            lastUserMessageText = null;
            lastUserMessageElement = null;
        }

        // Check for folding group similarity (after exact match checks fail)
        if (foldingGroup.element && foldingGroup.type === currentType) {
            var prevMessage = foldingGroup.messages[foldingGroup.messages.length - 1];

            if (shouldFoldMessages(currentType, foldingGroup.type, messageText, prevMessage.message)) {
                // If this is the first fold (elements not created yet), convert single message to group
                if (!foldingGroup.elements) {
                    // Create folding group wrapper
                    foldingGroup.elements = createFoldingGroupElement(currentType);

                    // Copy filter state from original element
                    var originalBubble = foldingGroup.element.querySelector('.message-bubble');
                    if (originalBubble && originalBubble.classList.contains('hidden')) {
                        foldingGroup.elements.bubble.classList.add('hidden');
                    }

                    // Add first message to history
                    addToFoldingHistory(foldingGroup.elements, prevMessage, currentType);

                    // Set up latest with second message (will be updated below)
                    updateFoldingLatest(foldingGroup.elements, name, messageText, messageTime);

                    // Replace the single message element with the folding group
                    messageList.replaceChild(foldingGroup.elements.item, foldingGroup.element);

                    // Update badge
                    updateFoldingBadge(foldingGroup.elements, 1);

                    // Update the element reference
                    foldingGroup.element = foldingGroup.elements.item;
                } else {
                    // Add to existing folding group
                    // Move current latest to history
                    addToFoldingHistory(foldingGroup.elements, prevMessage, currentType);

                    // Update latest display
                    updateFoldingLatest(foldingGroup.elements, name, messageText, messageTime);
                    updateFoldingBadge(foldingGroup.elements, foldingGroup.messages.length);
                }

                // Store the new message
                foldingGroup.messages.push({
                    name: name,
                    message: messageText,
                    time: messageTime,
                    duration: duration,
                    cacheHit: cacheHit,
                    glossaryMatch: glossaryMatch,
                    skipSrcLang: skipSrcLang,
                    usage: usage,
                    messageText: parseMinecraftText(messageText),
                    original: original
                });

                pendingMessages--;
                handleMessageScroll(wasAtBottom);
                return;
            }
        }

        // If type changed from previous folding group, reset it
        if (foldingGroup.type && foldingGroup.type !== currentType) {
            foldingGroup = {
                messages: [],
                element: null,
                type: null,
                elements: null
            };
        }

        var messageData = createMessageElement(name, messageText, messageTime, duration, cacheHit, glossaryMatch, skipSrcLang, usage, original);
        messageList.appendChild(messageData.element);

        // Start tracking for potential folding group
        foldingGroup = {
            messages: [{
                name: name,
                message: messageText,
                time: messageTime,
                duration: duration,
                cacheHit: cacheHit,
                glossaryMatch: glossaryMatch,
                skipSrcLang: skipSrcLang,
                usage: usage,
                messageText: parseMinecraftText(messageText),
                original: original
            }],
            element: messageData.element,
            type: currentType,
            elements: null  // Will be created when folding actually starts
        };

        // 更新合并追踪状态
        if (currentType === 'user') {
            lastUserMessageText = messageText;
            lastUserMessageElement = messageData.element;
            lastUserMessageCount = 1;
            lastUserMessageSenders = [name];
        } else {
            lastMergeableMessageType = currentType;
            lastMergeableMessageText = messageText;
            lastMergeableMessageElement = messageData.element;
            lastMergeableMessageCount = 1;
        }

        pendingMessages--;
        handleMessageScroll(wasAtBottom);
        updateClearButtonVisibility();
    };

    window.eventSource.onerror = function() {
        if (!window.eventSource) {
            return;
        }
        if (window.eventSource.readyState === EventSource.CLOSED) {
            scheduleReconnect();
        }
    };

    window.eventSource.addEventListener('heartbeat', function() {
        lastHeartbeat = Date.now();
    });

    // update 事件：slot 填充完成，找到占位元素并原地替换
    window.eventSource.addEventListener('update', function(event) {
        lastHeartbeat = Date.now();

        var jsonData;
        try {
            jsonData = JSON.parse(event.data);
        } catch (e) {
            return;
        }

        var slotId = jsonData.id;
        if (!slotId) return;

        // 找到占位元素
        var pendingEl = messageList.querySelector('[data-slot-id="' + slotId + '"]');
        if (!pendingEl) {
            // 占位元素已被清除（如清空操作），忽略
            return;
        }

        var name = jsonData.name || '';
        var messageText = jsonData.message || '';
        var messageTime = jsonData.time;
        var duration = jsonData.duration;
        var cacheHit = jsonData.cache_hit;
        var glossaryMatch = jsonData.glossary_match;
        var skipSrcLang = jsonData.skip_src_lang;
        var usage = jsonData.usage;
        var original = jsonData.original;
        if (!messageText) {
            // 译文为空（被过滤等），移除占位元素
            pendingEl.style.transition = 'opacity 0.2s';
            pendingEl.style.opacity = '0';
            setTimeout(function() {
                if (pendingEl.parentNode) pendingEl.parentNode.removeChild(pendingEl);
            }, 200);
            return;
        }

        // 创建真实消息元素
        var messageData = createMessageElement(
            name || null,
            messageText,
            messageTime,
            duration,
            cacheHit,
            glossaryMatch,
            skipSrcLang,
            usage,
            original
        );

        // 将占位元素替换为真实消息元素（位置保持不变）
        var wasAtBottom = checkIfAtBottom();
        pendingEl.classList.add('pending-resolve');
        setTimeout(function() {
            if (pendingEl.parentNode) {
                pendingEl.parentNode.replaceChild(messageData.element, pendingEl);
            }
            // 更新合并追踪状态（update 不参与合并逻辑，仅更新最新追踪）
            var currentType = !name ? 'system' : (name === "[ERROR]" ? 'error' : (name === "[INFO]" ? 'info' : 'user'));
            if (currentType === 'user') {
                lastUserMessageText = messageText;
                lastUserMessageElement = messageData.element;
                lastUserMessageCount = 1;
                lastUserMessageSenders = [name];
            } else {
                lastMergeableMessageType = currentType;
                lastMergeableMessageText = messageText;
                lastMergeableMessageElement = messageData.element;
                lastMergeableMessageCount = 1;
            }
            handleMessageScroll(wasAtBottom);
            updateClearButtonVisibility();
        }, 60);
    });

    startHeartbeatMonitor();
}

function checkIfAtBottom() {
    var tolerance = 20;
    return (window.innerHeight + window.pageYOffset) >= (document.body.scrollHeight - tolerance);
}

function needsScrolling() {
    return document.body.scrollHeight > window.innerHeight;
}

function updateScrollButtonState() {
    isAtBottom = checkIfAtBottom();

    if (!needsScrolling() || isAtBottom) {
        scrollBottomBtn.style.display = "none";
    } else {
        scrollBottomBtn.style.display = "flex";
    }
}

function scrollToBottom() {
    window.scrollTo({
        top: document.body.scrollHeight,
        behavior: 'smooth'
    });
    setTimeout(updateScrollButtonState, 500);
}

window.addEventListener('scroll', function() {
    lastScrollTime = Date.now();
    updateScrollButtonState();
});

window.addEventListener('resize', function() {
    updateScrollButtonState();
});

document.addEventListener('visibilitychange', function() {
    if (!document.hidden) {
        ensureEventSourceActive(false);
    }
});

window.addEventListener('focus', function() {
    ensureEventSourceActive(false);
});

window.addEventListener('pageshow', function(event) {
    if (event.persisted) {
        ensureEventSourceActive(true);
    }
});

scrollBottomBtn.addEventListener('click', function() {
    scrollToBottom();
});

document.getElementById('fab-clear').addEventListener('click', function() {
    obfuscatedElements.forEach(function(element) {
        removeObfuscatedElement(element);
    });
    obfuscatedElements.clear();
    resetProcessedMessages();
    resetMergingState();
    lastEventId = null;

    fetch('/clear-messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            document.getElementById('message-list').innerHTML = '';
            initializeEventSource();
            updateScrollButtonState();
        }
    })
    .catch(() => {});
});

document.querySelectorAll('.filter-option').forEach(function(filter) {
    filter.addEventListener('click', function() {
        var type = this.getAttribute('data-type');

        messageFilters[type] = !messageFilters[type];
        this.classList.toggle('active');

        if (messageFilters[type]) {
            this.classList.add(type);
        } else {
            this.classList.remove(type);
        }

        applyFilters();
    });
});

function applyFilters() {
    document.querySelectorAll('.message-bubble').forEach(function(bubble) {
        var messageType = '';

        if (bubble.classList.contains('user')) {
            messageType = 'user';
        } else if (bubble.classList.contains('system')) {
            messageType = 'system';
        } else if (bubble.classList.contains('error')) {
            messageType = 'error';
        } else if (bubble.classList.contains('info')) {
            messageType = 'info';
        }

        if (messageType && messageFilters.hasOwnProperty(messageType)) {
            if (messageFilters[messageType]) {
                bubble.classList.remove('hidden');
            } else {
                bubble.classList.add('hidden');
            }
        } else if (!messageType) {
            // 无法识别类型的气泡（如 folding-group-container），保持可见
            bubble.classList.remove('hidden');
        }
    });

    setTimeout(updateScrollButtonState, 50);
}

var messageInput = document.getElementById("message-input");
var sendButton = document.getElementById("send-button");
var translationIndicator = document.querySelector(".translation-indicator");
var isTranslating = false;
var isRageMode = false;
var previousThemeHref = '';

function sendMessage() {
    var message = messageInput.value.trim();
    if (message === "" || isTranslating) return;

    isTranslating = true;
    messageInput.disabled = true;
    sendButton.disabled = true;
    translationIndicator.classList.add("active");

    if (translationTimeoutId) {
        clearTimeout(translationTimeoutId);
    }
    translationTimeoutId = setTimeout(function() {
        if (isTranslating) {
            resetTranslationUI();
        }
    }, 15000);

    fetch('/send-message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message, rage_mode: isRageMode })
    })
    .then(response => response.json())
    .then(data => {
        console.log("收到翻译:", data.translated);
    })
    .catch(() => {
        resetTranslationUI();
    });

    messageInput.value = "";
}

function resetTranslationUI() {
    if (translationTimeoutId) {
        clearTimeout(translationTimeoutId);
        translationTimeoutId = null;
    }
    isTranslating = false;
    messageInput.disabled = false;
    sendButton.disabled = false;
    translationIndicator.classList.remove("active");
}

sendButton.addEventListener("click", sendMessage);
messageInput.addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        e.preventDefault();
        sendMessage();
    }
});

window.addEventListener('beforeunload', function() {
    stopObfuscatedEffect();
});

initializeEventSource();

document.addEventListener('DOMContentLoaded', (event) => {
    document.querySelectorAll('.filter-option').forEach(function(filter) {
        var type = filter.getAttribute('data-type');
        if (messageFilters[type]) {
            filter.classList.add('active');
            filter.classList.add(type);
        } else {
            filter.classList.remove('active');
            filter.classList.remove(type);
        }
    });
    applyFilters();
});

// FAB Speed Dial 菜单功能
document.addEventListener('DOMContentLoaded', (event) => {
    // 初始化过滤器
    document.querySelectorAll('.filter-option').forEach(function(filter) {
        var type = filter.getAttribute('data-type');
        if (messageFilters[type]) {
            filter.classList.add('active');
            filter.classList.add(type);
        } else {
            filter.classList.remove('active');
            filter.classList.remove(type);
        }
    });
    applyFilters();

    // FAB 菜单相关元素
    const fabMain = document.getElementById('fab-main');
    const fabContainer = document.querySelector('.fab-container');
    const fabDarkMode = document.getElementById('fab-dark-mode');
    const fabTheme = document.getElementById('fab-theme');
    const fabRageMode = document.getElementById('fab-rage-mode');
    const fabSubmenu = document.getElementById('fab-submenu');

    // Rage Mode 切换功能
    if (fabRageMode) {
        fabRageMode.addEventListener('click', function() {
            isRageMode = !isRageMode;
            const themeLink = document.getElementById('theme-stylesheet');
            
            if (isRageMode) {
                previousThemeHref = themeLink.getAttribute('href');
                themeLink.setAttribute('href', '/static/css/rage_mode.css');
            } else {
                if (previousThemeHref) {
                    themeLink.setAttribute('href', previousThemeHref);
                }
            }
            
            // 关闭菜单
            fabContainer.classList.remove('open');
            if (fabSubmenu) fabSubmenu.classList.remove('open');
        });
    }

    // 深色模式切换功能
    const storedTheme = localStorage.getItem('theme');
    if (storedTheme) {
        document.documentElement.setAttribute('data-theme', storedTheme);
    }
    updateDarkModeIcon();

    function updateDarkModeIcon() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        if (currentTheme === 'dark') {
            // 深色模式下显示更现代的太阳图标 (Lucide style)
            fabDarkMode.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path></svg>';
        } else {
            // 浅色模式下显示精美月亮图标
            fabDarkMode.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path></svg>';
        }
    }

    fabDarkMode.addEventListener('click', function() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        if (currentTheme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'light');
            localStorage.setItem('theme', 'light');
        } else {
            document.documentElement.setAttribute('data-theme', 'dark');
            localStorage.setItem('theme', 'dark');
        }
        updateDarkModeIcon();
        // 关闭菜单
        fabContainer.classList.remove('open');
        // 同时关闭二级菜单
        if (fabSubmenu) fabSubmenu.classList.remove('open');
    });

    // 主题二级菜单展开/收起
    fabTheme.addEventListener('click', function(e) {
        e.stopPropagation();
        if (!fabSubmenu) return;
        // 切换二级菜单展开状态；若已展开则仅关闭二级，一级保持
        if (fabSubmenu.classList.contains('open')) {
            fabSubmenu.classList.remove('open');
        } else {
            // 打开二级菜单
            fabSubmenu.classList.add('open');
        }
    });

    // 绑定二级菜单主题项点击事件
    if (fabSubmenu) {
        fabSubmenu.querySelectorAll('.fab-subitem').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                const theme = this.getAttribute('data-theme');
                if (!theme) return;
                // 应用主题：通过更新 URL 参数并刷新
                const url = new URL(window.location.href);
                url.searchParams.set('theme', theme);

                // 关闭所有菜单（UI 上立即反馈）
                fabSubmenu.classList.remove('open');
                fabContainer.classList.remove('open');

                window.location.href = url.toString();
            });
        });
    }

    // FAB 主按钮点击事件
    fabMain.addEventListener('click', function() {
        const willOpen = !fabContainer.classList.contains('open');
        fabContainer.classList.toggle('open');
        if (!willOpen) {
            // 如果此次点击是关闭一级菜单，则也关闭二级菜单
            if (fabSubmenu) fabSubmenu.classList.remove('open');
        }
    });

    // 点击页面其他地方关闭菜单
    document.addEventListener('click', function(e) {
        if (!fabContainer.contains(e.target)) {
            if (fabContainer.classList.contains('open')) {
                fabContainer.classList.remove('open');
            }
            if (fabSubmenu && fabSubmenu.classList.contains('open')) {
                fabSubmenu.classList.remove('open');
            }
        }
    });
});

// ============================================================
// Long-Press Context Menu — Show Original / Show Translation
// ============================================================
var longPressTimer = null;
var longPressTarget = null;
var longPressStartX = 0;
var longPressStartY = 0;
var contextMenuEl = null;
var LONG_PRESS_DURATION = 500;
var LONG_PRESS_MOVE_THRESHOLD = 10;

// I18N fallback
var I18N = window.I18N || { showOriginal: 'Show Original', showTranslation: 'Show Translation' };

// --- Context Menu DOM (lazy-create once) ---
function getContextMenu() {
    if (contextMenuEl) return contextMenuEl;
    contextMenuEl = document.createElement('div');
    contextMenuEl.id = 'context-menu';
    contextMenuEl.style.display = 'none';
    document.body.appendChild(contextMenuEl);
    return contextMenuEl;
}

// --- Show the context menu near the press point ---
function showContextMenu(bubbleElement, clientX, clientY) {
    var menu = getContextMenu();
    var showing = bubbleElement.getAttribute('data-showing') || 'translation';

    var svgIcon, labelText;
    if (showing === 'translation') {
        // Show Original — document icon
        svgIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>';
        labelText = I18N.showOriginal;
    } else {
        // Show Translation — globe icon
        svgIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>';
        labelText = I18N.showTranslation;
    }

    var copyIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
    var copyLabelText = I18N.copy || '复制';
    
    var readIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>';
    var readLabelText = I18N.readAloud || '朗读';

    menu.innerHTML = 
        '<div class="context-menu-item" id="menu-toggle-translation">' + svgIcon + '<span>' + labelText + '</span></div>' +
        '<div class="context-menu-item" id="menu-copy">' + copyIcon + '<span>' + copyLabelText + '</span></div>' +
        '<div class="context-menu-item" id="menu-read-aloud">' + readIcon + '<span>' + readLabelText + '</span></div>';

    // Position: prefer below the press point, flip if too close to edge
    var menuWidth = 200; // approximate
    var menuHeight = 140; // approximate for 3 items

    var left = clientX;
    var top = clientY + 8;

    if (left + menuWidth > window.innerWidth - 12) {
        left = window.innerWidth - menuWidth - 12;
    }
    if (left < 12) left = 12;

    if (top + menuHeight > window.innerHeight - 12) {
        top = clientY - menuHeight - 8;
    }
    if (top < 12) top = 12;

    menu.style.left = left + 'px';
    menu.style.top = top + 'px';
    menu.style.transformOrigin = (clientX - left) + 'px ' + (clientY - top) + 'px';
    menu.style.display = 'block';
    // Re-trigger animation
    menu.style.animation = 'none';
    menu.offsetHeight;
    menu.style.animation = 'contextMenuIn 0.2s cubic-bezier(0.16, 1, 0.3, 1)';

    // Click handlers
    var textDiv = bubbleElement.querySelector('.message-text');
    var textContent = textDiv ? textDiv.textContent : '';

    menu.querySelector('#menu-toggle-translation').onclick = function(e) {
        e.stopPropagation();
        toggleMessageText(bubbleElement);
        dismissContextMenu();
    };

    menu.querySelector('#menu-copy').onclick = function(e) {
        e.stopPropagation();
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(textContent);
        } else {
            // fallback
            var textArea = document.createElement("textarea");
            textArea.value = textContent;
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try { document.execCommand('copy'); } catch (err) {}
            document.body.removeChild(textArea);
        }
        dismissContextMenu();
    };

    menu.querySelector('#menu-read-aloud').onclick = function(e) {
        e.stopPropagation();
        fetch('/read-aloud', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text: textContent })
        }).catch(function(err) {
            console.error('Failed to trigger read aloud:', err);
        });
        dismissContextMenu();
    };
}

// --- Toggle message text between original and translation ---
function toggleMessageText(bubbleElement) {
    // Find the .message-text div inside
    var textDiv = bubbleElement.querySelector('.message-text');
    if (!textDiv) return;

    var showing = textDiv.getAttribute('data-showing') || 'translation';
    var original = textDiv.getAttribute('data-original');
    if (!original) return;

    var currentHtml = textDiv.innerHTML;

    if (showing === 'translation') {
        // Save current (translated) content before swapping
        textDiv.setAttribute('data-translation-html', currentHtml);
        // Switch to original
        textDiv.innerHTML = parseMinecraftText(original);
        textDiv.setAttribute('data-showing', 'original');
        bubbleElement.setAttribute('data-showing', 'original');
    } else {
        // Restore translation
        var savedTranslation = textDiv.getAttribute('data-translation-html');
        if (savedTranslation) {
            textDiv.innerHTML = savedTranslation;
        }
        textDiv.setAttribute('data-showing', 'translation');
        bubbleElement.setAttribute('data-showing', 'translation');
    }

    // Animate the text swap
    textDiv.classList.add('swapping');
    setTimeout(function() {
        textDiv.classList.remove('swapping');
    }, 260);
}

// --- Dismiss ---
function dismissContextMenu() {
    if (!contextMenuEl || contextMenuEl.style.display === 'none') return;

    contextMenuEl.classList.add('dismissing');
    setTimeout(function() {
        contextMenuEl.style.display = 'none';
        contextMenuEl.classList.remove('dismissing');
    }, 140);
}

// --- Long-press handlers ---
function onPressStart(e, bubble) {
    // Only respond if bubble has original text
    if (!bubble.getAttribute('data-has-original')) return;

    // Don't show menu on pending bubbles
    if (bubble.classList.contains('pending-bubble')) return;

    longPressTarget = bubble;
    longPressStartX = e.type.indexOf('touch') === 0 ? e.touches[0].clientX : e.clientX;
    longPressStartY = e.type.indexOf('touch') === 0 ? e.touches[0].clientY : e.clientY;

    dismissContextMenu();

    longPressTimer = setTimeout(function() {
        bubble.classList.add('long-pressing');
        showContextMenu(bubble, longPressStartX, longPressStartY);
        longPressTimer = null;
    }, LONG_PRESS_DURATION);
}

function onPressMove(e) {
    if (!longPressTimer) return;
    var clientX = e.type.indexOf('touch') === 0 ? e.touches[0].clientX : e.clientX;
    var clientY = e.type.indexOf('touch') === 0 ? e.touches[0].clientY : e.clientY;
    var dx = clientX - longPressStartX;
    var dy = clientY - longPressStartY;
    if (Math.abs(dx) > LONG_PRESS_MOVE_THRESHOLD || Math.abs(dy) > LONG_PRESS_MOVE_THRESHOLD) {
        cancelLongPress();
    }
}

function onPressEnd(e) {
    cancelLongPress();
}

function cancelLongPress() {
    if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
    }
    if (longPressTarget) {
        longPressTarget.classList.remove('long-pressing');
        longPressTarget = null;
    }
}

// --- Delegate long-press events on the message list ---
var messageListEl = document.getElementById('message-list');
if (messageListEl) {
    messageListEl.addEventListener('mousedown', function(e) {
        var bubble = e.target.closest('.message-bubble');
        if (!bubble) return;
        onPressStart(e, bubble);
    });

    messageListEl.addEventListener('mousemove', function(e) {
        if (longPressTimer) onPressMove(e);
    });

    messageListEl.addEventListener('mouseup', onPressEnd);
    messageListEl.addEventListener('mouseleave', onPressEnd);

    messageListEl.addEventListener('touchstart', function(e) {
        var bubble = e.target.closest('.message-bubble');
        if (!bubble) return;
        onPressStart(e, bubble);
    }, { passive: true });

    messageListEl.addEventListener('touchmove', function(e) {
        if (longPressTimer) onPressMove(e);
    }, { passive: true });

    messageListEl.addEventListener('touchend', onPressEnd);
    messageListEl.addEventListener('touchcancel', onPressEnd);
}

// --- Global dismiss ---
document.addEventListener('click', function(e) {
    if (contextMenuEl && contextMenuEl.style.display !== 'none') {
        if (!contextMenuEl.contains(e.target)) {
            dismissContextMenu();
        }
    }
});

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        dismissContextMenu();
    }
});

window.addEventListener('scroll', function() {
    if (contextMenuEl && contextMenuEl.style.display !== 'none') {
        dismissContextMenu();
    }
}, { passive: true });

window.addEventListener('resize', function() {
    dismissContextMenu();
});
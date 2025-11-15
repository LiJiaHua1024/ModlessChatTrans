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

// 创建消息元素的通用函数
function createMessageElement(name, messageText, messageTime, duration, cacheHit, glossaryMatch, skipSrcLang, usage) {
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

            var lightningIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            lightningIcon.setAttribute('viewBox', '0 0 24 24');
            lightningIcon.setAttribute('fill', 'currentColor');
            lightningIcon.innerHTML = '<path d="M13 0L6 12h5l-1 12 7-12h-5l1-12z"/>';

            var durationText = document.createTextNode(duration.toString());

            durationTag.appendChild(lightningIcon);
            durationTag.appendChild(durationText);
            bottomTagsContainer.appendChild(durationTag);
        }

        if (glossaryMatch === true) {
            var glossaryMatchTag = document.createElement('div');
            glossaryMatchTag.className = 'glossary-match-tag';

            var glossaryIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            glossaryIcon.setAttribute('viewBox', '0 0 24 24');
            glossaryIcon.setAttribute('fill', 'currentColor');
            glossaryIcon.innerHTML = '<path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM5 17V7h14v10H5z"/><path d="M7 9h10v2H7z"/><path d="M7 13h6v2H7z"/>';

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
            skipIcon.setAttribute('fill', 'currentColor');
            skipIcon.innerHTML = '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zM4 12c0-4.42 3.58-8 8-8 1.85 0 3.55.63 4.9 1.69L5.69 16.9C4.63 15.55 4 13.85 4 12zm8 8c-1.85 0-3.55-.63-4.9-1.69L18.31 7.1C19.37 8.45 20 10.15 20 12c0 4.42-3.58 8-8 8z"/>';

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
            cacheIcon.setAttribute('fill', 'currentColor');
            cacheIcon.innerHTML = '<path d="M6 2c-1.1 0-2 .9-2 2v5H2v6h2v5c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-5h2V9h-2V4c0-1.1-.9-2-2-2H6z"/><circle cx="8" cy="6" r="1"/><circle cx="12" cy="6" r="1"/><circle cx="16" cy="6" r="1"/>';

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

        if (name === "[INFO]" && isTranslating) {
            setTimeout(resetTranslationUI, 500);
        }

        var messageData = createMessageElement(name, messageText, messageTime, duration, cacheHit, glossaryMatch, skipSrcLang, usage);
        messageList.appendChild(messageData.element);

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
        } else {
            bubble.classList.remove('hidden');
        }
    });

    setTimeout(updateScrollButtonState, 50);
}

var messageInput = document.getElementById("message-input");
var sendButton = document.getElementById("send-button");
var translationIndicator = document.querySelector(".translation-indicator");
var isTranslating = false;

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
        body: JSON.stringify({ message: message })
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
    const fabSubmenu = document.getElementById('fab-submenu');

    // 深色模式切换功能
    const storedTheme = localStorage.getItem('theme');
    if (storedTheme) {
        document.documentElement.setAttribute('data-theme', storedTheme);
    }
    updateDarkModeIcon();

    function updateDarkModeIcon() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        if (currentTheme === 'dark') {
            // 深色模式下显示实心太阳图标
            fabDarkMode.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41m11.32-11.32l1.41-1.41"/></svg>';
        } else {
            // 浅色模式下显示空心太阳图标（更简洁）
            fabDarkMode.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41m11.32-11.32l1.41-1.41"/></svg>';
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
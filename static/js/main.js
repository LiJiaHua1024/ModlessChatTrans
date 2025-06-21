// 将事件处理程序和初始化代码提取为可重用函数
var messageList = document.getElementById("message-list");
var scrollBottomBtn = document.getElementById("scroll-bottom-btn");
var isUserScrolling = false;
var isAtBottom = true;
var lastScrollTime = Date.now();
var pendingMessages = 0;

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
                // 颜色代码：移除之前的颜色类，添加新颜色类
                currentClasses = currentClasses.filter(function(cls) {
                    return !cls.startsWith('mc-color-');
                });
                currentClasses.push(colorCodes[code]);
            } else if (formatCodes[code]) {
                // 格式代码：添加格式类（如果不存在）
                if (currentClasses.indexOf(formatCodes[code]) === -1) {
                    currentClasses.push(formatCodes[code]);
                }
            }
        }
    }

    return result;
}

// 创建消息元素的通用函数
function createMessageElement(name, messageText, messageTime, duration, cacheHit, glossaryMatch, skipSrcLang, usage) {
    var newMessageItem = document.createElement("li");
    var bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'message-bubble';

    var messageType = '';

    // 确定消息类型并设置相应的类
    if (!name) {
        // 系统消息
        messageType = 'system';
        bubbleDiv.classList.add(messageType);

        var textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        textDiv.innerHTML = parseMinecraftText(messageText); // 使用innerHTML以支持格式化

        var timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = messageTime;

        bubbleDiv.append(textDiv, timeDiv);
    } else {
        // 确定消息类型
        if (name === "[ERROR]") messageType = 'error';
        else if (name === "[INFO]") messageType = 'info';
        else messageType = 'user';

        bubbleDiv.classList.add(messageType);

        // 创建消息内容元素
        var nameSpan = document.createElement('span');
        nameSpan.className = 'message-name';
        nameSpan.innerHTML = parseMinecraftText(name); // 用户名也支持格式化

        var textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        textDiv.innerHTML = parseMinecraftText(messageText); // 使用innerHTML以支持格式化

        var timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = messageTime;

        bubbleDiv.append(nameSpan, textDiv, timeDiv);
    }

    // 创建底部标签容器
    var hasBottomTags = (duration !== null && duration !== undefined && duration !== "" && duration !== 0) ||
                       (cacheHit === true) || (glossaryMatch === true) || (skipSrcLang === true) ||
                       (usage && usage.total_tokens !== null && usage.total_tokens !== undefined);
    if (hasBottomTags) {
        var bottomTagsContainer = document.createElement('div');
        bottomTagsContainer.className = 'bottom-tags-container';

        // 添加usage标签（如果有usage信息）
        if (usage && usage.total_tokens !== null && usage.total_tokens !== undefined) {
            var usageTag = document.createElement('div');
            usageTag.className = 'usage-tag';

            // 创建usage图标 (更换为代币图标)
            var usageIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            usageIcon.setAttribute('viewBox', '0 0 24 24');
            usageIcon.setAttribute('fill', 'none');
            usageIcon.setAttribute('stroke', 'currentColor');
            usageIcon.setAttribute('stroke-width', '2');
            usageIcon.setAttribute('stroke-linecap', 'round');
            usageIcon.setAttribute('stroke-linejoin', 'round');
            usageIcon.innerHTML = '<path d="M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0 -18 0" /><path d="M14.8 9a2 2 0 0 0 -1.8 -1h-2a2 2 0 0 0 0 4h2a2 2 0 0 1 0 4h-2a2 2 0 0 1 -1.8 -1" /><path d="M12 6v2" /><path d="M12 16v2" />';

            // 创建total显示
            var usageTotal = document.createElement('span');
            usageTotal.className = 'usage-total';
            usageTotal.textContent = usage.total_tokens;

            // 创建详细信息 (添加单位)
            var usageDetail = document.createElement('span');
            usageDetail.className = 'usage-detail';
            usageDetail.textContent = `${usage.prompt_tokens}+${usage.completion_tokens}=${usage.total_tokens} tokens`;

            usageTag.appendChild(usageIcon);
            usageTag.appendChild(usageTotal);
            usageTag.appendChild(usageDetail);
            bottomTagsContainer.appendChild(usageTag);
        }

        // 添加耗时标签（如果有duration信息）
        if (duration !== null && duration !== undefined && duration !== "" && duration !== 0) {
            var durationTag = document.createElement('div');
            durationTag.className = 'duration-tag';

            // 创建闪电图标
            var lightningIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            lightningIcon.setAttribute('viewBox', '0 0 24 24');
            lightningIcon.setAttribute('fill', 'currentColor');
            lightningIcon.innerHTML = '<path d="M13 0L6 12h5l-1 12 7-12h-5l1-12z"/>';

            // 创建耗时文本
            var durationText = document.createTextNode(duration.toString());

            durationTag.appendChild(lightningIcon);
            durationTag.appendChild(durationText);
            bottomTagsContainer.appendChild(durationTag);
        }

        // 添加术语表匹配标签
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

        // 添加跳过源语言标签
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

        // 添加缓存命中标签（如果cache_hit为true）
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

    // 检查过滤状态
    if (messageType && messageFilters.hasOwnProperty(messageType) && !messageFilters[messageType]) {
        bubbleDiv.classList.add('hidden');
    }

    newMessageItem.appendChild(bubbleDiv);
    return {
        element: newMessageItem,
        type: messageType
    };
}

// 处理消息滚动逻辑
function handleMessageScroll(wasAtBottom) {
    // 更新滚动按钮状态
    updateScrollButtonState();

    // 只有当之前用户在底部，且没有短时间内滚动操作，且没有待处理消息时，才自动滚动
    var userRecentlyScrolled = (Date.now() - lastScrollTime) < 300;

    if (wasAtBottom && !userRecentlyScrolled && pendingMessages === 0) {
        // 使用requestAnimationFrame确保DOM完全更新后再滚动
        requestAnimationFrame(function() {
            // 如果添加消息前在底部，就强制滚到底部
            scrollToBottom();
        });
    } else if (!wasAtBottom) {
        // 如果添加消息时用户不在底部，确保按钮是可见的（如果需要滚动）
        updateScrollButtonState();
    }
}

function initializeEventSource() {
    // 如果已存在连接，先关闭
    if (window.eventSource) {
        window.eventSource.close();
    }

    // 创建新连接
    window.eventSource = new EventSource("/stream");

    // 设置事件处理程序
    window.eventSource.onmessage = function(event) {
        // 收到消息时先检查用户是否在底部，在添加消息之前进行检查
        var wasAtBottom = checkIfAtBottom();
        pendingMessages++;

        var jsonData = JSON.parse(event.data);
        var name = jsonData.name;
        var messageText = jsonData.message;
        var messageTime = jsonData.time;
        var duration = jsonData.duration;
        var cacheHit = jsonData.cache_hit;
        var glossaryMatch = jsonData.glossary_match;
        var skipSrcLang = jsonData.skip_src_lang;
        var usage = jsonData.usage;

        // 检查是否为翻译完成的INFO消息
        if (name === "[INFO]" && isTranslating) {
            setTimeout(resetTranslationUI, 500);
        }

        // 使用通用函数创建消息元素
        var messageData = createMessageElement(name, messageText, messageTime, duration, cacheHit, glossaryMatch, skipSrcLang, usage);
        messageList.appendChild(messageData.element);

        pendingMessages--;
        handleMessageScroll(wasAtBottom);
        updateClearButtonVisibility();
    };

    window.eventSource.onerror = function(event) {
        window.eventSource.close();
    };
}

//更新清除按钮状态的函数
function updateClearButtonVisibility() {
    var messageList = document.getElementById('message-list');
    var clearButton = document.getElementById('clear-messages-btn');

    if (messageList.childElementCount > 0) {
        clearButton.style.display = 'flex';
    } else {
        clearButton.style.display = 'none';
    }
}

// 检查是否在底部的函数
function checkIfAtBottom() {
    var tolerance = 20;
    return (window.innerHeight + window.pageYOffset) >= (document.body.scrollHeight - tolerance);
}

// 检查是否需要滚动的函数
function needsScrolling() {
    return document.body.scrollHeight > window.innerHeight;
}

// 更新滚动按钮状态的函数
function updateScrollButtonState() {
    isAtBottom = checkIfAtBottom();

    if (!needsScrolling() || isAtBottom) {
        scrollBottomBtn.style.display = "none";
    } else {
        scrollBottomBtn.style.display = "flex";
    }
}

// 滚动到底部的函数
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

scrollBottomBtn.addEventListener('click', function() {
    scrollToBottom();
});

document.getElementById('clear-messages-btn').addEventListener('click', function() {
    obfuscatedElements.forEach(function(element) {
        removeObfuscatedElement(element);
    });
    obfuscatedElements.clear();

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
            updateClearButtonVisibility();
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
    updateScrollButtonState();
    updateClearButtonVisibility();
});

// Dark mode toggle functionality
(function() {
    var toggleButton = document.getElementById("dark-mode-toggle");
    var storedTheme = localStorage.getItem("theme");
    if (storedTheme) {
        document.documentElement.setAttribute("data-theme", storedTheme);
    }
    function updateIcon() {
        var currentTheme = document.documentElement.getAttribute("data-theme");
        if (currentTheme === "dark") {
            toggleButton.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>';
        } else {
            toggleButton.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 0112.21 3 7 7 0 0012 21a9 9 0 009-8.21z"></path></svg>';
        }
    }
    updateIcon();
    toggleButton.addEventListener("click", function() {
        var currentTheme = document.documentElement.getAttribute("data-theme");
        if (currentTheme === "dark") {
            document.documentElement.setAttribute("data-theme", "light");
            localStorage.setItem("theme", "light");
        } else {
            document.documentElement.setAttribute("data-theme", "dark");
            localStorage.setItem("theme", "dark");
        }
        updateIcon();
    });
})();
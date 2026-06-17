

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function prioritizeImageLoading() {
    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://kodik-add.com/add-players.min.js';
    document.head.appendChild(script);
}

var kodikAddPlayers = {
    shikimoriID: document.currentScript ? document.currentScript.getAttribute('data-shikimori-id') : null,
    types: "anime, anime-serial, foreign-cartoon, anime-movie",
    width: "100%",
    height: "100%",
    camrip: false,
    prioritizeTranslations: [609,610,1978,767,643],
    onDomReady: true
};

kodikAddPlayers.foundCallback = function(data) {
    console.log("Плеер инициализирован");
    document.querySelectorAll('.kodik-season-selector-wrapper, .kodik-episode-selector-wrapper')
           .forEach(el => el.remove());
};

kodikAddPlayers.notFoundCallback = function() {
    console.error("Kodik: аниме не найдено");
};

let skipTime = 85;
let isFullscreen = false;

// Обработчики событий Kodik плеера
window.addEventListener('message', (e) => {
    const data = e.data;

    // Событие скипа опенинга
    if (data.key === 'kodik_player_skip_button') {
        const btn = document.getElementById('skip-op-button');
        if (btn) {
            btn.style.display = 'block';
            skipTime = data.value.start_time + 5;
            setTimeout(() => {
                if (btn) btn.style.display = 'none';
            }, 5000);
        }
    }

    // Смена серии/сезона
    if (data.key === 'kodik_player_current_episode') {
        const skipBtn = document.getElementById('skip-op-button');
        if (skipBtn) skipBtn.style.display = 'none';
    }

    // Полноэкранный режим
    if (data.key === 'kodik_player_enter_pip') isFullscreen = true;
    if (data.key === 'kodik_player_exit_pip') isFullscreen = false;
});



// Функция для сворачивания/разворачивания описания
let descriptionState = {
    isExpanded: false,
    originalHTML: null,
    isTruncating: false
};

function checkDescriptionHeight() {
    const description = document.getElementById('anime-description');
    if (!description) return false;

    const computedStyle = getComputedStyle(description);
    const lineHeight = parseFloat(computedStyle.lineHeight);
    const height = description.scrollHeight;

    const numberOfLines = Math.round(height / lineHeight);

    console.log('Высота элемента:', height, 'px');
    console.log('Высота строки:', lineHeight, 'px');
    console.log('Расчетное количество строк:', numberOfLines);
    console.log('Нужно обрезать (>=5 строк):', numberOfLines >= 5);

    return numberOfLines >= 5;
}

function truncateDescription() {
    const description = document.getElementById('anime-description');
    const readMoreBtn = document.getElementById('read-more-btn');

    if (!description || descriptionState.isTruncating) return;

    descriptionState.isTruncating = true;

    if (!descriptionState.originalHTML) {
        descriptionState.originalHTML = description.innerHTML;
    }

    const originalHTML = descriptionState.originalHTML;

    // Восстанавливаем оригинальный HTML
    description.innerHTML = originalHTML;
    description.classList.remove('description-content--collapsed', 'description-content--expanded');

    // Убираем все inline кнопки
    const inlineButtons = description.querySelectorAll('.read-more-inline');
    inlineButtons.forEach(btn => btn.remove());

    // Проверяем высоту
    const shouldTruncate = checkDescriptionHeight();

    if (!shouldTruncate) {
        console.log('Текст короткий, скрываем кнопки');
        description.classList.add('description-content--expanded');

        // Гарантированно скрываем основную кнопку
        if (readMoreBtn) {
            readMoreBtn.style.display = 'none';
            readMoreBtn.style.visibility = 'hidden';
            readMoreBtn.style.opacity = '0';
        }

        descriptionState.isTruncating = false;
        descriptionState.isExpanded = true;
        return;
    }

    console.log('Текст длинный, обрезаем');

    // Создаем временный элемент для измерения
    const tempDiv = document.createElement('div');
    tempDiv.style.cssText = `
        position: absolute;
        top: -9999px;
        left: -9999px;
        width: ${description.offsetWidth}px;
        font: inherit;
        line-height: 1.5em;
        font-size: 1.05rem;
        white-space: normal;
        overflow: hidden;
    `;
    document.body.appendChild(tempDiv);

    // Получаем чистый текст
    const tempTextDiv = document.createElement('div');
    tempTextDiv.innerHTML = originalHTML;
    const plainText = tempTextDiv.textContent || tempTextDiv.innerText;

    // Устанавливаем максимальную высоту в 4 строки
    const lineHeight = parseFloat(getComputedStyle(description).lineHeight);
    const maxHeight = lineHeight * 4;

    // Если текст короткий, скрываем кнопку
    tempDiv.innerHTML = originalHTML;
    if (tempDiv.scrollHeight <= maxHeight) {
        if (readMoreBtn) {
            readMoreBtn.style.display = 'none';
            readMoreBtn.textContent = 'Читать дальше';
            readMoreBtn.onclick = expandDescription;
        }
        description.classList.remove('description-content--collapsed');
        description.classList.add('description-content--expanded');
        document.body.removeChild(tempDiv);
        descriptionState.isTruncating = false;
        return;
    }

    // Бинарный поиск для определения количества символов
    let low = 0;
    let high = plainText.length;
    let bestIndex = plainText.length;

    while (low <= high) {
        const mid = Math.floor((low + high) / 2);
        const testText = plainText.substring(0, mid);

        tempDiv.textContent = testText;
        const height = tempDiv.scrollHeight;

        if (height <= maxHeight) {
            bestIndex = mid;
            low = mid + 1;
        } else {
            high = mid - 1;
        }
    }

    // УВЕЛИЧИВАЕМ КОЛИЧЕСТВО СИМВОЛОВ НА 13
    bestIndex = Math.min(bestIndex + 13, plainText.length);

    // Находим последний пробел
    let visibleText = plainText.substring(0, bestIndex);
    const lastSpaceIndex = visibleText.lastIndexOf(' ');

    if (lastSpaceIndex > 0 && bestIndex - lastSpaceIndex < 15) {
        visibleText = visibleText.substring(0, lastSpaceIndex);
    }

    // Удаляем временные элементы
    document.body.removeChild(tempDiv);

    // Физически обрезаем HTML
    const tempContainer = document.createElement('div');
    tempContainer.innerHTML = originalHTML;

    // Рекурсивно обрезаем DOM
    function truncateNode(node, charsLeft) {
        if (charsLeft <= 0) {
            node.remove();
            return 0;
        }

        if (node.nodeType === Node.TEXT_NODE) {
            if (node.textContent.length > charsLeft) {
                // Обрезаем текст с минимальным запасом
                let trimLength = charsLeft;

                // Находим оптимальную точку обрезки - ближе к концу строки
                const text = node.textContent.substring(0, charsLeft);

                // Ищем последний пробел или пунктуацию в последних 10 символах
                const searchEnd = Math.max(0, text.length - 10);
                let bestBreakPoint = text.length;

                for (let i = text.length - 1; i >= searchEnd; i--) {
                    const char = text[i];
                    if (char === ' ' || char === '.' || char === ',' || char === '!' || char === '?') {
                        bestBreakPoint = i;
                        break;
                    }
                }

                // Если нашли хорошую точку обрезки рядом с концом, используем её
                if (bestBreakPoint > charsLeft - 8) {
                    trimLength = bestBreakPoint;
                } else {
                    // Иначе обрезаем практически до конца, оставляя минимум
                    trimLength = Math.max(charsLeft - 2, 0);
                }

                node.textContent = node.textContent.substring(0, trimLength);

                // Создаем обертку для текста с маской
                const textWrapper = document.createElement('span');
                textWrapper.className = 'truncated-text';

                // Заменяем текстовый узел на обертку с текстом
                const parent = node.parentNode;
                parent.insertBefore(textWrapper, node);
                textWrapper.appendChild(node);

                // Создаем кнопку как часть текста
                const readMoreSpan = document.createElement('span');
                readMoreSpan.className = 'read-more-inline';
                readMoreSpan.textContent = 'Читать дальше';
                readMoreSpan.style.cssText = `
                    display: inline;
                    color: #3b82f6;
                    cursor: pointer;
                    white-space: nowrap;
                    margin-left: 1px;
                    background: none;
                    border: none;
                    padding: 0;
                    font: inherit;
                    font-size: inherit;
                    line-height: inherit;
                `;
                readMoreSpan.addEventListener('click', expandDescription);

                // Вставляем кнопку сразу после обертки с текстом
                parent.insertBefore(readMoreSpan, textWrapper.nextSibling);

                return 0;
            } else {
                return charsLeft - node.textContent.length;
            }
        } else if (node.nodeType === Node.ELEMENT_NODE) {
            const children = Array.from(node.childNodes);
            let remainingChars = charsLeft;

            for (const child of children) {
                remainingChars = truncateNode(child, remainingChars);
                if (remainingChars <= 0) break;
            }

            if (node.childNodes.length === 0) {
                node.remove();
            }

            return remainingChars;
        }

        return charsLeft;
    }

    // Обрезаем DOM
    truncateNode(tempContainer, visibleText.length);
    const truncatedHTML = tempContainer.innerHTML;

    // Вставляем обрезанный HTML (УЖЕ С КНОПКОЙ ВНУТРИ)
    description.innerHTML = truncatedHTML;

    description.classList.add('description-content--collapsed');
    description.classList.remove('description-content--expanded');

    // Скрываем основную кнопку
    if (readMoreBtn) {
        readMoreBtn.style.display = 'none';
    }

    descriptionState.isExpanded = false;
    descriptionState.isTruncating = false;
}

document.addEventListener('click', function(e) {
    if (e.target.classList.contains('read-more-inline')) {
        expandDescription();
    }
});

// Также обновим функцию expandDescription для корректной работы
function expandDescription() {
    const description = document.getElementById('anime-description');
    const readMoreBtn = document.getElementById('read-more-btn');

    if (!description || !descriptionState.originalHTML) return;

    description.innerHTML = descriptionState.originalHTML;
    description.classList.remove('description-content--collapsed');
    description.classList.add('description-content--expanded');

    // Убираем inline кнопки
    const inlineButtons = description.querySelectorAll('.read-more-inline');
    inlineButtons.forEach(btn => btn.remove());

    // Показываем кнопку "Свернуть" только если текст длинный
    if (readMoreBtn && checkDescriptionHeight()) {
        readMoreBtn.style.display = 'inline-block';
        readMoreBtn.style.visibility = 'visible';
        readMoreBtn.style.opacity = '1';
        readMoreBtn.textContent = 'Свернуть';
        readMoreBtn.onclick = collapseDescription;
    } else if (readMoreBtn) {
        // Если текст короткий, скрываем кнопку
        readMoreBtn.style.display = 'none';
        readMoreBtn.style.visibility = 'hidden';
        readMoreBtn.style.opacity = '0';
    }

    descriptionState.isExpanded = true;
}

function collapseDescription() {
    // Всегда проверяем нужно ли обрезать
    if (checkDescriptionHeight()) {
        descriptionState.isExpanded = false;
        truncateDescription();
    } else {
        // Если текст стал коротким, просто скрываем кнопку
        const readMoreBtn = document.getElementById('read-more-btn');
        if (readMoreBtn) {
            readMoreBtn.style.display = 'none';
        }
        descriptionState.isExpanded = false;
    }
}

function initDescriptionToggle() {
    // Сначала полностью скрываем кнопку через JS
    const readMoreBtn = document.getElementById('read-more-btn');
    if (readMoreBtn) {
        readMoreBtn.style.display = 'none';
        readMoreBtn.style.visibility = 'hidden';
        readMoreBtn.style.opacity = '0';
    }

    // Даем время на отрисовку DOM
    setTimeout(() => {
        truncateDescription();
    }, 100);

    // Оптимизированный обработчик изменения размера
    let resizeTimeout;
    let lastWidth = window.innerWidth;

    window.addEventListener('resize', function() {
        const currentWidth = window.innerWidth;

        if (Math.abs(currentWidth - lastWidth) < 50) return;

        lastWidth = currentWidth;

        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            if (!descriptionState.isExpanded) {
                truncateDescription();
            }
        }, 250);
    });
}


document.addEventListener('DOMContentLoaded', function() {
    prioritizeImageLoading();
    initDescriptionToggle();

    // Проверка для .anime-header (если нужна)
    var header = document.querySelector('.anime-header');
    if (header) {
        header.style.backgroundImage = 'none';
    }

    // Обработчик кнопки пропуска опенинга
    var skipButton = document.getElementById('skip-op-button');
    if (skipButton) {
        skipButton.addEventListener('click', function() {
            var iframe = document.querySelector('#kodik-player iframe');
            if (iframe && iframe.contentWindow) {
                iframe.contentWindow.postMessage({
                    key: "kodik_player_api",
                    value: { method: "seek", seconds: skipTime }
                }, '*');
            }
        });
    }

    // Последовательное появление блоков (уже было, оставь)
    window.addEventListener('load', function() {
        var blockIds = ['player-block', 'franchise-block', 'similar-anime-block', 'comments-block'];
        blockIds.forEach(function(id, index) {
            var block = document.getElementById(id);
            if (block) {
                setTimeout(function() {
                    block.classList.add('loaded-block');
                }, index * 100);
            }
        });
    });
});

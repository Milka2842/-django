// deferred.js - код для асинхронной загрузки
document.addEventListener('DOMContentLoaded', function() {
    // Функция getCookie должна быть доступна (определена в critical.js)
    if (typeof getCookie !== 'function') {
        console.error('Функция getCookie не определена');
        return;
    }

    // Функции для работы с рейтингами комментариев
    function saveRatingState(commentId, action) {
        try {
            const ratings = JSON.parse(localStorage.getItem('commentRatings') || '{}');
            ratings[commentId] = action;
            localStorage.setItem('commentRatings', JSON.stringify(ratings));
        } catch (e) {
            console.error('Ошибка сохранения рейтинга:', e);
        }
    }

    function loadRatingState(commentId) {
        try {
            const ratings = JSON.parse(localStorage.getItem('commentRatings') || '{}');
            return ratings[commentId] || null;
        } catch (e) {
            console.error('Ошибка загрузки рейтинга:', e);
            return null;
        }
    }

    function updateRatingUI(commentId, action) {
        const comment = document.querySelector(`[data-comment-id="${commentId}"]`);
        if (!comment) return;

        const likeBtn = comment.querySelector('.like-btn');
        const dislikeBtn = comment.querySelector('.dislike-btn');

        likeBtn?.classList.remove('active');
        dislikeBtn?.classList.remove('active');

        if (action === 'like' && likeBtn) {
            likeBtn.classList.add('active');
        } else if (action === 'dislike' && dislikeBtn) {
            dislikeBtn.classList.add('active');
        }
    }

    // Инициализация состояний при загрузке
    try {
        const ratings = JSON.parse(localStorage.getItem('commentRatings') || '{}');
        Object.keys(ratings).forEach(commentId => {
            updateRatingUI(commentId, ratings[commentId]);
        });
    } catch (e) {
        console.error('Ошибка инициализации рейтингов:', e);
    }

    // Единый обработчик для лайков/дизлайков
    document.addEventListener('click', async (e) => {
        const btn = e.target.closest('.like-btn, .dislike-btn');
        if (!btn) return;

        const commentId = btn.dataset.commentId;
        const action = btn.dataset.action;
        const commentActions = btn.closest('.comment-actions');
        if (!commentActions) return;

        const likeBtn = commentActions.querySelector('.like-btn');
        const dislikeBtn = commentActions.querySelector('.dislike-btn');

        if (!likeBtn || !dislikeBtn) return;

        // Сохраняем текущие значения для сравнения
        const oldLikes = parseInt(likeBtn.querySelector('.count')?.textContent || 0);
        const oldDislikes = parseInt(dislikeBtn.querySelector('.count')?.textContent || 0);

        // Текущее состояние
        const currentState = loadRatingState(commentId);
        const isActive = btn.classList.contains('active');

        try {
            // Блокируем кнопку на время запроса
            btn.disabled = true;

            const response = await fetch(`/comment/${commentId}/${action}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                },
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            // Обновляем счетчики
            if (likeBtn.querySelector('.count')) {
                likeBtn.querySelector('.count').textContent = data.likes || 0;
            }
            if (dislikeBtn.querySelector('.count')) {
                dislikeBtn.querySelector('.count').textContent = data.dislikes || 0;
            }

            // Определяем новое состояние
            let newState = null;

            if (currentState === action) {
                // Снимаем оценку
                newState = null;
                btn.classList.remove('active');
            } else {
                // Устанавливаем новую оценку
                newState = action;

                // Снимаем активность с противоположной кнопки
                if (action === 'like' && dislikeBtn) {
                    dislikeBtn.classList.remove('active');
                } else if (action === 'dislike' && likeBtn) {
                    likeBtn.classList.remove('active');
                }

                // Устанавливаем активность текущей кнопке
                btn.classList.add('active');
            }

            // Сохраняем новое состояние
            saveRatingState(commentId, newState);

        } catch (error) {
            console.error('Ошибка:', error);
            // Восстанавливаем предыдущие значения
            if (likeBtn.querySelector('.count')) {
                likeBtn.querySelector('.count').textContent = oldLikes;
            }
            if (dislikeBtn.querySelector('.count')) {
                dislikeBtn.querySelector('.count').textContent = oldDislikes;
            }
        } finally {
            // Разблокируем кнопку
            btn.disabled = false;
        }
    });

    // Обработчик для форм комментариев
    async function handleCommentSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const parentId = form.querySelector('input[name="parent_id"]')?.value || null;

        try {
            const formData = new FormData(form);
            const response = await fetch(window.location.href, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Accept': 'application/json',
                },
                body: formData,
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            if (data.success) {
                // Создаем элемент комментария
                const newComment = document.createElement('div');
                newComment.className = 'comment mb-3 p-3 border rounded';
                newComment.setAttribute('data-comment-id', data.comment_id);
                newComment.setAttribute('data-parent-id', data.parent_id || '');

                // Используем простые иконки
                newComment.innerHTML = `
                    <div class="comment-header mb-2">
                        <strong>${data.user}</strong>
                        <small class="text-muted">${data.created_at}</small>
                    </div>
                    <p class="mb-2">${data.text}</p>
                    <div class="comment-actions d-flex gap-2 align-items-center">
                        <button class="btn btn-sm like-btn" data-comment-id="${data.comment_id}" data-action="like">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M1 21h4V9H1v12zm22-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L14.17 1 7.59 7.59C7.22 7.95 7 8.45 7 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-2z" fill="currentColor"/>
                            </svg>
                            <span class="count">0</span>
                        </button>
                        <button class="btn btn-sm dislike-btn" data-comment-id="${data.comment_id}" data-action="dislike">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M15 3H6c-.83 0-1.54.5-1.84 1.22l-3.02 7.05c-.09.23-.14.47-.14.73v2c0 1.1.9 2 2 2h6.31l-.95 4.57-.03.32c0 .41.17.79.44 1.06L9.83 23l6.58-6.59c.36-.36.58-.86.58-1.41V5c0-1.1-.9-2-2-2zm4 0v12h4V3h-4z" fill="currentColor"/>
                            </svg>
                            <span class="count">0</span>
                        </button>
                        <button class="btn btn-link text-decoration-none p-0 show-replies-btn" data-comment-id="${data.comment_id}">
                            Ответы 0
                        </button>
                    </div>
                    <div class="replies ml-4 mt-2" id="replies-${data.comment_id}" style="display: none;"></div>
                `;

                // Находим целевой контейнер
                const targetContainer = data.parent_id
                    ? document.querySelector(`#replies-${data.parent_id}`)
                    : document.querySelector('.comments-list');

                if (targetContainer) {
                    // Добавляем новый комментарий
                    targetContainer.prepend(newComment);

                    // Обновляем счетчик ответов
                    if (data.parent_id) {
                        const parentComment = document.querySelector(`[data-comment-id="${data.parent_id}"]`);
                        if (parentComment) {
                            const repliesBtn = parentComment.querySelector('.show-replies-btn');
                            if (repliesBtn) {
                                const currentCount = parseInt(repliesBtn.textContent.match(/\d+/) || 0);
                                repliesBtn.textContent = `Ответов ${currentCount + 1}`;
                            }

                            // Показываем контейнер ответов
                            const repliesContainer = parentComment.querySelector('.replies');
                            if (repliesContainer && repliesContainer.style.display === 'none') {
                                repliesContainer.style.display = 'block';
                            }
                        }
                    }

                    // Обновляем общий счетчик
                    const totalCountElement = document.querySelector('#comments-block h2');
                    if (totalCountElement) {
                        const totalCount = parseInt(totalCountElement.textContent.match(/\d+/) || 0) + 1;
                        totalCountElement.textContent = `Комментарии (${totalCount})`;
                    }
                }

                // Очищаем форму
                form.reset();
                const parentIdInput = document.getElementById('parent_id');
                if (parentIdInput) parentIdInput.value = '';

                // Дополнительно: сбрасываем высоту textarea
                const textarea = form.querySelector('textarea');
                if (textarea) textarea.style.height = 'auto';
            }
        } catch (error) {
            console.error('Ошибка:', error);
            alert('Произошла ошибка при отправке комментария. Попробуйте еще раз.');
        }
    }

    // Инициализация главной формы
    const mainForm = document.querySelector('form');
    if (mainForm) {
        mainForm.addEventListener('submit', handleCommentSubmit);
    }

    // Обработчик для кнопок ответов
    document.addEventListener('click', (e) => {
        const showRepliesBtn = e.target.closest('.show-replies-btn');
        if (!showRepliesBtn) return;

        const commentId = showRepliesBtn.dataset.commentId;
        const repliesContainer = document.getElementById(`replies-${commentId}`);
        if (!repliesContainer) return;

        const isExpanded = repliesContainer.style.display === 'block';
        repliesContainer.style.display = isExpanded ? 'none' : 'block';

        // Создаем форму/сообщение только при первом открытии
        if (!isExpanded && !repliesContainer.querySelector('.reply-content')) {
            const contentDiv = document.createElement('div');
            contentDiv.className = 'reply-content';

            // Проверяем, авторизован ли пользователь
            const isAuthenticated = document.body.classList.contains('user-authenticated') ||
                                  document.querySelector('form') !== null;

            if (isAuthenticated) {
                // Для авторизованных: форма ответа
                contentDiv.innerHTML = `
                    <form class="mt-3 reply-form">
                        <textarea class="form-control mb-2" name="text" rows="2"
                                  placeholder="Ваш ответ..." required></textarea>
                        <input type="hidden" name="parent_id" value="${commentId}">
                        <input type="hidden" name="csrfmiddlewaretoken" value="${getCookie('csrftoken')}">
                        <button type="submit" class="btn btn-primary btn-sm">Отправить</button>
                    </form>
                `;
                contentDiv.querySelector('form').addEventListener('submit', handleCommentSubmit);
            } else {
                // Для неавторизованных: сообщение
                contentDiv.innerHTML = `
                    <p style="color: #b0b0b0; margin-top: 10px;">
                        <a href="/register/" style="color: #3b82f6;">Зарегистрируйтесь</a>, чтобы ответить
                    </p>
                `;
            }

            repliesContainer.appendChild(contentDiv);
        }
    });

    // Инициализация каруселей
    initCarousel('franchise');
    initCarousel('similar');

    // Инициализация кнопки загрузки комментариев
    const loadMoreBtn = document.getElementById('load-more-btn');
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', loadMoreComments);
    }
});

function initCarousel(blockType) {
    const selector = blockType === 'franchise' ? '#franchise-block .franchise-carousel' : '#similar-anime-block .franchise-carousel';
    const carousel = document.querySelector(selector);
    if (!carousel) return;

    const viewport = carousel.querySelector('.franchise-viewport');
    const track = carousel.querySelector('.franchise-track');
    const items = Array.from(track.querySelectorAll('.franchise-item'));
    const leftArrow = carousel.querySelector('.franchise-arrow.left');
    const rightArrow = carousel.querySelector('.franchise-arrow.right');

    // Определяем начальный индекс
    let currentIndex = 0;
    if (blockType === 'franchise') {
        const activeItem = track.querySelector('.franchise-item.active');
        if (activeItem) currentIndex = items.indexOf(activeItem);
    }
    if (currentIndex < 0) currentIndex = 0;
    if (currentIndex >= items.length) currentIndex = items.length - 1;

    // Если элементов меньше двух, скрываем стрелки
    if (items.length < 2) {
        if (leftArrow) leftArrow.style.display = 'none';
        if (rightArrow) rightArrow.style.display = 'none';
        return;
    }

    const isMobile = window.innerWidth < 768;

    function updatePositions() {
        items.forEach((item, index) => {
            item.classList.remove(
                'active', 'left-1', 'left-2', 'left-3',
                'right-1', 'right-2', 'right-3',
                'hidden-left', 'hidden-right', 'hidden'
            );
            const diff = index - currentIndex;
            if (diff === 0) item.classList.add('active');
            else if (diff === -1) item.classList.add('left-1');
            else if (diff === -2) item.classList.add('left-2');
            else if (diff <= -3) item.classList.add('hidden-left');
            else if (diff === 1) item.classList.add('right-1');
            else if (diff === 2) item.classList.add('right-2');
            else if (diff >= 3) item.classList.add('hidden-right');
        });

        if (leftArrow) leftArrow.style.display = currentIndex === 0 ? 'none' : 'block';
        if (rightArrow) rightArrow.style.display = currentIndex === items.length - 1 ? 'none' : 'block';
    }

    // ---------- Улучшенный drag с постоянным захватом ----------
    let startX = 0, startY = 0, startTime = 0;
    let lastX = 0;
    let isDragging = false;
    let swiped = false;          // был ли горизонтальный свайп (превышен порог)
    let preventClick = false;    // нужно ли предотвратить клик после жеста
    const threshold = isMobile ? 8 : 12; // пиксели для определения свайпа
    const carouselWidth = carousel.offsetWidth;
    const thresholdPercent = isMobile ? 12 : 15;
    const switchThreshold = carouselWidth * (thresholdPercent / 100);
    let accumulatedDistance = 0;
    let lastSwitchTime = 0;
    const switchCooldown = 150;

    function handleDragStart(e) {
        const clientX = e.pageX ?? e.touches[0].pageX;
        const clientY = e.pageY ?? e.touches[0].pageY;
        startX = clientX;
        startY = clientY;
        lastX = clientX;
        startTime = Date.now();
        isDragging = true;
        swiped = false;
        preventClick = false;    // сбрасываем флаг блокировки клика
        accumulatedDistance = 0;
        carousel.classList.add('dragging');
        track.classList.add('dragging');
        if (e.type === 'mousedown') e.preventDefault(); // для мыши блокируем выделение
    }

    function handleDragMove(e) {
        if (!isDragging) return;
        const clientX = e.pageX ?? e.touches[0].pageX;
        const clientY = e.pageY ?? e.touches[0].pageY;
        const deltaX = clientX - lastX;

        // Определяем свайп по горизонтальному смещению от старта
        if (!swiped && Math.abs(clientX - startX) > threshold) {
            swiped = true;
            preventClick = true; // был свайп → блокируем клик
        }

        accumulatedDistance += deltaX;
        lastX = clientX;

        const now = Date.now();
        if (Math.abs(accumulatedDistance) >= switchThreshold && now - lastSwitchTime >= switchCooldown) {
            const direction = accumulatedDistance > 0 ? -1 : 1;
            if (direction < 0 && currentIndex > 0) {
                currentIndex--;
                updatePositions();
                lastSwitchTime = now;
                const remainder = Math.abs(accumulatedDistance) - switchThreshold;
                accumulatedDistance = direction * remainder;
            } else if (direction > 0 && currentIndex < items.length - 1) {
                currentIndex++;
                updatePositions();
                lastSwitchTime = now;
                const remainder = Math.abs(accumulatedDistance) - switchThreshold;
                accumulatedDistance = direction * remainder;
            }
        }

        // Блокируем стандартное поведение только если событие отменяемо и был свайп
        if (e.type === 'touchmove' && swiped && e.cancelable) {
            e.preventDefault();
        }
    }

    function handleDragEnd(e) {
        if (!isDragging) return;

        const clientX = e.pageX ?? (e.changedTouches?.[0]?.pageX ?? lastX);
        const totalDistance = clientX - startX;
        const timeElapsed = Date.now() - startTime;

        // Если не было свайпа, но движение было коротким и быстрым – переключаем
        if (!swiped && Math.abs(totalDistance) > threshold * 2 && timeElapsed < 300) {
            if (totalDistance > 0 && currentIndex > 0) currentIndex--;
            else if (totalDistance < 0 && currentIndex < items.length - 1) currentIndex++;
            updatePositions();
            // В этом случае свайпа не было, но слайд переключился – клик тоже блокируем
            preventClick = true;
        }

        resetDrag();
    }

    function resetDrag() {
        isDragging = false;
        // Не сбрасываем swiped и preventClick сразу, чтобы они успели сработать в обработчике click
        // Они сбросятся при следующем dragStart
        accumulatedDistance = 0;
        carousel.classList.remove('dragging');
        track.classList.remove('dragging');
        lastSwitchTime = 0;
    }

    // Глобальный обработчик клика на карусели для предотвращения перехода по ссылкам после свайпа
    carousel.addEventListener('click', (e) => {
        if (preventClick) {
            e.preventDefault();
            e.stopPropagation(); // останавливаем всплытие, чтобы клик не сработал на ссылке
            // Сбрасываем флаг после обработки
            preventClick = false;
        }
    }, true); // используем capturing, чтобы поймать событие до целевых обработчиков

    // Обработчики для мыши
    carousel.addEventListener('mousedown', handleDragStart);
    document.addEventListener('mousemove', handleDragMove);
    document.addEventListener('mouseup', handleDragEnd);
    document.addEventListener('mouseleave', resetDrag);

    // Обработчики для touch
    carousel.addEventListener('touchstart', handleDragStart, { passive: false });
    document.addEventListener('touchmove', handleDragMove, { passive: false });
    document.addEventListener('touchend', handleDragEnd, { passive: false });
    document.addEventListener('touchcancel', resetDrag, { passive: false });

    // Запрещаем контекстное меню на карусели
    carousel.addEventListener('contextmenu', e => e.preventDefault());

    // Стрелки
    if (leftArrow) {
        leftArrow.addEventListener('click', (e) => {
            e.stopPropagation(); // предотвращаем влияние флага preventClick на стрелки
            if (currentIndex > 0) {
                currentIndex--;
                updatePositions();
            }
        });
    }
    if (rightArrow) {
        rightArrow.addEventListener('click', (e) => {
            e.stopPropagation();
            if (currentIndex < items.length - 1) {
                currentIndex++;
                updatePositions();
            }
        });
    }

    updatePositions();
}

// Функция загрузки дополнительных комментариев
async function loadMoreComments() {
    const loadMoreBtn = document.getElementById('load-more-btn');
    if (!loadMoreBtn) return;

    const nextPage = loadMoreBtn.dataset.nextPage;
    const totalComments = parseInt(loadMoreBtn.dataset.totalComments);
    const oldButtonHtml = loadMoreBtn.innerHTML;

    loadMoreBtn.disabled = true;
    loadMoreBtn.innerHTML = 'Загрузка...';

    try {
        const response = await fetch(`?page=${nextPage}&type=comments`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        });

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const html = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        // Добавляем новые комментарии
        const newComments = doc.querySelectorAll('.comment');
        const commentsContainer = document.getElementById('comments-container');

        if (newComments.length > 0 && commentsContainer) {
            newComments.forEach(commentNode => {
                const clone = commentNode.cloneNode(true);

                // Скрываем ВСЕ контейнеры ответов
                const replyContainers = clone.querySelectorAll('.replies');
                replyContainers.forEach(container => {
                    container.style.display = 'none';
                    // Добавляем атрибут для отслеживания состояния
                    container.setAttribute('data-initial-state', 'hidden');
                });

                commentsContainer.appendChild(clone);
                initCommentRatings(clone); // Инициализируем рейтинги
            });
        }

        // Обновляем кнопку
        const newLoadMoreBtn = doc.getElementById('load-more-btn');
        if (newLoadMoreBtn) {
            loadMoreBtn.dataset.nextPage = newLoadMoreBtn.dataset.nextPage;
            loadMoreBtn.dataset.totalComments = newLoadMoreBtn.dataset.totalComments;

            // Обновляем счётчик оставшихся комментариев
            const newRemainingSpan = newLoadMoreBtn.querySelector('.remaining-count');
            const oldRemainingSpan = loadMoreBtn.querySelector('.remaining-count');
            if (newRemainingSpan && oldRemainingSpan) {
                oldRemainingSpan.textContent = newRemainingSpan.textContent;
            }
        } else {
            loadMoreBtn.remove();
        }

        loadMoreBtn.innerHTML = oldButtonHtml;
        loadMoreBtn.disabled = false;
    } catch (error) {
        console.error('Ошибка загрузки комментариев:', error);
        loadMoreBtn.innerHTML = 'Ошибка, попробовать снова';
        loadMoreBtn.disabled = false;

        setTimeout(() => {
            loadMoreBtn.innerHTML = oldButtonHtml;
            loadMoreBtn.disabled = false;
        }, 3000);
    }
}

// Функция для инициализации рейтингов комментария
function initCommentRatings(commentElement) {
    const commentId = commentElement.dataset.commentId;
    const action = loadRatingState(commentId);

    if (!action) return;

    const likeBtn = commentElement.querySelector('.like-btn');
    const dislikeBtn = commentElement.querySelector('.dislike-btn');

    likeBtn?.classList.remove('active');
    dislikeBtn?.classList.remove('active');

    if (action === 'like' && likeBtn) {
        likeBtn.classList.add('active');
    } else if (action === 'dislike' && dislikeBtn) {
        dislikeBtn.classList.add('active');
    }
}

// Функция для загрузки состояния рейтинга из localStorage
function loadRatingState(commentId) {
    try {
        const ratings = JSON.parse(localStorage.getItem('commentRatings') || '{}');
        return ratings[commentId] || null;
    } catch (e) {
        console.error('Ошибка загрузки рейтинга:', e);
        return null;
    }
}
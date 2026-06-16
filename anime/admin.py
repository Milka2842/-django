from django.db import transaction
from yume import settings
from .models import Anime, logger, Screenshot, Franchise
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.utils.html import format_html
from django import forms
import concurrent.futures
import time
from django.db.models import Q


class AnimeAdminForm(forms.ModelForm):
    class Meta:
        model = Anime
        fields = '__all__'

    def save(self, commit=True):
        # Помечаем описание как ручное если оно было изменено
        if 'description' in self.changed_data:
            self.instance.description_manual = True
        return super().save(commit)


class ScreenshotInline(admin.TabularInline):
    model = Screenshot
    extra = 0
    readonly_fields = ['url']
    fields = ['url', 'order']
    ordering = ['order']


@admin.register(Anime)
class AnimeAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        "shikimori_id",
        'poster_preview',
        'poster_kodik',
        'year',
        'shikimori_rating',
        'season',
        'genres',
    )
    list_editable = ('year', 'poster_kodik')
    search_fields = ('title', 'shikimori_id')
    readonly_fields = ('shikimori_rating',)
    actions = ['update_data_action', 'index_selected_anime', 'update_selected_anime_data']
    form = AnimeAdminForm
    inlines = [ScreenshotInline]

    fieldsets = (
        (None, {
            'fields': ("shikimori_id",)
        }),
        ('Основные данные', {
            'fields': (
                'title',
                'description',
                'description_manual',
                'genres',
                'year',
                'season',
                "poster_kodik"
            ),
            'classes': ('collapse',)
        }),
        ('Франшиза', {
            'fields': ('franchise_code',),
            'description': 'Для объединения в серии. Формат: НазваниеБезПробеловЧисло (пример: AttackOnTitan3)'
        }),
    )

    def update_selected_anime_data(self, request, queryset):
        """Обновление данных для выбранных аниме"""
        from django.contrib import messages

        total = queryset.count()
        updated = []
        errors = []
        rating_updated = []
        start_time = time.time()

        # Используем ThreadPoolExecutor для параллельной обработки
        max_workers = min(10, total)  # Не более 10 потоков

        def update_single_anime(anime):
            try:
                import requests
                import logging
                logger = logging.getLogger(__name__)

                # Обновляем рейтинг
                rating_flag = anime.update_shikimori_rating(force=True)

                # Основные данные
                anime.get_data_from_shikimori()
                anime.update_from_kodik()
                anime.update_poster_from_kodik()

                # Сохраняем аниме
                with transaction.atomic():
                    anime.save()

                return anime, True, rating_flag, None
            except Exception as e:
                logger.error(f"Ошибка обновления аниме {anime.title}: {str(e)}", exc_info=True)
                return anime, False, False, str(e)

        # Для небольшого количества обрабатываем последовательно
        if total <= 5:
            for anime in queryset:
                try:
                    rating_flag = anime.update_shikimori_rating(force=True)
                    anime.get_data_from_shikimori()
                    anime.update_from_kodik()
                    anime.update_poster_from_kodik()

                    with transaction.atomic():
                        anime.save()

                    updated.append(anime.title)
                    if rating_flag:
                        rating_updated.append(anime.title)

                except Exception as e:
                    errors.append(f"{anime.title}: {str(e)}")
                    logger.error(f"Ошибка обновления: {str(e)}", exc_info=True)

                # Небольшая пауза между запросами
                time.sleep(0.5)
        else:
            # Для большого количества используем потоки
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Запускаем задачи
                future_to_anime = {
                    executor.submit(update_single_anime, anime): anime
                    for anime in queryset
                }

                # Обрабатываем результаты по мере готовности
                for future in concurrent.futures.as_completed(future_to_anime):
                    anime = future_to_anime[future]
                    try:
                        anime_obj, success, rating_flag, error = future.result(
                            timeout=60)  # Таймаут 60 секунд на задачу

                        if success:
                            updated.append(anime_obj.title)
                            if rating_flag:
                                rating_updated.append(anime_obj.title)
                        else:
                            errors.append(f"{anime.title}: {error}")

                    except concurrent.futures.TimeoutError:
                        errors.append(f"{anime.title}: Таймаут при обновлении")
                    except Exception as e:
                        errors.append(f"{anime.title}: {str(e)}")

        # Формируем сообщение
        elapsed_time = time.time() - start_time
        messages_list = []

        if updated:
            success_count = len(updated)
            messages_list.append(f"Успешно обновлено: {success_count} аниме")

        if rating_updated:
            messages_list.append(f"Рейтинг обновлен для: {len(rating_updated)} аниме")

        if errors:
            messages_list.append(f"Ошибки: {len(errors)} аниме (детали в логах)")

        messages_list.append(f"Время выполнения: {elapsed_time:.1f} секунд")

        # Показываем только первые 10 ошибок, чтобы не перегружать сообщение
        if errors and len(errors) > 10:
            error_display = errors[:10] + [f"... и еще {len(errors) - 10} ошибок"]
        else:
            error_display = errors

        if error_display:
            for error in error_display:
                logger.error(f"Ошибка обновления: {error}")

        # Показываем сообщение об успехе с предупреждением об ошибках
        if not errors:
            self.message_user(
                request,
                " | ".join(messages_list),
                messages.SUCCESS
            )
        elif updated:
            self.message_user(
                request,
                " | ".join(messages_list),
                messages.WARNING
            )
            self.message_user(
                request,
                "Первые ошибки: " + "; ".join(error_display),
                messages.ERROR
            )
        else:
            self.message_user(
                request,
                "Ошибки при обновлении: " + "; ".join(error_display),
                messages.ERROR
            )

    update_selected_anime_data.short_description = "🔄 Обновить все данные выбранных аниме"

    def update_data_action(self, request, queryset):
        """Быстрое обновление данных (для небольшого количества)"""
        updated = []
        errors = []
        rating_updated = []  # Для отслеживания успешных обновлений рейтинга

        for anime in queryset:
            try:
                # Принудительно обновляем рейтинг
                rating_updated_flag = anime.update_shikimori_rating(force=True)

                # Основные данные
                anime.get_data_from_shikimori()
                anime.update_from_kodik()
                anime.update_poster_from_kodik()

                anime.save()
                updated.append(anime.title)

                if rating_updated_flag:
                    rating_updated.append(anime.title)

            except Exception as e:
                errors.append(f"{anime.title}: {str(e)}")
                logger.error(f"Ошибка обновления: {str(e)}", exc_info=True)

        # Формируем сообщения
        messages_list = []
        if updated:
            messages_list.append(f"Обновлено: {', '.join(updated)}")
        if rating_updated:
            messages_list.append(f"Рейтинг обновлен: {', '.join(rating_updated)}")
        if errors:
            messages_list.append(f"Ошибки: {'; '.join(errors)}")

        self.message_user(request, " | ".join(messages_list), messages.SUCCESS if not errors else messages.ERROR)

    update_data_action.short_description = "⟳ Обновить данные (быстрое, до 10 аниме)"

    def response_change(self, request, obj):
        if "_update-dreamcast" in request.POST:
            try:
                obj.update_episodes()
                self.message_user(request, "Эпизоды обновлены!", messages.SUCCESS)
            except Exception as e:
                self.message_user(request, f"Ошибка: {str(e)}", messages.ERROR)
            return redirect(request.path)
        return super().response_change(request, obj)

    def save_model(self, request, obj, form, change):
        obj.save()

        if not change:
            self.message_user(
                request,
                "Аниме успешно создано и данные загружены",
                messages.SUCCESS
            )

    def description_short(self, obj):
        """Краткое описание для списка"""
        return obj.description[:50] + "..." if obj.description else ""

    description_short.short_description = "Описание"

    def poster_preview(self, obj):
        if obj.poster_kodik:
            return format_html(f'<img src="{obj.poster_kodik}" style="max-height: 100px;" />')
        return "Постер отсутствует"

    poster_preview.short_description = "Превью постера (Kodik/World Art)"


class FranchiseAdminForm(forms.ModelForm):
    anime_ids_display = forms.CharField(
        label="shikimori_id аниме (через запятую или многострочно)",
        widget=forms.Textarea(attrs={'rows': 6}),
        help_text="Укажите shikimori_id в нужном порядке. Каждый ID на новой строке или через запятую.",
        required=True
    )

    class Meta:
        model = Franchise
        fields = ('name', 'anime_ids_display')


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Преобразуем список ID в строку для отображения
            self.fields['anime_ids_display'].initial = '\n'.join(
                str(id) for id in self.instance.anime_ids
            )

    def clean_anime_ids_display(self):
        data = self.cleaned_data['anime_ids_display']
        if not data.strip():
            raise forms.ValidationError("Укажите хотя бы один shikimori_id")

        # Разбираем ввод (запятые или переводы строк)
        ids_str = data.replace(',', '\n')
        raw_ids = [id.strip() for id in ids_str.split('\n') if id.strip()]

        if not raw_ids:
            raise forms.ValidationError("Не удалось распарсить shikimori_id")

        # Приводим всё к строкам и убираем пробелы
        str_ids = [str(sid).strip() for sid in raw_ids]

        # Проверяем существование в БД одним запросом
        existing = set(Anime.objects.filter(shikimori_id__in=str_ids).values_list('shikimori_id', flat=True))
        existing_str = {str(eid).strip() for eid in existing}

        invalid = [sid for sid in str_ids if sid not in existing_str]
        if invalid:
            raise forms.ValidationError(
                f"Следующие shikimori_id не найдены в БД: {', '.join(invalid)}"
            )

        return str_ids

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Присваиваем значение из очищенного поля
        instance.anime_ids = self.cleaned_data['anime_ids_display']
        if commit:
            instance.save()
            self.save_m2m()  # если есть many-to-many поля, иначе можно без
        return instance

@admin.register(Franchise)
class FranchiseAdmin(admin.ModelAdmin):
    form = FranchiseAdminForm
    list_display = ('franchise_display', 'anime_count', 'updated_at')
    search_fields = ('name',)
    fieldsets = (
        (None, {
            'fields': ('name',),
            'description': 'Создание и редактирование франшизы'
        }),
        ('Информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')

    def change_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            obj = self.get_object(request, object_id)
            if obj:
                # Передаём объекты аниме в текущем порядке
                extra_context['anime_objects'] = obj.get_anime_objects()
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def franchise_display(self, obj):
        """Компактное отображение франшизы в списке (все постеры)"""
        if not obj.anime_ids:
            return format_html('<span style="color: red;">Пустая франшиза</span>')

        anime_objs = obj.get_anime_objects()
        html_parts = []

        for anime in anime_objs:
            if not anime.poster_kodik:
                continue
            # Формируем тултип с подробной информацией
            tooltip = f"{anime.title}\n"
            tooltip += f"Сезон: {anime.get_season_display()} {anime.year}\n"
            tooltip += f"Серий: {anime.total_episodes or '?'}"

            # Каждый постер с подписью ID под ним
            html_parts.append(
                f'<div style="display: inline-block; text-align: center; margin: 0 5px 5px 0; vertical-align: top;">'
                f'<img src="{anime.poster_kodik}" '
                f'style="height: 100px; border-radius: 4px; display: block;" '
                f'loading="lazy" '
                f'title="{tooltip}" />'
                f'<small style="color: #666;">#{anime.shikimori_id}</small>'
                f'</div>'
            )

        return format_html(''.join(html_parts) if html_parts else 'Нет постеров')

    franchise_display.short_description = "Франшиза"

    def anime_count(self, obj):
        """Количество аниме в франшизе"""
        return len(obj.anime_ids) if obj.anime_ids else 0
    anime_count.short_description = "Кол-во аниме"

    def franchise_posters_display(self, obj):
        """Полный предпросмотр всех постеров в форме редактирования (прозрачный фон, тултипы)"""
        if not obj.pk:
            return "Сохраните франшизу, чтобы увидеть постеры"

        anime_objs = obj.get_anime_objects()
        if not anime_objs:
            return format_html('<span style="color: red;">Нет доступных аниме</span>')

        html_parts = []
        for i, anime in enumerate(anime_objs):
            if not anime.poster_kodik:
                continue
            # Тултип с той же информацией
            tooltip = f"{anime.title}\n"
            tooltip += f"Сезон: {anime.get_season_display()} {anime.year}\n"
            tooltip += f"Серий: {anime.total_episodes or '?'}"

            html_parts.append(f'''
                <div style="display: inline-block; margin: 10px; text-align: center; vertical-align: top;">
                    <div style="position: relative;">
                        <img src="{anime.poster_kodik}" 
                             style="height: 150px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);"
                             loading="lazy"
                             title="{tooltip}"
                             alt="{anime.title}" />
                    </div>
                    <div style="margin-top: 5px; font-size: 12px;">
                        <span style="color: #999;">Сезон {i + 1}</span><br/>
                        <span style="color: #666;">
                            {anime.year or '?'} {anime.get_season_display() or '?'}
                        </span><br/>
                        <span style="color: #666;">
                            Эпизодов: {anime.total_episodes or '?'}
                        </span><br/>
                        <small>#{anime.shikimori_id}</small>
                    </div>
                </div>
            ''')

        # Убрали белый фон, оставили только контейнер без фона
        return format_html(
            f'<div style="padding: 20px;">'
            f'{"".join(html_parts)}'
            f'</div>'
        )

    franchise_posters_display.short_description = "Постеры франшизы"

    def get_search_results(self, request, queryset, search_term):
        # Стандартный поиск по полю name (если указано в search_fields)
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        if search_term:
            term = search_term.strip()

            # 1. Поиск по ID в массиве anime_ids (точное совпадение)
            # Пробуем и как строку, и как число (на случай, если где-то остались числа)
            id_conditions = Q(anime_ids__contains=[term])
            try:
                int_term = int(term)
                id_conditions |= Q(anime_ids__contains=[int_term])
            except ValueError:
                pass

            # 2. Поиск по названиям аниме, входящих во франшизу
            # Находим все ID аниме, чьё название содержит термин
            matching_ids = Anime.objects.filter(
                title__icontains=term
            ).values_list('shikimori_id', flat=True)

            # Преобразуем найденные ID в строки
            str_ids = [str(x) for x in matching_ids]

            # Добавляем условие, если есть совпадения
            if str_ids:
                # Используем overlap для поиска любого совпадения в массиве
                id_conditions |= Q(anime_ids__overlap=str_ids)

            # Применяем все условия
            queryset |= self.model.objects.filter(id_conditions)
            use_distinct = True

        return queryset, use_distinct









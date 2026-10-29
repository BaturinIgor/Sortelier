# Как моделировать новые продукты Sortelier

Продукты и блюда - процедурные модели Blender в стиле мягких глянцевых 3D-иконок (как в топовых goods sort играх).
Образец стиля: `Sortelier/Resources/Sprites/*.png` (например `grapes.png`, `gelato.png`, `tomato.png`, `espresso.png`,
`dish_pizza.png`, `dish_pasta.png`, `dish_ramen.png`).

## Устройство

- Помощники и примеры - в `tools/render/models.py`: меши (`sphere`, `lathe`, `capsule`, `cylinder`, `torus`,
  `polar_disc`, `profile_prism`, `box_mesh`, `tube`), обработка (`subdivide`, `bevel`, `smooth`, `deform`,
  `push_normals`, `bend`, `bisect`, `boolean_cut`, `place`, `apply_transform`, `rotate_all`, `stack`),
  материалы (`material` с градиентом по оси, `flat`, `add_speckles`, `add_stripes`), россыпь деталей (`scatter_on`),
  подача (`plate`, `wooden_board`). Хорошие примеры: `tomato`, `grapes`, `gelato`, `tiramisu`, `espresso`, `olives`,
  `juice`, `dish_pasta`, `dish_caprese`, `dish_ramen`, `dish_sushi`.
- Новые модели живут в своих модулях `tools/render/models_<группа>.py`:

  ```python
  import models as M
  from models import *  # noqa: F401,F403  помощники

  def lime():
      ...
      return [obj1, obj2]

  M.MODELS.update({"lime": lime, "dish_taco": dish_taco})
  ```

  Функция возвращает список объектов. Камера ортографическая, смотрит спереди (со стороны -Y) чуть справа
  (14 градусов) и сверху (26 градусов), кадр подгоняется по границам модели сам. Блюда (`dish_*`) рендерятся крупнее
  и потом крутятся на 360 градусов в анимации открытия, поэтому должны хорошо смотреться со всех сторон.

## Рендер и проверка

- Черновик: `/home/claude/venv-blender/bin/python tools/render/models.py art/new/<группа> --only a,b --size 300 --samples 40`
- Лист для проверки: `python3 tools/render/sheet.py art/new/<группа>_sheet.png art/new/<группа>` и посмотреть картинку.
  Рядом полезно положить пару готовых спрайтов из `Sortelier/Resources/Sprites` для сравнения стиля.
- Чистовой рендер (без `--size` и `--samples`) - когда модель готова. Анимацию вращения (`--spin`) не делать.

## Что считается хорошим результатом

- Продукт узнается с первого взгляда в размере 60-80 точек на телефоне: ясный силуэт, 1-3 главных цвета,
  крупные формы, мелкие детали только как фактура.
- Глянцевый мягкий пластилин: скругленные края (bevel/subdivide), градиент в материале, лак (coat), где уместно
  подповерхностное рассеяние (фрукты, тесто, крем). Никаких плоских серых участков и пересечений, торчащих сквозь
  поверхность.
- Цвета сочные, но не неоновые, как у соседних продуктов в игре.
- Предметы, которые заказывают тройками, должны отличаться от уже существующих продуктов игры по силуэту и цвету.

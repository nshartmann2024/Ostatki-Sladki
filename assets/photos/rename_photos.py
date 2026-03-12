"""Одноразовый скрипт: переименовать файлы фото. Запуск из корня проекта: python assets/photos/rename_photos.py"""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
RENAMES = [
    ("brotauflauf mit kaese.jpg", "brotauflauf_kaese.jpg"),
    ("erdaepfelgulash.jpg", "erdaepfelgulasch.jpg"),
    ("kekse aus altem brot.jpg", "kekse_altes_brot.jpg"),
]
for old_name, new_name in RENAMES:
    old_path = os.path.join(ROOT, old_name)
    new_path = os.path.join(ROOT, new_name)
    if os.path.isfile(old_path):
        os.rename(old_path, new_path)
        print("Renamed:", old_name, "->", new_name)
    else:
        print("Skip (not found):", old_name)

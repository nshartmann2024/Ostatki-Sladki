"""
Временный скрипт проверки рецептов в БД после пересоздания.
Запуск из корня: python db/check_recipes.py
"""
import json
import os
import sys
import sqlite3

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(SCRIPT_DIR, "app.db")

NEW_IDS = [
    "erdaepfelrahmsuppe_v1",
    "zwiebelrahmsuppe_v1",
    "kraut_schinken_fleckerl_v1",
    "reisfleisch_v1",
    "krautsuppe_v1",
    "schwammerlsuppe_v1",
    "gefuellte_champignons_v1",
    "erdaepfel_vogerlsalat_v1",
]

EXPECTED_DIFFICULTY = ("Просто", "Средне", "Сложно")
EXPECTED_PHOTO = {
    "kraut_schinken_fleckerl_v1": "assets/photos/krautfleckerl.jpg",
    "erdaepfel_vogerlsalat_v1": "assets/photos/erdaepfel_vogel_salat.jpg",
}


def main():
    if not os.path.isfile(DB_PATH):
        print("ERROR: db/app.db not found. Run init_db.py first.")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # a) общее число рецептов
    cur.execute("SELECT COUNT(*) FROM recipes")
    total = cur.fetchone()[0]
    print("a) Всего рецептов:", total)
    if total != 18:
        print("   ОЖИДАЛОСЬ: 18")
    print()

    # b) список id+title для 8 новых
    print("b) 8 новых рецептов (id, title_de — title_ru):")
    found = []
    for rid in NEW_IDS:
        cur.execute(
            "SELECT id, title_de, title_ru, photo_url, difficulty, must_have_json FROM recipes WHERE id = ?",
            (rid,),
        )
        row = cur.fetchone()
        if row:
            found.append(row)
            title = f"{row['title_de']} — {row['title_ru']}"
            print(f"   {row['id']}: {title}")
        else:
            print(f"   {rid}: НЕ НАЙДЕН")
    print()

    # c) для каждого из 8: photo_url, difficulty, must_have_json
    print("c) photo_url, difficulty, must_have_json для каждого из 8:")
    photo_mismatch = []
    for row in found:
        rid = row["id"]
        photo_url = row["photo_url"] or "(null)"
        difficulty = row["difficulty"] or ""
        must = row["must_have_json"] or "[]"
        try:
            must_list = json.loads(must)
        except Exception:
            must_list = []
        print(f"   {rid}:")
        print(f"     photo_url: {photo_url}")
        print(f"     difficulty: {difficulty}")
        print(f"     must_have_json: {must_list}")

        if difficulty and difficulty not in EXPECTED_DIFFICULTY:
            print(f"     ВНИМАНИЕ: difficulty не из списка Просто/Средне/Сложно")

        if rid in EXPECTED_PHOTO and (row["photo_url"] or "") != EXPECTED_PHOTO[rid]:
            print(f"     ВНИМАНИЕ: ожидался photo_url {EXPECTED_PHOTO[rid]}")

        # Проверка существования файла
        if row["photo_url"]:
            path = os.path.join(ROOT, row["photo_url"])
            if not os.path.isfile(path):
                photo_mismatch.append((rid, row["photo_url"], path))
        print()
    conn.close()

    # Фактические файлы в assets/photos
    photos_dir = os.path.join(ROOT, "assets", "photos")
    if os.path.isdir(photos_dir):
        files = [f for f in os.listdir(photos_dir) if not f.startswith(".") and f.endswith((".jpg", ".jpeg", ".png"))]
        print("Файлы в assets/photos:", files or "(нет изображений)")
    else:
        print("Папка assets/photos не найдена.")

    if photo_mismatch:
        print()
        print("НЕСОВПАДЕНИЕ photo_url с файлами:")
        for rid, url, path in photo_mismatch:
            print(f"  {rid}: url={url}, путь не найден: {path}")
        print("Рекомендация: привести photo_url в seed к именам файлов в assets/photos.")
    else:
        print()
        print("Все photo_url в БД соответствуют существующим файлам (или null).")


if __name__ == "__main__":
    main()

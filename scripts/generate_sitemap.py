"""
Генерация статического sitemap.xml для проекта «Остатки Сладки».
Запуск из корня: python scripts/generate_sitemap.py
Файл создаётся в корне проекта (sitemap.xml). Для Streamlit Cloud sitemap доступен по ?sitemap=1.
"""
import html
import os
import sys

# Только ингредиенты с рабочими SEO-страницами (без лук, чеснок)
SITEMAP_INGREDIENTS = [
    "банан",
    "картофель",
    "картофель-быстро",
    "рис",
    "сыр",
    "творог",
    "хлеб",
    "черствый-хлеб",
    "яблоко",
]

SITEMAP_BASE_URL = os.environ.get("SITEMAP_BASE_URL", "https://your-app.streamlit.app").rstrip("/")


def build_sitemap_xml(base_url: str) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f"  <url><loc>{base_url}/</loc></url>",
    ]
    for slug in sorted(SITEMAP_INGREDIENTS):
        lines.append(f'  <url><loc>{base_url}/?ingredient={html.escape(slug)}</loc></url>')
    lines.append("</urlset>")
    return "\n".join(lines)


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(root, "sitemap.xml")
    xml = build_sitemap_xml(SITEMAP_BASE_URL)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"Written: {out_path}")
    print(f"Base URL: {SITEMAP_BASE_URL}")
    print(f"URLs: 1 main + {len(SITEMAP_INGREDIENTS)} ingredients = {1 + len(SITEMAP_INGREDIENTS)} total")


if __name__ == "__main__":
    main()
    sys.exit(0)

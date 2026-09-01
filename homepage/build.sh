#!/bin/bash
set -e
python3 ../admin/generator.py
mkdir -p admin
cp ../admin/static/index.html admin/index.html
cp ../admin/static/login.html admin/login.html
cp ../admin/static/admin.js admin.js
cp ../admin/static/admin.css admin.css
cp ../admin/static/icons-data.js icons-data.js
mkdir -p api/_seed
cp ../admin/content/*.json api/_seed/

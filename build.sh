#!/bin/bash
set -o errexit

# Устанавливаем системные зависимости
apt-get update
apt-get install -y libxml2-dev libxslt-dev python3-dev

# Устанавливаем Python-зависимости
pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

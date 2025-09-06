#!/bin/bash

# ไปยังโฟลเดอร์ project
cd /home/backend/thepixstock-api || exit

# ตั้งข้อความ commit อัตโนมัติ (แก้ไขได้)
COMMIT_MSG="Auto commit $(date '+%Y-%m-%d %H:%M:%S')"

# ดึงการเปลี่ยนแปลงล่าสุดจาก remote
git fetch origin main

# เช็คว่า local มีการแก้ไขหรือไม่
if [[ -n $(git status --porcelain) ]]; then
    echo "Staging changes..."
    git add .

    echo "Committing changes..."
    git commit -m "$COMMIT_MSG"
else
    echo "No changes to commit."
fi

# Rebase เพื่อดึง commit ล่าสุดจาก remote
git pull origin main --rebase

# Push ขึ้น remote
git push origin main

echo "Done!"

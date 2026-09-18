import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Менеджеры магазина. Можно указать несколько через запятую.
MANAGER_USERNAMES = {
    username.strip().lstrip("@").lower()
    for username in os.getenv("MANAGER_USERNAMES", "devarapq,fishlme").split(",")
    if username.strip()
}

# Для обратной совместимости оставляем основной контакт.
MANAGER_USERNAME = os.getenv("MANAGER_USERNAME", "devarapq")

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
ADMIN_CHAT_IDS = [
    int(value.strip())
    for value in os.getenv("ADMIN_CHAT_IDS", "").split(",")
    if value.strip().lstrip("-").isdigit()
]
if ADMIN_CHAT_ID and ADMIN_CHAT_ID not in ADMIN_CHAT_IDS:
    ADMIN_CHAT_IDS.insert(0, ADMIN_CHAT_ID)

SHOP_NAME = "Fishl Shop"

# GitHub backups. Token is stored only in Railway Variables, never in GitHub.
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")
GITHUB_BACKUP_BRANCH = os.getenv("GITHUB_BACKUP_BRANCH", "backups")
GITHUB_BACKUP_PATH = os.getenv("GITHUB_BACKUP_PATH", "backups/orders")
GITHUB_BACKUP_INTERVAL_MINUTES = int(os.getenv("GITHUB_BACKUP_INTERVAL_MINUTES", "360"))

import os

files_to_check = [
    'dashboard.py',
    'components/tab_overview.py',
    'components/tab_analytics.py',
    'components/tab_forensics.py',
    'components/tab_customer360.py'
]

emojis = [
    '⚡ ', '🔒 ', '⛔ ', '⚙️ ', '🏢 ', '⚠️ ', '📱 ', '📡 ', '📥 ', 
    '📊  ', '💸  ', '🔍  ', '👤  ', '🔥 ', '✅ ', '↑ ', '🔬 ', 
    '📉 ', '🚨 ', '📜 ', '📩 ', '🔎 ', '⚡'
]

for filepath in files_to_check:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for emoji in emojis:
        content = content.replace(emoji, '')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print('Emojis removed successfully.')

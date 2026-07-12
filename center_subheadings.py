import glob
import re

files = glob.glob('dashboard.py') + glob.glob('components/*.py')
for file in files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()

    def replacer(match):
        indent = match.group(1)
        text = match.group(2)
        # Skip if it's already HTML or contains headers or if it's a line rule
        if '<' in text or '---' in text or '#' in text or 'text-align' in text or 'unsafe_allow_html' in text:
            return match.group(0)
        
        # Replace Markdown with HTML
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
        text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
        
        return f'{indent}st.markdown("<p style=\'text-align: center; color: #A1A1AA;\'>{text}</p>", unsafe_allow_html=True)'

    new_content = re.sub(r'^(\s*)st\.markdown\([\'"]([^\'"]+)[\'"]\)', replacer, content, flags=re.MULTILINE)
    
    if new_content != content:
        with open(file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated {file}')

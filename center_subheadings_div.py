import glob

files = glob.glob('dashboard.py') + glob.glob('components/*.py')
for file in files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content.replace("<p style='text-align: center; color: #A1A1AA;'>", "<div class='centered-subheading'>")
    new_content = new_content.replace("</p>\", unsafe_allow_html=True)", "</div>\", unsafe_allow_html=True)")
    new_content = new_content.replace("</p>', unsafe_allow_html=True)", "</div>', unsafe_allow_html=True)")

    if new_content != content:
        with open(file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated {file}')

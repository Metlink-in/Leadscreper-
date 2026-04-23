import os

favicon_html = '\n  <link rel="icon" href="data:image/svg+xml,<svg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 100 100\'><rect width=\'100\' height=\'100\' rx=\'20\' fill=\'%2300ffa3\'/><text x=\'50%\' y=\'65%\' font-family=\'Arial, sans-serif\' font-size=\'50\' font-weight=\'bold\' fill=\'%23000\' text-anchor=\'middle\'>LI</text></svg>" type="image/svg+xml">\n</head>'
template_dir = r"E:\Leadscraper\Leadscraper\app\templates"

for filename in os.listdir(template_dir):
    if filename.endswith('.html'):
        filepath = os.path.join(template_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'rel="icon"' not in content:
            content = content.replace('</head>', favicon_html)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

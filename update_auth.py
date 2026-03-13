import re

auth_file_path = r'F:\python\新建文件夹 (5)\tonyoudianshangpingtai\services\auth_service.py'

with open(auth_file_path, 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(
    r'"token": token,(\s*)}',
    r'"token": token,\1"role": user.role,\1}',
    text
)

with open(auth_file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Auth service updated")

import re

path = r'F:\python\新建文件夹 (5)\tonyoudianshangpingtai\api\admin_routes.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'require_admin,\s*require_admin.*', 'require_admin', text)

old_str = 'router = APIRouter(prefix="/admin", tags=["管理员管理"])'
new_str = 'router = APIRouter(prefix="/admin", tags=["管理员管理"], dependencies=[Depends(require_admin)])'
if 'dependencies' not in text:
    text = text.replace(old_str, new_str)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print("success")

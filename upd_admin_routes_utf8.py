
path = r'F:\python\新建文件夹 (5)\tonyoudianshangpingtai\api\admin_routes.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('from api.auth_routes import require_root, get_current_user_obj,require_merchant', 'from api.auth_routes import require_root, get_current_user_obj,require_merchant, require_admin')

text = text.replace('router = APIRouter(prefix=\
/admin\, tags=[\管理员管理\])', 'router = APIRouter(prefix=\/admin\, tags=[\管理员管理\], dependencies=[Depends(require_admin)])')

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)


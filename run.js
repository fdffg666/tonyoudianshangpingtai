
const fs = require('fs');
const file = 'F:/python/新建文件夹 (5)/tonyoudianshangpingtai/api/admin_routes.py';
let text = fs.readFileSync(file, 'utf-8');

text = text.replace(/from api\.auth_routes import require_root.*/g, 'from api.auth_routes import require_root, get_current_user_obj, require_merchant, require_admin');

text = text.replace(/router = APIRouter\(prefix=\
\/admin\, tags=\[\管理员管理\\]\)/g, 'router = APIRouter(prefix=\/admin\, tags=[\管理员管理\], dependencies=[Depends(require_admin)])');

fs.writeFileSync(file, text, 'utf-8');


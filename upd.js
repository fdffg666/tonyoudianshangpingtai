
const fs = require('fs');
const path1 = 'c:/Users/时柒/Desktop/my-login-app/src/components/Orders.vue';
const path2 = 'c:/Users/时柒/Desktop/my-login-app/src/components/OrderDetail.vue';
const path3 = 'c:/Users/时柒/Desktop/my-login-app/src/components/AdminOrders.vue';

const dictStr = '{\n  \'pending\': \'待处理\',\n  \'confirmed\': \'已确认\',\n  \'processing\': \'处理中\',\n  \'shipped\': \'已发货\',\n  \'completed\': \'已完成\',\n  \'cancelled\': \'已取消\'\n}';

// 1. Update Orders.vue
let c1 = fs.readFileSync(path1, 'utf-8');
c1 = c1.replace('<div>状态：{{ order.status }}</div>', '<div>状态：{{ statusMap[order.status] || order.status }}</div>');
if (!c1.includes('const statusMap')) {
  c1 = c1.replace('import { getOrderList } from \'../utils/api\'', 'import { getOrderList } from \'../utils/api\'\n\nconst statusMap = ' + dictStr + ';');
}
fs.writeFileSync(path1, c1, 'utf-8');

// 2. Update OrderDetail.vue
let c2 = fs.readFileSync(path2, 'utf-8');
c2 = c2.replace(/const statusText = {[\s\S]*?}/, 'const statusText = ' + dictStr);
fs.writeFileSync(path2, c2, 'utf-8');

// 3. Update AdminOrders.vue
let c3 = fs.readFileSync(path3, 'utf-8');
c3 = c3.replace(/const statusMap = {[\s\S]*?}/, 'const statusMap = ' + dictStr);
c3 = c3.replace('<p>状态：{{ order.status }}</p>', '<p>状态：{{ statusMap[order.status] || order.status }}</p>');
fs.writeFileSync(path3, c3, 'utf-8');

console.log('Update complete');


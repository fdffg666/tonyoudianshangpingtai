
const fs = require('fs');
const path = 'c:/Users/时柒/Desktop/my-login-app/src/components/OrderDetail.vue';
let content = fs.readFileSync(path, 'utf-8');
const widget = \      <!-- 微信信息 -->
      <div v-if=\
order.assigned_wechat\ class=\section
wechat-info\>
         请添加微信：<strong>{{ order.assigned_wechat }}</strong> 备注\下单\完成支付
      </div>

      <!-- 操作按钮 -->\;
content = content.replace('      <!-- 操作按钮 -->', widget);
content = content + '\n<style scoped>\n.wechat-info { background: #e6f4ea; color: #1e8e3e; border: 1px solid #cce8d6; text-align: center; font-size: 16px; padding: 16px; }\n.wechat-info strong { font-size: 18px; user-select: all; }\n</style>';
fs.writeFileSync(path, content, 'utf-8');


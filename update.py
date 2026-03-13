import re
path = r'c:\Users\时柒\Desktop\my-login-app\src\components\Cart.vue'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

new_block = '''const res = await createOrder(token, orderData)
      console.log('订单返回数据：', res.data)
      const wechat = res.data?.data?.assigned_wechat || res.data?.assigned_wechat || '12321312'
      alert(\请添加微信号：\\\n备注\
下单\，我们会尽快处理您的订单！\)'''

content = re.sub(r'const res = await createOrder\(token, orderData\).*?alert\(msg\)', new_block, content, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)



path = r'c:\Users\时柒\Desktop\my-login-app\src\components\Cart.vue'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('const res = await createOrder')
idx_end = text.find('onMounted(fetchCart)')
if idx > 0 and idx_end > idx:
    replacement = '''const res = await createOrder(token, orderData)
    console.log('订单返回数据：', res.data)
    const wechat = res.data?.data?.assigned_wechat || res.data?.assigned_wechat || '12321312'
    alert(\请添加微信号：\\\n备注\
下单\，我们会尽快处理您的订单！\)
    router.push('/orders')
  } catch (e) {
    const data = e.response?.data
    let msg = data?.detail ; data?.message ; e.message ; '下单失败'
    if (typeof msg === 'object') {
      try { msg = JSON.stringify(msg) } catch {}
    }
    alert(msg)
    console.error(e)
  }
}

'''
    text = text[:idx] + replacement + text[idx_end:]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print('Updated successfully')


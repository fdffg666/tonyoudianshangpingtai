import re

path = r'c:\Users\时柒\Desktop\my-login-app\src\components\Login.vue'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    "localStorage.setItem('token', res.data.data.token)",
    "localStorage.setItem('token', res.data.data.token)\n      localStorage.setItem('role', res.data.data.role)"
)

text = text.replace(
    "localStorage.setItem('token', data.data.token)",
    "localStorage.setItem('token', data.data.token)\n      localStorage.setItem('role', data.data.role)"
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print("done")

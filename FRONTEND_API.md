# 前端对接API文档

## 基础信息

- **Base URL**: `http://localhost:8000`
- **认证方式**: Bearer Token (JWT)
- **Content-Type**: `application/json`

## 认证说明

### 1. 获取Token

所有需要认证的接口都需要在请求头中携带Token：

```
Authorization: Bearer <your_token>
```

### 2. 用户角色

- **普通用户**: 可以浏览商品、添加购物车、创建订单
- **商家**: 可以管理商品、查看订单、更新订单状态
- **管理员**: 拥有所有权限

---

## API接口列表

## 1. 认证模块 (`/auth`)

### 1.1 账号密码注册

**接口**: `POST /auth/register/password`

**请求参数**:
```json
{
  "phone_number": "13800138000",
  "password": "123456",
  "nickname": "张三"
}
```

**响应**:
```json
{
  "success": true,
  "message": "注册成功",
  "data": {
    "user_id": 1,
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

### 1.2 账号密码登录

**接口**: `POST /auth/login/password`

**请求参数**:
```json
{
  "phone_number": "13800138000",
  "password": "123456"
}
```

**响应**:
```json
{
  "success": true,
  "message": "登录成功",
  "data": {
    "user_id": 1,
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "phone": "13800138000",
    "role": "user"
  }
}
```

### 1.3 获取当前用户信息

**接口**: `GET /auth/profile`

**请求头**: 需要携带Token

**响应**:
```json
{
  "user": {
    "id": 1,
    "phone": "13800138000",
    "role": "user",
    "nickname": "张三",
    "status": "active",
    "points": 0
  }
}
```

### 1.4 商家注册

**接口**: `POST /auth/register/merchant`

**请求参数**:
```json
{
  "username": "merchant001",
  "password": "123456",
  "wechat_id": "wx123456",
  "invite_code": "INVITE123"
}
```

**响应**:
```json
{
  "success": true,
  "message": "注册成功",
  "data": {
    "user_id": 2
  }
}
```

### 1.5 短信验证码登录

**发送验证码**: `POST /auth/sms/send`
```json
{
  "phone_number": "13800138000",
  "scene": "login"
}
```

**验证码登录**: `POST /auth/login/sms`
```json
{
  "phone_number": "13800138000",
  "code": "123456",
  "scene": "login"
}
```

---

## 2. 商品管理模块 (`/products`)

### 2.1 创建商品 (商家权限)

**接口**: `POST /products`

**请求头**: 需要携带Token

**请求参数**:
```json
{
  "name": "钨钢刀具",
  "price": 199.99,
  "description": "高品质钨钢刀具",
  "cost_price": 150.00,
  "image_url": "/static/image1.png",
  "category": "刀具",
  "sku_id": "SKU001",
  "initial_stock": 100
}
```

**响应**:
```json
{
  "success": true,
  "message": "创建商品成功",
  "data": {
    "id": 1,
    "name": "钨钢刀具",
    "price": 199.99,
    "sku_id": "SKU001"
  }
}
```

### 2.2 获取商品详情

**接口**: `GET /products/{product_id}`

**请求头**: 需要携带Token

**响应**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "id": 1,
    "name": "钨钢刀具",
    "price": 199.99,
    "description": "高品质钨钢刀具",
    "image_url": "/static/image1.png",
    "category": "刀具",
    "sku_id": "SKU001",
    "status": 1,
    "created_at": "2026-03-17T10:00:00"
  }
}
```

### 2.3 获取商品列表

**接口**: `GET /products`

**请求头**: 需要携带Token

**查询参数**:
- `page`: 页码 (默认1)
- `page_size`: 每页数量 (默认20，最大100)
- `category`: 分类筛选 (可选)
- `status`: 状态筛选 (可选)
- `keyword`: 关键词搜索 (可选)

**响应**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "list": [
      {
        "id": 1,
        "name": "钨钢刀具",
        "price": 199.99,
        "image_url": "/static/image1.png"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 100,
      "total_pages": 5
    }
  }
}
```

### 2.4 更新商品 (商家权限)

**接口**: `PUT /products/{product_id}`

**请求头**: 需要携带Token

**请求参数**:
```json
{
  "name": "钨钢刀具升级版",
  "price": 299.99,
  "status": 1
}
```

**响应**:
```json
{
  "success": true,
  "message": "更新成功"
}
```

### 2.5 删除商品 (商家权限)

**接口**: `DELETE /products/{product_id}`

**请求头**: 需要携带Token

**响应**:
```json
{
  "success": true,
  "message": "删除成功"
}
```

---

## 3. 购物车模块 (`/cart`)

### 3.1 添加商品到购物车

**接口**: `POST /cart/items`

**请求头**: 需要携带Token

**请求参数**:
```json
{
  "product_id": 1,
  "quantity": 2
}
```

**响应**:
```json
{
  "success": true,
  "message": "添加成功",
  "data": {
    "cart_id": 1,
    "product_id": 1,
    "quantity": 2,
    "price": 199.99,
    "subtotal": 399.98
  }
}
```

### 3.2 获取购物车

**接口**: `GET /cart`

**请求头**: 需要携带Token

**响应**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "items": [
      {
        "cart_id": 1,
        "product_id": 1,
        "name": "钨钢刀具",
        "quantity": 2,
        "price": 199.99,
        "subtotal": 399.98,
        "image_url": "/static/image1.png"
      }
    ],
    "total_amount": 399.98,
    "total_quantity": 2
  }
}
```

### 3.3 更新购物车商品数量

**接口**: `PUT /cart/items/{item_id}`

**请求头**: 需要携带Token

**请求参数**:
```json
{
  "quantity": 3
}
```

**响应**:
```json
{
  "success": true,
  "message": "更新成功"
}
```

### 3.4 删除购物车商品

**接口**: `DELETE /cart/items/{item_id}`

**请求头**: 需要携带Token

**响应**:
```json
{
  "success": true,
  "message": "删除成功"
}
```

### 3.5 清空购物车

**接口**: `DELETE /cart`

**请求头**: 需要携带Token

**响应**:
```json
{
  "success": true,
  "message": "清空成功"
}
```

---

## 4. 订单管理模块 (`/orders`)

### 4.1 创建订单

**接口**: `POST /orders`

**请求头**: 需要携带Token

**请求参数**:
```json
{
  "items": [
    {
      "product_id": 1,
      "quantity": 2
    }
  ],
  "expected_delivery_date": "2026-03-20",
  "remark": "请尽快发货"
}
```

**响应**:
```json
{
  "success": true,
  "message": "创建订单成功",
  "data": {
    "order_id": 1,
    "order_no": "ORD2026031710001",
    "total_amount": 399.98,
    "status": "pending",
    "items": [
      {
        "product_id": 1,
        "name": "钨钢刀具",
        "quantity": 2,
        "price": 199.99,
        "subtotal": 399.98
      }
    ]
  }
}
```

### 4.2 获取订单列表

**接口**: `GET /orders`

**请求头**: 需要携带Token

**查询参数**:
- `status`: 订单状态筛选 (可选)
- `page`: 页码 (默认1)
- `page_size`: 每页数量 (默认20，最大100)

**响应**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "list": [
      {
        "order_id": 1,
        "order_no": "ORD2026031710001",
        "total_amount": 399.98,
        "status": "pending",
        "created_at": "2026-03-17T10:00:00"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 10,
      "total_pages": 1
    }
  }
}
```

### 4.3 获取订单详情

**接口**: `GET /orders/{order_id}`

**请求头**: 需要携带Token

**响应**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "order_id": 1,
    "order_no": "ORD2026031710001",
    "user_id": 1,
    "total_amount": 399.98,
    "status": "pending",
    "expected_delivery_date": "2026-03-20",
    "remark": "请尽快发货",
    "items": [
      {
        "product_id": 1,
        "name": "钨钢刀具",
        "quantity": 2,
        "price": 199.99,
        "subtotal": 399.98
      }
    ],
    "created_at": "2026-03-17T10:00:00"
  }
}
```

### 4.4 取消订单

**接口**: `POST /orders/{order_id}/cancel`

**请求头**: 需要携带Token

**响应**:
```json
{
  "success": true,
  "message": "订单已取消"
}
```

### 4.5 更新订单状态 (商家权限)

**接口**: `PUT /orders/{order_id}/status`

**请求头**: 需要携带Token

**请求参数**:
```json
{
  "status": "confirmed"
}
```

**状态值**: `pending`, `confirmed`, `shipped`, `completed`, `cancelled`

**响应**:
```json
{
  "success": true,
  "message": "订单状态已更新"
}
```

---

## 5. 支付模块 (`/payments`)

### 5.1 创建支付订单

**接口**: `POST /payments/native`

**请求头**: 需要携带Token

**请求参数**:
```json
{
  "order_id": 1
}
```

**响应**:
```json
{
  "success": true,
  "message": "创建支付订单成功",
  "data": {
    "code_url": "wechat://addfriend/CustomerService123",
    "out_trade_no": "ORD2026031710001",
    "expire_at": "2026-03-18T10:00:00",
    "customer_service_wechat": "CustomerService123",
    "message": "请添加客服微信进行支付"
  }
}
```

**说明**: 
- 系统使用客服微信号支付方式
- 前端需要显示客服微信号和添加按钮
- 用户添加客服微信后，通过微信转账完成支付

### 5.2 查询支付结果

**接口**: `GET /payments/{order_id}`

**请求头**: 需要携带Token

**响应**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "out_trade_no": "ORD2026031710001",
    "trade_state": "NOTPAY",
    "pay_amount": 399.98,
    "time_paid": null,
    "customer_service_wechat": "CustomerService123",
    "message": "请添加客服微信进行支付"
  }
}
```

**支付状态**:
- `NOTPAY`: 未支付
- `SUCCESS`: 已支付
- `CLOSED`: 已关闭
- `REFUND`: 已退款

---

## 6. 库存管理模块 (`/inventory`)

### 6.1 初始化库存 (商家权限)

**接口**: `POST /inventory/init`

**请求头**: 需要携带Token

**请求参数**:
```json
{
  "sku_id": "SKU001",
  "total_stock": 100,
  "force": false
}
```

**响应**:
```json
{
  "success": true,
  "message": "SKU SKU001 库存初始化成功",
  "data": {
    "sku_id": "SKU001",
    "total_stock": 100,
    "available_stock": 100,
    "locked_stock": 0
  }
}
```

### 6.2 锁定库存

**接口**: `POST /inventory/lock`

**请求头**: 需要携带Token

**请求参数**:
```json
{
  "sku_id": "SKU001",
  "lock_num": 2,
  "order_id": "ORD2026031710001",
  "lock_timeout": 30
}
```

**响应**:
```json
{
  "success": true,
  "message": "锁定库存2件成功",
  "data": {
    "sku_id": "SKU001",
    "available_stock": 98,
    "locked_stock": 2
  }
}
```

### 6.3 释放库存

**接口**: `POST /inventory/release`

**请求头**: 需要携带Token

**请求参数**:
```json
{
  "sku_id": "SKU001",
  "lock_num": 2,
  "order_id": "ORD2026031710001",
  "lock_timeout": 30
}
```

**响应**:
```json
{
  "success": true,
  "message": "释放库存2件成功",
  "data": {
    "sku_id": "SKU001",
    "available_stock": 100,
    "locked_stock": 0
  }
}
```

### 6.4 扣减库存 (商家权限)

**接口**: `POST /inventory/deduct`

**请求头**: 需要携带Token

**请求参数**:
```json
{
  "sku_id": "SKU001",
  "deduct_num": 2,
  "order_id": "ORD2026031710001",
  "lock_timeout": 30
}
```

**响应**:
```json
{
  "success": true,
  "message": "扣减总库存2件成功",
  "data": {
    "sku_id": "SKU001",
    "total_stock": 98,
    "available_stock": 98,
    "locked_stock": 0
  }
}
```

### 6.5 查询库存

**接口**: `GET /inventory/query/{sku_id}`

**请求头**: 需要携带Token

**响应**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "sku_id": "SKU001",
    "total_stock": 100,
    "available_stock": 98,
    "locked_stock": 2,
    "version": 1
  }
}
```

### 6.6 查询所有库存

**接口**: `GET /inventory/query`

**请求头**: 需要携带Token

**响应**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": [
    {
      "sku_id": "SKU001",
      "total_stock": 100,
      "available_stock": 98,
      "locked_stock": 2,
      "version": 1
    }
  ]
}
```

### 6.7 查询库存日志

**接口**: `GET /inventory/logs`

**请求头**: 需要携带Token

**查询参数**:
- `sku_id`: SKU ID (可选)
- `order_id`: 订单ID (可选)
- `change_type`: 操作类型 (可选)
- `page`: 页码 (默认1)
- `page_size`: 每页数量 (默认10，最大100)

**响应**:
```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "list": [
      {
        "id": 1,
        "sku_id": "SKU001",
        "order_id": "ORD2026031710001",
        "biz_id": "ORD2026031710001_LOCK_SKU001",
        "change_type": "LOCK",
        "change_amount": 2,
        "before_total": 100,
        "before_available": 100,
        "before_locked": 0,
        "created_at": "2026-03-17 10:00:00"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 10,
      "total": 50,
      "total_pages": 5
    }
  }
}
```

---

## 7. 文件上传

### 7.1 上传图片

**接口**: `POST /upload`

**请求类型**: `multipart/form-data`

**请求参数**:
- `file`: 图片文件

**响应**:
```json
{
  "success": true,
  "url": "/static/3c553e04eca443c89ba28231e829e565.png"
}
```

---

## 错误码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 401 | 未授权或Token无效 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

## 通用响应格式

### 成功响应
```json
{
  "success": true,
  "message": "操作成功",
  "data": {}
}
```

### 失败响应
```json
{
  "success": false,
  "message": "错误描述",
  "code": 400
}
```

---

## 前端对接注意事项

1. **Token管理**: 登录成功后，需要将Token存储在本地（localStorage或sessionStorage），并在每次请求时携带
2. **错误处理**: 统一处理HTTP错误，根据状态码显示相应的错误信息
3. **分页处理**: 列表接口都支持分页，需要处理分页逻辑
4. **图片上传**: 使用FormData上传图片，上传成功后获取图片URL
5. **支付流程**: 
   - 创建订单后调用支付接口
   - 显示客服微信号和添加按钮
   - 用户添加客服微信后通过微信转账完成支付
   - 定期查询支付状态更新订单状态
6. **权限控制**: 根据用户角色显示/隐藏相应的功能按钮

---

## 测试账号

### 普通用户
- 手机号: 13800138000
- 密码: 123456

### 商家账号
- 手机号: 13900139000
- 密码: 123456

### 管理员账号
- 手机号: 13700137000
- 密码: 123456

---

## 联系方式

- **客服微信**: CustomerService123
- **技术支持**: 根据实际情况填写

---

**注意**: 本文档基于当前API版本编写，如有更新请及时同步。
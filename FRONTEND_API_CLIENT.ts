// 前端对接API客户端示例
// 支持多种HTTP客户端：axios、fetch等

import type {
  ApiResponse,
  PaginationParams,
  PaginatedResponse,
  LoginRequest,
  RegisterRequest,
  LoginResponse,
  MerchantRegisterRequest,
  SmsCodeRequest,
  SmsLoginRequest,
  SetPasswordRequest,
  ChangePasswordRequest,
  UserProfile,
  Product,
  ProductCreateRequest,
  ProductUpdateRequest,
  ProductListParams,
  CartData,
  AddToCartRequest,
  UpdateCartItemRequest,
  Order,
  CreateOrderRequest,
  OrderListParams,
  UpdateOrderStatusRequest,
  PaymentCreateRequest,
  PaymentData,
  Inventory,
  InventoryLog,
  InitStockRequest,
  LockStockRequest,
  ReleaseStockRequest,
  DeductStockRequest,
  InventoryLogParams,
  UploadResponse,
  User,
  API_BASE_URL,
  USER_ROLES,
  ORDER_STATUS,
  PAYMENT_STATUS,
  INVENTORY_CHANGE_TYPE
} from './FRONTEND_TYPES';

// ==================== 配置 ====================

const CONFIG = {
  baseURL: import.meta.env?.VUE_APP_API_BASE_URL || API_BASE_URL,
  timeout: 30000,
  tokenKey: 'auth_token',
  userKey: 'auth_user'
};

// ==================== HTTP客户端 ====================

class ApiClient {
  private baseURL: string;
  private token: string | null = null;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
    this.loadToken();
  }

  // ==================== Token管理 ====================

  private loadToken(): void {
    this.token = localStorage.getItem(CONFIG.tokenKey);
  }

  setToken(token: string): void {
    this.token = token;
    localStorage.setItem(CONFIG.tokenKey, token);
  }

  clearToken(): void {
    this.token = null;
    localStorage.removeItem(CONFIG.tokenKey);
    localStorage.removeItem(CONFIG.userKey);
  }

  getToken(): string | null {
    return this.token;
  }

  // ==================== 请求方法 ====================

  private async request<T>(
    method: string,
    url: string,
    data?: any,
    params?: any,
    headers: Record<string, string> = {}
  ): Promise<ApiResponse<T>> {
    const requestHeaders: Record<string, string> = {
      'Content-Type': 'application/json',
      ...headers
    };

    if (this.token) {
      requestHeaders['Authorization'] = `Bearer ${this.token}`;
    }

    const config: RequestInit = {
      method,
      headers: requestHeaders,
      body: data ? JSON.stringify(data) : undefined
    };

    // 构建查询参数
    if (params) {
      const queryParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          queryParams.append(key, String(value));
        }
      });
      url += `?${queryParams.toString()}`;
    }

    try {
      const response = await fetch(`${this.baseURL}${url}`, config);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('API请求失败:', error);
      throw error;
    }
  }

  async get<T>(url: string, params?: any): Promise<ApiResponse<T>> {
    return this.request<T>('GET', url, undefined, params);
  }

  async post<T>(url: string, data?: any): Promise<ApiResponse<T>> {
    return this.request<T>('POST', url, data);
  }

  async put<T>(url: string, data?: any): Promise<ApiResponse<T>> {
    return this.request<T>('PUT', url, data);
  }

  async delete<T>(url: string): Promise<ApiResponse<T>> {
    return this.request<T>('DELETE', url);
  }

  // ==================== 文件上传 ====================

  async uploadFile(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const headers: Record<string, string> = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    try {
      const response = await fetch(`${this.baseURL}/upload`, {
        method: 'POST',
        headers,
        body: formData
      });

      if (!response.ok) {
        throw new Error(`上传失败: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('文件上传失败:', error);
      throw error;
    }
  }
}

// ==================== API实例 ====================

const api = new ApiClient(CONFIG.baseURL);

// ==================== 认证API ====================

export const authApi = {
  // 账号密码注册
  register: (data: RegisterRequest) =>
    api.post<LoginResponse>('/auth/register/password', data),

  // 账号密码登录
  login: (data: LoginRequest) =>
    api.post<LoginResponse>('/auth/login/password', data),

  // 获取当前用户信息
  getProfile: () =>
    api.get<UserProfile>('/auth/profile'),

  // 商家注册
  registerMerchant: (data: MerchantRegisterRequest) =>
    api.post<{ user_id: number }>('/auth/register/merchant', data),

  // 发送短信验证码
  sendSmsCode: (data: SmsCodeRequest) =>
    api.post('/auth/sms/send', data),

  // 短信验证码登录
  loginWithSms: (data: SmsLoginRequest) =>
    api.post<LoginResponse>('/auth/login/sms', data),

  // 设置密码
  setPassword: (data: SetPasswordRequest) =>
    api.post('/auth/set-password', data),

  // 修改密码
  changePassword: (data: ChangePasswordRequest) =>
    api.post('/auth/change-password', data)
};

// ==================== 商品API ====================

export const productApi = {
  // 创建商品
  create: (data: ProductCreateRequest) =>
    api.post<Product>('/products', data),

  // 获取商品详情
  get: (productId: number) =>
    api.get<Product>(`/products/${productId}`),

  // 获取商品列表
  list: (params: ProductListParams) =>
    api.get<PaginatedResponse<Product>>('/products', params),

  // 更新商品
  update: (productId: number, data: ProductUpdateRequest) =>
    api.put(`/products/${productId}`, data),

  // 删除商品
  delete: (productId: number) =>
    api.delete(`/products/${productId}`)
};

// ==================== 购物车API ====================

export const cartApi = {
  // 添加商品到购物车
  add: (data: AddToCartRequest) =>
    api.post('/cart/items', data),

  // 获取购物车
  get: () =>
    api.get<CartData>('/cart'),

  // 更新购物车商品数量
  update: (itemId: number, data: UpdateCartItemRequest) =>
    api.put(`/cart/items/${itemId}`, data),

  // 删除购物车商品
  remove: (itemId: number) =>
    api.delete(`/cart/items/${itemId}`),

  // 清空购物车
  clear: () =>
    api.delete('/cart')
};

// ==================== 订单API ====================

export const orderApi = {
  // 创建订单
  create: (data: CreateOrderRequest) =>
    api.post<Order>('/orders', data),

  // 获取订单列表
  list: (params: OrderListParams) =>
    api.get<PaginatedResponse<Order>>('/orders', params),

  // 获取订单详情
  get: (orderId: number) =>
    api.get<Order>(`/orders/${orderId}`),

  // 取消订单
  cancel: (orderId: number) =>
    api.post(`/orders/${orderId}/cancel`),

  // 更新订单状态
  updateStatus: (orderId: number, data: UpdateOrderStatusRequest) =>
    api.put(`/orders/${orderId}/status`, data)
};

// ==================== 支付API ====================

export const paymentApi = {
  // 创建支付订单
  create: (data: PaymentCreateRequest) =>
    api.post<PaymentCreateResponse>('/payments/native', data),

  // 查询支付结果
  query: (orderId: number) =>
    api.get<PaymentData>(`/payments/${orderId}`)
};

// ==================== 库存API ====================

export const inventoryApi = {
  // 初始化库存
  init: (data: InitStockRequest) =>
    api.post<Inventory>('/inventory/init', data),

  // 锁定库存
  lock: (data: LockStockRequest) =>
    api.post<Inventory>('/inventory/lock', data),

  // 释放库存
  release: (data: ReleaseStockRequest) =>
    api.post<Inventory>('/inventory/release', data),

  // 扣减库存
  deduct: (data: DeductStockRequest) =>
    api.post<Inventory>('/inventory/deduct', data),

  // 查询单个SKU库存
  get: (skuId: string) =>
    api.get<Inventory>(`/inventory/query/${skuId}`),

  // 查询所有库存
  list: () =>
    api.get<Inventory[]>('/inventory/query'),

  // 查询库存日志
  logs: (params: InventoryLogParams) =>
    api.get<PaginatedResponse<InventoryLog>>('/inventory/logs', params)
};

// ==================== 文件上传API ====================

export const uploadApi = {
  // 上传文件
  upload: (file: File) =>
    api.uploadFile(file)
};

// ==================== 导出 ====================

export default {
  // 配置
  CONFIG,

  // 客户端实例
  api,

  // API模块
  authApi,
  productApi,
  cartApi,
  orderApi,
  paymentApi,
  inventoryApi,
  uploadApi,

  // Token管理
  setToken: (token: string) => api.setToken(token),
  clearToken: () => api.clearToken(),
  getToken: () => api.getToken(),

  // 常量
  USER_ROLES,
  ORDER_STATUS,
  PAYMENT_STATUS,
  INVENTORY_CHANGE_TYPE
};

// ==================== 使用示例 ====================

/*
// 1. 登录
import { authApi } from './api-client';

async function handleLogin() {
  try {
    const result = await authApi.login({
      phone_number: '13800138000',
      password: '123456'
    });

    if (result.success && result.data) {
      // 保存Token
      api.setToken(result.data.token);

      // 保存用户信息
      localStorage.setItem(CONFIG.userKey, JSON.stringify(result.data));

      console.log('登录成功', result.data);
    }
  } catch (error) {
    console.error('登录失败', error);
  }
}

// 2. 获取商品列表
import { productApi } from './api-client';

async function loadProducts() {
  try {
    const result = await productApi.list({
      page: 1,
      page_size: 20,
      status: 1
    });

    if (result.success && result.data) {
      console.log('商品列表', result.data.list);
      console.log('分页信息', result.data.pagination);
    }
  } catch (error) {
    console.error('加载商品失败', error);
  }
}

// 3. 添加到购物车
import { cartApi } from './api-client';

async function addToCart(productId: number, quantity: number) {
  try {
    const result = await cartApi.add({
      product_id: productId,
      quantity: quantity
    });

    if (result.success) {
      console.log('添加成功', result.message);
    }
  } catch (error) {
    console.error('添加失败', error);
  }
}

// 4. 创建订单
import { orderApi } from './api-client';

async function createOrder() {
  try {
    const result = await orderApi.create({
      items: [
        {
          product_id: 1,
          quantity: 2
        }
      ],
      expected_delivery_date: '2026-03-20',
      remark: '请尽快发货'
    });

    if (result.success && result.data) {
      console.log('订单创建成功', result.data);
    }
  } catch (error) {
    console.error('创建订单失败', error);
  }
}

// 5. 创建支付
import { paymentApi } from './api-client';

async function createPayment(orderId: number) {
  try {
    const result = await paymentApi.create({
      order_id: orderId
    });

    if (result.success && result.data) {
      console.log('支付信息', result.data);
      console.log('客服微信', result.data.customer_service_wechat);
    }
  } catch (error) {
    console.error('创建支付失败', error);
  }
}

// 6. 上传图片
import { uploadApi } from './api-client';

async function uploadImage(file: File) {
  try {
    const result = await uploadApi.upload(file);

    if (result.success) {
      console.log('上传成功', result.url);
      return result.url;
    }
  } catch (error) {
    console.error('上传失败', error);
    throw error;
  }
}
*/
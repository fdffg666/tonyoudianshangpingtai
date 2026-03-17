// 前端对接TypeScript类型定义

// ==================== 基础类型 ====================

export interface ApiResponse<T = any> {
  success: boolean;
  message: string;
  data?: T;
  code?: number;
}

export interface PaginationParams {
  page: number;
  page_size: number;
}

export interface PaginationData {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface PaginatedResponse<T> {
  list: T[];
  pagination: PaginationData;
}

// ==================== 认证相关类型 ====================

export interface User {
  id: number;
  phone: string;
  role: 'user' | 'merchant' | 'admin' | 'root';
  nickname: string;
  status: string;
  points: number;
}

export interface LoginRequest {
  phone_number: string;
  password: string;
}

export interface RegisterRequest {
  phone_number: string;
  password: string;
  nickname?: string;
}

export interface LoginResponse {
  user_id: number;
  token: string;
  phone: string;
  role: string;
}

export interface MerchantRegisterRequest {
  username: string;
  password: string;
  wechat_id: string;
  invite_code: string;
}

export interface SmsCodeRequest {
  phone_number: string;
  scene?: string;
}

export interface SmsLoginRequest {
  phone_number: string;
  code: string;
  scene?: string;
}

export interface SetPasswordRequest {
  new_password: string;
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
}

export interface UserProfile {
  user: User;
}

// ==================== 商品相关类型 ====================

export interface Product {
  id: number;
  name: string;
  price: number;
  description?: string;
  cost_price?: number;
  image_url?: string;
  category?: string;
  sku_id?: string;
  status: number;
  created_at: string;
  updated_at?: string;
}

export interface ProductCreateRequest {
  name: string;
  price: number;
  description?: string;
  cost_price?: number;
  image_url?: string;
  category?: string;
  sku_id?: string;
  initial_stock?: number;
}

export interface ProductUpdateRequest {
  name?: string;
  price?: number;
  description?: string;
  cost_price?: number;
  image_url?: string;
  category?: string;
  sku_id?: string;
  status?: number;
}

export interface ProductListParams extends PaginationParams {
  category?: string;
  status?: number;
  keyword?: string;
}

// ==================== 购物车相关类型 ====================

export interface CartItem {
  cart_id: number;
  product_id: number;
  name: string;
  quantity: number;
  price: number;
  subtotal: number;
  image_url?: string;
}

export interface CartData {
  items: CartItem[];
  total_amount: number;
  total_quantity: number;
}

export interface AddToCartRequest {
  product_id: number;
  quantity: number;
}

export interface UpdateCartItemRequest {
  quantity: number;
}

// ==================== 订单相关类型 ====================

export interface OrderItem {
  product_id: number;
  name: string;
  quantity: number;
  price: number;
  subtotal: number;
}

export interface Order {
  order_id: number;
  order_no: string;
  user_id: number;
  total_amount: number;
  status: 'pending' | 'confirmed' | 'shipped' | 'completed' | 'cancelled';
  expected_delivery_date?: string;
  remark?: string;
  assigned_wechat?: string;
  items: OrderItem[];
  created_at: string;
  updated_at?: string;
}

export interface CreateOrderRequest {
  items: {
    product_id: number;
    quantity: number;
  }[];
  expected_delivery_date?: string;
  remark?: string;
}

export interface OrderListParams extends PaginationParams {
  status?: string;
}

export interface UpdateOrderStatusRequest {
  status: 'pending' | 'confirmed' | 'shipped' | 'completed' | 'cancelled';
}

// ==================== 支付相关类型 ====================

export interface PaymentCreateRequest {
  order_id: number;
}

export interface PaymentCreateResponse {
  code_url: string;
  out_trade_no: string;
  expire_at: string;
  customer_service_wechat: string;
  message: string;
}

export interface PaymentData {
  out_trade_no: string;
  trade_state: 'NOTPAY' | 'SUCCESS' | 'CLOSED' | 'REFUND';
  pay_amount: number;
  time_paid?: string;
  customer_service_wechat: string;
  message: string;
}

// ==================== 库存相关类型 ====================

export interface Inventory {
  sku_id: string;
  total_stock: number;
  available_stock: number;
  locked_stock: number;
  version: number;
}

export interface InventoryLog {
  id: number;
  sku_id: string;
  order_id: string;
  biz_id: string;
  change_type: 'INIT' | 'RESET' | 'LOCK' | 'RELEASE' | 'DEDUCT';
  change_amount: number;
  before_total: number;
  before_available: number;
  before_locked: number;
  created_at: string;
}

export interface InitStockRequest {
  sku_id: string;
  total_stock: number;
  force?: boolean;
}

export interface LockStockRequest {
  sku_id: string;
  lock_num: number;
  order_id: string;
  lock_timeout?: number;
}

export interface ReleaseStockRequest {
  sku_id: string;
  lock_num: number;
  order_id: string;
  lock_timeout?: number;
}

export interface DeductStockRequest {
  sku_id: string;
  deduct_num: number;
  order_id: string;
  lock_timeout?: number;
}

export interface InventoryLogParams extends PaginationParams {
  sku_id?: string;
  order_id?: string;
  change_type?: string;
}

// ==================== 文件上传相关类型 ====================

export interface UploadResponse {
  success: boolean;
  url: string;
}

// ==================== API客户端配置 ====================

export interface ApiConfig {
  baseURL: string;
  timeout?: number;
  headers?: Record<string, string>;
}

// ==================== 请求拦截器类型 ====================

export interface RequestConfig {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  data?: any;
  params?: any;
  headers?: Record<string, string>;
  timeout?: number;
}

// ==================== 响应拦截器类型 ====================

export interface ResponseInterceptor {
  (response: ApiResponse): ApiResponse | Promise<ApiResponse>;
}

export interface ErrorInterceptor {
  (error: any): any;
}

// ==================== 存储相关类型 ====================

export interface StoredAuth {
  token: string;
  user: User;
  expireAt: number;
}

// ==================== 常量定义 ====================

export const API_BASE_URL = 'http://localhost:8000';

export const USER_ROLES = {
  USER: 'user',
  MERCHANT: 'merchant',
  ADMIN: 'admin',
  ROOT: 'root'
} as const;

export const ORDER_STATUS = {
  PENDING: 'pending',
  CONFIRMED: 'confirmed',
  SHIPPED: 'shipped',
  COMPLETED: 'completed',
  CANCELLED: 'cancelled'
} as const;

export const PAYMENT_STATUS = {
  NOTPAY: 'NOTPAY',
  SUCCESS: 'SUCCESS',
  CLOSED: 'CLOSED',
  REFUND: 'REFUND'
} as const;

export const INVENTORY_CHANGE_TYPE = {
  INIT: 'INIT',
  RESET: 'RESET',
  LOCK: 'LOCK',
  RELEASE: 'RELEASE',
  DEDUCT: 'DEDUCT'
} as const;

// ==================== 工具类型 ====================

export type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

export type Optional<T> = T | null | undefined;

export type RequiredFields<T, K extends keyof T> = T & Required<Pick<T, K>>;

// ==================== 环境变量类型 ====================

export interface EnvConfig {
  NODE_ENV: 'development' | 'production' | 'test';
  VUE_APP_API_BASE_URL?: string;
  VUE_APP_TITLE?: string;
}

declare const process: {
  env: EnvConfig;
};

// ==================== 路由相关类型 ====================

export interface RouteMeta {
  title?: string;
  requiresAuth?: boolean;
  roles?: string[];
  keepAlive?: boolean;
}

export interface RouteConfig {
  path: string;
  name: string;
  component: any;
  meta?: RouteMeta;
  children?: RouteConfig[];
}

// ==================== 表单相关类型 ====================

export interface FormRule {
  required?: boolean;
  message?: string;
  trigger?: 'blur' | 'change';
  min?: number;
  max?: number;
  pattern?: RegExp;
  validator?: (rule: any, value: any, callback: any) => void;
}

export interface FormRules {
  [key: string]: FormRule | FormRule[];
}

// ==================== 组件相关类型 ====================

export interface TableColumn {
  key: string;
  title: string;
  width?: number;
  align?: 'left' | 'center' | 'right';
  fixed?: 'left' | 'right';
  sorter?: boolean;
  filters?: any[];
}

export interface TableProps {
  columns: TableColumn[];
  data: any[];
  loading?: boolean;
  pagination?: boolean | PaginationData;
  rowKey?: string;
}

// ==================== 错误类型 ====================

export interface ApiError {
  code: number;
  message: string;
  details?: any;
}

export class HttpError extends Error {
  code: number;
  details?: any;

  constructor(message: string, code: number, details?: any) {
    super(message);
    this.name = 'HttpError';
    this.code = code;
    this.details = details;
  }
}

// ==================== 日志类型 ====================

export enum LogLevel {
  DEBUG = 'debug',
  INFO = 'info',
  WARN = 'warn',
  ERROR = 'error'
}

export interface LogEntry {
  level: LogLevel;
  message: string;
  timestamp: string;
  context?: any;
}

// ==================== 缓存相关类型 ====================

export interface CacheOptions {
  ttl?: number; // 过期时间（毫秒）
  persistent?: boolean; // 是否持久化
}

export interface CacheItem<T> {
  value: T;
  timestamp: number;
  ttl?: number;
}

// ==================== 主题相关类型 ====================

export type ThemeMode = 'light' | 'dark' | 'auto';

export interface ThemeConfig {
  mode: ThemeMode;
  primaryColor: string;
  borderRadius: number;
}

// ==================== 国际化类型 ====================

export interface I18nMessages {
  [key: string]: string | I18nMessages;
}

export interface I18nConfig {
  locale: string;
  fallbackLocale: string;
  messages: Record<string, I18nMessages>;
}

// ==================== 通知类型 ====================

export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  duration?: number;
  timestamp: number;
}

// ==================== WebSocket类型 ====================

export interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: number;
}

export interface WebSocketOptions {
  url: string;
  protocols?: string | string[];
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

// ==================== 文件类型 ====================

export interface FileUploadOptions {
  accept?: string;
  maxSize?: number; // 字节
  multiple?: boolean;
}

export interface UploadedFile {
  name: string;
  size: number;
  type: string;
  url: string;
}

// ==================== 导出所有类型 ====================

export default {
  // 基础类型
  ApiResponse,
  PaginationParams,
  PaginationData,
  PaginatedResponse,

  // 认证相关
  User,
  LoginRequest,
  RegisterRequest,
  LoginResponse,
  MerchantRegisterRequest,
  SmsCodeRequest,
  SmsLoginRequest,
  SetPasswordRequest,
  ChangePasswordRequest,
  UserProfile,

  // 商品相关
  Product,
  ProductCreateRequest,
  ProductUpdateRequest,
  ProductListParams,

  // 购物车相关
  CartItem,
  CartData,
  AddToCartRequest,
  UpdateCartItemRequest,

  // 订单相关
  Order,
  OrderItem,
  CreateOrderRequest,
  OrderListParams,
  UpdateOrderStatusRequest,

  // 支付相关
  PaymentCreateRequest,
  PaymentCreateResponse,
  PaymentData,

  // 库存相关
  Inventory,
  InventoryLog,
  InitStockRequest,
  LockStockRequest,
  ReleaseStockRequest,
  DeductStockRequest,
  InventoryLogParams,

  // 文件上传
  UploadResponse,

  // 配置
  ApiConfig,
  API_BASE_URL,

  // 常量
  USER_ROLES,
  ORDER_STATUS,
  PAYMENT_STATUS,
  INVENTORY_CHANGE_TYPE,

  // 错误
  ApiError,
  HttpError,
};
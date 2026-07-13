"""
安全模块

提供 JWT Token、AES 加密、Tool Token 等安全相关功能
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Iterable, List
from jose import jwt, JWTError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import bcrypt
import secrets
import hashlib
import base64
import os

from app.config import get_settings, get_current_time
from app.logger_mgr import get_logger

logger = get_logger("app.core.security")


# ==================== JWT Token ====================

def create_access_token(
    data: Dict[str, Any], 
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建 JWT Access Token
    
    Args:
        data: 要编码到 token 中的数据（如 user_id, username, is_admin 等）
        expires_delta: 过期时间增量，默认使用配置中的过期时间
    
    Returns:
        JWT token 字符串
    """
    settings = get_settings()
    to_encode = data.copy()
    
    now = get_current_time()
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )
    
    to_encode.update({
        "exp": expire,
        "iat": now
    })
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.jwt_secret_key, 
        algorithm=settings.jwt_algorithm
    )
    
    logger.debug(f"Created JWT token for data: {data}")
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    验证并解析 JWT Token
    
    Args:
        token: JWT token 字符串
    
    Returns:
        解析后的 payload 字典，验证失败返回 None
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, 
            settings.jwt_secret_key, 
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {str(e)}")
        return None


def decode_token_without_verify(token: str) -> Optional[Dict[str, Any]]:
    """
    解析 JWT Token（不验证签名，仅用于调试）
    
    Args:
        token: JWT token 字符串
    
    Returns:
        解析后的 payload 字典
    """
    try:
        # 不验证签名和过期时间
        payload = jwt.decode(
            token, 
            options={"verify_signature": False, "verify_exp": False}
        )
        return payload
    except Exception as e:
        logger.error(f"Token decode error: {str(e)}")
        return None


# ==================== AES-256-GCM 加密 ====================

def _get_aes_key(secret_key: Optional[str] = None) -> bytes:
    """
    获取 AES 密钥
    
    Args:
        secret_key: 可选的密钥字符串，默认使用配置中的密钥
    
    Returns:
        32 字节的 AES 密钥
    """
    if secret_key is None:
        settings = get_settings()
        secret_key = settings.aes_secret_key
    
    # 确保密钥长度为 32 字节
    key = secret_key.encode()[:32].ljust(32, b'\0')
    return key


def encrypt_api_key(api_key: str, secret_key: Optional[str] = None) -> str:
    """
    使用 AES-256-GCM 加密 API Key
    
    Args:
        api_key: 要加密的 API Key
        secret_key: 可选的加密密钥，默认使用配置中的密钥
    
    Returns:
        Base64 编码的加密字符串（包含 nonce + ciphertext）
    """
    key = _get_aes_key(secret_key)
    aesgcm = AESGCM(key)
    
    # 生成随机 nonce（12 字节）
    nonce = os.urandom(12)
    
    # 加密
    ciphertext = aesgcm.encrypt(nonce, api_key.encode(), None)
    
    # 返回 nonce + ciphertext 的 Base64 编码
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_api_key(encrypted_key: str, secret_key: Optional[str] = None) -> str:
    """
    解密 API Key
    
    Args:
        encrypted_key: Base64 编码的加密字符串
        secret_key: 可选的解密密钥，默认使用配置中的密钥
    
    Returns:
        解密后的 API Key
        
    Raises:
        Exception: 解密失败时抛出异常
    """
    key = _get_aes_key(secret_key)
    aesgcm = AESGCM(key)
    
    # Base64 解码
    data = base64.b64decode(encrypted_key)
    
    # 分离 nonce 和 ciphertext
    nonce = data[:12]
    ciphertext = data[12:]
    
    # 解密
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    
    return plaintext.decode()


# ==================== Tool Token ====================

def generate_tool_token() -> str:
    """
    生成 Tool Token
    
    生成格式为 sk-{random_string} 的 token
    
    Returns:
        Tool Token 字符串
    """
    return f"sk-{secrets.token_urlsafe(32)}"


def hash_tool_token(token: str) -> str:
    """
    计算 Tool Token 的 SHA-256 哈希
    
    Args:
        token: Tool Token 字符串
    
    Returns:
        SHA-256 哈希值（十六进制）
    """
    return hashlib.sha256(token.encode()).hexdigest()


def verify_tool_token(token: str, token_hash: str) -> bool:
    """
    验证 Tool Token 是否匹配
    
    Args:
        token: Tool Token 字符串
        token_hash: 存储的 token 哈希值
    
    Returns:
        是否匹配
    """
    return hash_tool_token(token) == token_hash


# ==================== 密码哈希（bcrypt）====================

def hash_password(password: str) -> str:
    """使用 bcrypt 哈希密码

    Args:
        password: 密码明文

    Returns:
        bcrypt 哈希字符串
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码是否匹配 bcrypt 哈希

    Args:
        password: 密码明文
        password_hash: 存储的 bcrypt 哈希值

    Returns:
        是否匹配
    """
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


# ==================== 日志脱敏 ====================

def extract_api_key_from_headers(headers: Optional[Dict[str, str]]) -> Optional[str]:
    """
    从请求头中提取 API Key 字面值（用于日志脱敏）

    支持两种常见的 provider 认证头：
    - Authorization: Bearer <key>
    - x-api-key: <key>
    """
    if not headers:
        return None
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    if isinstance(auth, str) and auth.lower().startswith("bearer "):
        candidate = auth[7:].strip()
        if candidate:
            return candidate
    xkey = headers.get("x-api-key") or headers.get("X-API-Key")
    if isinstance(xkey, str):
        stripped = xkey.strip()
        if stripped:
            return stripped
    return None


def sanitize_for_log(text: str, headers: Optional[Dict[str, str]] = None, extra_secrets: Optional[Iterable[str]] = None) -> str:
    """
    脱敏日志文本

    将 headers 中可识别的 API Key 及 extra_secrets 中的值替换为 ``***REDACTED***``，
    用于避免上游回显请求头场景下 API Key 落入日志。

    为避免误伤（例如短到无意义的占位串），仅对长度 >= 8 的候选做替换。

    Args:
        text: 原始日志文本
        headers: 转发请求使用的 headers（从中提取 api_key）
        extra_secrets: 额外需要脱敏的字符串（可迭代）

    Returns:
        脱敏后的文本
    """
    if not text:
        return text

    secrets_to_mask: List[str] = []
    api_key = extract_api_key_from_headers(headers)
    if api_key:
        secrets_to_mask.append(api_key)
    if extra_secrets:
        for item in extra_secrets:
            if item and item not in secrets_to_mask:
                secrets_to_mask.append(item)

    sanitized = text
    for secret in secrets_to_mask:
        if secret and len(secret) >= 8:
            sanitized = sanitized.replace(secret, "***REDACTED***")
    return sanitized

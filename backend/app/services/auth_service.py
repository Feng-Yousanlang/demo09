from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.database import Admin

# 密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """认证服务类"""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """生成密码哈希"""
        return pwd_context.hash(password)
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """创建JWT访问令牌"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """验证JWT令牌"""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                return None
            return {"username": username}
        except JWTError:
            return None
    
    @staticmethod
    async def authenticate_admin(db: AsyncSession, username: str, password: str) -> Optional[Admin]:
        """验证管理员登录"""
        result = await db.execute(select(Admin).where(Admin.username == username))
        admin = result.scalar_one_or_none()
        
        if not admin:
            return None
        if not AuthService.verify_password(password, admin.password_hash):
            return None
        return admin
    
    @staticmethod
    async def get_admin_by_username(db: AsyncSession, username: str) -> Optional[Admin]:
        """根据用户名获取管理员"""
        result = await db.execute(select(Admin).where(Admin.username == username))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_admin(db: AsyncSession, username: str, password: str) -> Admin:
        """创建新管理员"""
        hashed_password = AuthService.get_password_hash(password)
        admin = Admin(username=username, password_hash=hashed_password)
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        return admin


# 创建全局认证服务实例
auth_service = AuthService() 
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import User, Profile, UserRole
from app.core.security import decode_access_token

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user."""
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    return user


async def require_ceo(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile or profile.role != UserRole.CEO:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CEO access required")
    return current_user


async def require_manager(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile or profile.role not in (UserRole.MANAGER, UserRole.CEO):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager access required")
    return current_user


async def require_employee(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile or profile.role != UserRole.EMPLOYEE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee access required")
    return current_user

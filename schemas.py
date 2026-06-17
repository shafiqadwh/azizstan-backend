from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from typing import Optional
from datetime import datetime


# ─── Organization ────────────────────────────────────────────────────────────

class OrganizationCreate(BaseModel):
    name: str
    slug: str
    default_language: str = "th"

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    plan: Optional[str] = None
    is_active: Optional[bool] = None
    default_language: Optional[str] = None

class Organization(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    plan: str
    is_active: bool
    default_language: str
    created_at: datetime


# ─── User ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str  # SuperAdmin/Admin/Owner/Buyer
    language: str = "th"

class UserUpdate(BaseModel):
    username: Optional[str] = None
    language: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organization_id: Optional[int]
    username: str
    email: str
    role: str
    language: str
    is_active: bool
    created_at: datetime


# ─── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ─── BackTeam ─────────────────────────────────────────────────────────────────

class BackTeamMemberCreate(BaseModel):
    user_id: int
    share_percentage: float

    @field_validator("share_percentage")
    @classmethod
    def validate_pct(cls, v):
        if not (0 < v <= 100):
            raise ValueError("share_percentage must be between 0 and 100")
        return v

class BackTeamMemberUpdate(BaseModel):
    share_percentage: float

class BackTeamMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    share_percentage: float
    user: UserOut


# ─── Plantation ───────────────────────────────────────────────────────────────

class PlantationCreate(BaseModel):
    name: str
    backteam_percentage: float = 10.0

class PlantationUpdate(BaseModel):
    name: Optional[str] = None
    backteam_percentage: Optional[float] = None
    is_active: Optional[bool] = None

class PlantationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organization_id: int
    name: str
    backteam_percentage: float
    is_active: bool


# ─── PlantationOwner ──────────────────────────────────────────────────────────

class PlantationOwnerCreate(BaseModel):
    owner_id: int
    share_percentage: float

class PlantationOwnerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    plantation_id: int
    owner_id: int
    share_percentage: float
    owner: UserOut


# ─── Plot ─────────────────────────────────────────────────────────────────────

class PlotCreate(BaseModel):
    name: str
    area_rai: Optional[float] = None

class PlotUpdate(BaseModel):
    name: Optional[str] = None
    area_rai: Optional[float] = None
    is_active: Optional[bool] = None

class PlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    plantation_id: int
    name: str
    area_rai: Optional[float]
    is_active: bool


# ─── Tapper ───────────────────────────────────────────────────────────────────

class TapperCreate(BaseModel):
    plantation_id: int
    name: str
    phone: Optional[str] = None

class TapperUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

class TapperOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    plantation_id: int
    name: str
    phone: Optional[str]
    is_active: bool


# ─── PlotTapper ───────────────────────────────────────────────────────────────

class PlotTapperAssign(BaseModel):
    tapper_id: int


# ─── Transaction ──────────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    plot_id: int
    tapper_id: int
    rubber_weight: float
    rubber_price_per_unit: float
    wood_income: float = 0.0
    notes: Optional[str] = None

class OwnerShareOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    owner_id: int
    share_percentage: float
    rubber_amount: float
    wood_amount: float
    total_amount: float
    owner: UserOut

class BackTeamShareOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    share_percentage: float
    amount: float
    member: UserOut

class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: datetime
    plot_id: int
    tapper_id: int
    buyer_id: int
    rubber_weight: float
    rubber_price_per_unit: float
    wood_income: float
    gross_rubber_amount: float
    tapper_share: float
    owner_rubber_pool: float
    backteam_amount: float
    owner_rubber_net: float
    is_paid: bool
    notes: Optional[str]
    tapper: TapperOut
    buyer: UserOut
    owner_shares: list[OwnerShareOut] = []
    backteam_shares: list[BackTeamShareOut] = []


# ─── Debt ─────────────────────────────────────────────────────────────────────

class DebtItemCreate(BaseModel):
    plantation_id: int
    tapper_id: Optional[int] = None
    description: str
    total_amount: float
    debtor_type: str  # owner/tapper/split
    owner_share_pct: float = 100.0

    @field_validator("debtor_type")
    @classmethod
    def validate_debtor_type(cls, v):
        if v not in ("owner", "tapper", "split"):
            raise ValueError("debtor_type must be owner, tapper, or split")
        return v

class DebtItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    plantation_id: int
    tapper_id: Optional[int]
    description: str
    total_amount: float
    debtor_type: str
    owner_share_pct: float
    is_active: bool
    created_at: datetime
    plantation: PlantationOut
    tapper: Optional[TapperOut]

class DebtPaymentCreate(BaseModel):
    amount: float
    paid_by: str   # owner/tapper
    notes: Optional[str] = None
    transaction_id: Optional[int] = None

    @field_validator("paid_by")
    @classmethod
    def validate_paid_by(cls, v):
        if v not in ("owner", "tapper"):
            raise ValueError("paid_by must be owner or tapper")
        return v

class DebtPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    debt_item_id: int
    amount: float
    paid_by: str
    paid_at: datetime
    notes: Optional[str]
    transaction_id: Optional[int]


class DebtSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    description: str
    total_amount: float
    total_paid: float
    balance: float
    debtor_type: str
    owner_share_pct: float
    is_active: bool
    plantation: PlantationOut
    tapper: Optional[TapperOut]
    payments: list[DebtPaymentOut] = []

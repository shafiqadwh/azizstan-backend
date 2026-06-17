from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    plan = Column(String, default="trial")  # trial/basic/pro
    is_active = Column(Boolean, default=True)
    default_language = Column(String, default="th")  # th/en/ms
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    users = relationship("User", back_populates="organization")
    plantations = relationship("Plantation", back_populates="organization")
    backteam_members = relationship("BackTeamMember", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)  # null = PlatformAdmin
    username = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # PlatformAdmin/SuperAdmin/Admin/Owner/Buyer
    language = Column(String, default="th")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="users")
    backteam_membership = relationship("BackTeamMember", back_populates="user", uselist=False)
    plantation_ownerships = relationship("PlantationOwner", back_populates="owner")
    owner_shares = relationship("OwnerShare", back_populates="owner", foreign_keys="OwnerShare.owner_id")
    backteam_shares = relationship("BackTeamShare", back_populates="member", foreign_keys="BackTeamShare.user_id")


class BackTeamMember(Base):
    """SuperAdmin/Admin who receives a % cut from each transaction."""
    __tablename__ = "backteam_members"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    share_percentage = Column(Float, nullable=False)  # sum per org must = 100

    organization = relationship("Organization", back_populates="backteam_members")
    user = relationship("User", back_populates="backteam_membership")
    backteam_shares = relationship("BackTeamShare", back_populates="member_config")


class Plantation(Base):
    __tablename__ = "plantations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    name = Column(String, nullable=False)
    backteam_percentage = Column(Float, default=10.0)  # % taken from owner's rubber share
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="plantations")
    plantation_owners = relationship("PlantationOwner", back_populates="plantation")
    plots = relationship("Plot", back_populates="plantation")
    tappers = relationship("Tapper", back_populates="plantation")
    debt_items = relationship("DebtItem", back_populates="plantation")


class PlantationOwner(Base):
    """M:M — one plantation can have multiple owners with different share %."""
    __tablename__ = "plantation_owners"

    id = Column(Integer, primary_key=True, index=True)
    plantation_id = Column(Integer, ForeignKey("plantations.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    share_percentage = Column(Float, nullable=False)  # sum per plantation must = 100

    plantation = relationship("Plantation", back_populates="plantation_owners")
    owner = relationship("User", back_populates="plantation_ownerships")
    owner_shares = relationship("OwnerShare", back_populates="plantation_owner")


class Plot(Base):
    """แปลง — sub-section of a plantation, each can have one or more tappers."""
    __tablename__ = "plots"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    plantation_id = Column(Integer, ForeignKey("plantations.id"), nullable=False)
    name = Column(String, nullable=False)
    area_rai = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)

    plantation = relationship("Plantation", back_populates="plots")
    plot_tappers = relationship("PlotTapper", back_populates="plot")
    transactions = relationship("Transaction", back_populates="plot")


class Tapper(Base):
    __tablename__ = "tappers"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    plantation_id = Column(Integer, ForeignKey("plantations.id"), nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    plantation = relationship("Plantation", back_populates="tappers")
    plot_tappers = relationship("PlotTapper", back_populates="tapper")
    transactions = relationship("Transaction", back_populates="tapper")
    debt_items = relationship("DebtItem", back_populates="tapper")


class PlotTapper(Base):
    """M:M — a plot can have multiple tappers, a tapper can work multiple plots."""
    __tablename__ = "plot_tappers"

    plot_id = Column(Integer, ForeignKey("plots.id"), primary_key=True)
    tapper_id = Column(Integer, ForeignKey("tappers.id"), primary_key=True)

    plot = relationship("Plot", back_populates="plot_tappers")
    tapper = relationship("Tapper", back_populates="plot_tappers")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    plot_id = Column(Integer, ForeignKey("plots.id"), nullable=False)
    tapper_id = Column(Integer, ForeignKey("tappers.id"), nullable=False)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(String, nullable=True)

    # Inputs
    rubber_weight = Column(Float, nullable=False)
    rubber_price_per_unit = Column(Float, nullable=False)
    wood_income = Column(Float, default=0.0)  # 100% to owners, bypasses BackTeam cut

    # Calculated (rubber only)
    gross_rubber_amount = Column(Float, nullable=False)  # weight × price
    tapper_share = Column(Float, nullable=False)          # gross / 2
    owner_rubber_pool = Column(Float, nullable=False)     # gross / 2
    backteam_amount = Column(Float, nullable=False)       # owner_rubber_pool × backteam_%
    owner_rubber_net = Column(Float, nullable=False)      # owner_rubber_pool - backteam_amount
    # owners_total_net = owner_rubber_net + wood_income (computed, not stored)

    is_paid = Column(Boolean, default=False)

    plot = relationship("Plot", back_populates="transactions")
    tapper = relationship("Tapper", back_populates="transactions")
    buyer = relationship("User", foreign_keys=[buyer_id])
    owner_shares = relationship("OwnerShare", back_populates="transaction")
    backteam_shares = relationship("BackTeamShare", back_populates="transaction")
    debt_payments = relationship("DebtPayment", back_populates="transaction")


class OwnerShare(Base):
    """Per-transaction record of each owner's payout. Snapshot at transaction time."""
    __tablename__ = "owner_shares"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    plantation_owner_id = Column(Integer, ForeignKey("plantation_owners.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    share_percentage = Column(Float, nullable=False)
    rubber_amount = Column(Float, nullable=False)   # from owner_rubber_net × share_%
    wood_amount = Column(Float, nullable=False)     # from wood_income × share_%
    total_amount = Column(Float, nullable=False)    # rubber_amount + wood_amount

    transaction = relationship("Transaction", back_populates="owner_shares")
    plantation_owner = relationship("PlantationOwner", back_populates="owner_shares")
    owner = relationship("User", back_populates="owner_shares", foreign_keys=[owner_id])


class BackTeamShare(Base):
    """Per-transaction record of each BackTeam member's payout."""
    __tablename__ = "backteam_shares"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    backteam_member_id = Column(Integer, ForeignKey("backteam_members.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    share_percentage = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)

    transaction = relationship("Transaction", back_populates="backteam_shares")
    member_config = relationship("BackTeamMember", back_populates="backteam_shares")
    member = relationship("User", back_populates="backteam_shares", foreign_keys=[user_id])


class DebtItem(Base):
    """A debt record — fertilizer, equipment, etc. fronted by BackTeam."""
    __tablename__ = "debt_items"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    plantation_id = Column(Integer, ForeignKey("plantations.id"), nullable=False)
    tapper_id = Column(Integer, ForeignKey("tappers.id"), nullable=True)
    description = Column(String, nullable=False)
    total_amount = Column(Float, nullable=False)
    debtor_type = Column(String, nullable=False)   # owner/tapper/split
    owner_share_pct = Column(Float, default=100.0) # if split: % owner must pay
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)

    plantation = relationship("Plantation", back_populates="debt_items")
    tapper = relationship("Tapper", back_populates="debt_items")
    payments = relationship("DebtPayment", back_populates="debt_item")


class DebtPayment(Base):
    """Installment payment against a DebtItem. Amount is flexible each time."""
    __tablename__ = "debt_payments"

    id = Column(Integer, primary_key=True, index=True)
    debt_item_id = Column(Integer, ForeignKey("debt_items.id"), nullable=False)
    amount = Column(Float, nullable=False)
    paid_by = Column(String, nullable=False)  # owner/tapper
    paid_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(String, nullable=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)

    debt_item = relationship("DebtItem", back_populates="payments")
    transaction = relationship("Transaction", back_populates="debt_payments")

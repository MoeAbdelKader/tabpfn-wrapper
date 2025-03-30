import datetime
import uuid

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID # Use PostgreSQL's UUID type

from tabpfn_api.db.database import Base
# We will define the relationship using strings to avoid circular imports
# from tabpfn_api.models.user import User # Avoid direct import


class ModelMetadata(Base):
    """
    Database model for storing metadata about trained TabPFN models.

    Links our internal model ID to the TabPFN train_set_uid and the owning user.
    Also stores basic information about the training run.
    """
    __tablename__ = "model_metadata"

    # Internal primary key for the metadata record itself
    id = Column(Integer, primary_key=True, index=True)

    # Our service's unique identifier for the trained model (e.g., for API endpoints)
    internal_model_id = Column(UUID(as_uuid=True), unique=True, index=True, nullable=False, default=uuid.uuid4)

    # The identifier returned by tabpfn-client's fit() method
    # Index this for potential lookups if we need to find our model based on TabPFN's ID
    tabpfn_train_set_uid = Column(String, index=True, nullable=False)

    # Foreign key linking to the user who created/owns this model
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Basic metadata captured during the fit request
    feature_count = Column(Integer, nullable=False)
    sample_count = Column(Integer, nullable=False)
    feature_names = Column(JSON, nullable=True) # Store list of feature names if provided
    tabpfn_config = Column(JSON, nullable=True) # Store the config dict passed to tabpfn fit

    # Timestamp for when the model metadata record was created
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Define relationship to User (using string to avoid circular import)
    # 'back_populates' should match the relationship name defined in the User model
    user = relationship("User", back_populates="models")


# Optional: Add a composite index if we expect frequent queries filtering by user and creation time, for example.
# Index('ix_model_metadata_user_created', ModelMetadata.user_id, ModelMetadata.created_at) 
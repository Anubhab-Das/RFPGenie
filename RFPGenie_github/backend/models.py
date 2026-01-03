from typing import Optional, List
from sqlmodel import Field, SQLModel, JSON, Column, Relationship
from pydantic import computed_field
import datetime

# Database Models

class Section(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    section_name: str
    description: str
    category: str
    is_custom: bool = Field(default=False)

class Template(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: str
    sections: List[str] = Field(sa_column=Column(JSON))
    proposals: List["Proposal"] = Relationship(back_populates="template", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

class SectionVersion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    proposal_section_id: int = Field(foreign_key="proposalsection.id")
    version_number: int
    content: str
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    proposal_section: "ProposalSection" = Relationship(back_populates="versions")

class ProposalSection(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    proposal_id: int = Field(foreign_key="proposal.id")
    section_name: str
    collection_mappings: List[str] = Field(sa_column=Column(JSON), default=[])
    custom_prompt: str = ""
    proposal: "Proposal" = Relationship(back_populates="proposal_sections")
    versions: List[SectionVersion] = Relationship(back_populates="proposal_section", sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"})

class Proposal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: str
    client_name: str
    scope_document_path: str
    template_id: Optional[int] = Field(default=None, foreign_key="template.id")
    final_rfp_json: Optional[str] = Field(default=None)
    proposal_sections: List[ProposalSection] = Relationship(back_populates="proposal", sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"})
    template: Optional["Template"] = Relationship(back_populates="proposals")

    @computed_field
    @property
    def draft_rfp_json(self) -> bool:
        return any(section.versions for section in self.proposal_sections)

# New Approval Model
class Approval(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    proposal_id: int = Field(foreign_key="proposal.id")
    approved_by: str
    approved_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    status: str = Field(default="pending")  # pending, approved, rejected
    comments: Optional[str] = None
    proposal: Proposal = Relationship()

# API Response Models

class SectionVersionResponse(SQLModel):
    id: int
    version_number: int
    content: str
    created_at: datetime.datetime

class ProposalSectionResponse(SQLModel):
    id: int
    proposal_id: int
    section_name: str
    collection_mappings: List[str]
    custom_prompt: str
    versions: List[SectionVersionResponse] = []

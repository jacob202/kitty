from typing import Literal

from pydantic import BaseModel


class PersonProperties(BaseModel):
    full_name: str
    aliases: list[str] = []
    nationality: str | None = None
    roles: list[str] = [] # e.g. ["Director", "Shareholder"]

class OrganizationProperties(BaseModel):
    name: str
    registration_number: str | None = None
    jurisdiction: str | None = None
    org_type: Literal["Company", "NGO", "Government", "Trust"]

class TransactionProperties(BaseModel):
    amount: float
    currency: str = "USD"
    date: str
    description: str | None = None
    source_account: str | None = None
    target_account: str | None = None

class ContractProperties(BaseModel):
    title: str
    value: float | None = None
    signing_date: str | None = None
    status: Literal["Active", "Terminated", "Pending"]

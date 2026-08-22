from fastapi import FastAPI, Depends, HTTPException, status,Query
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

import models
from database import engine, get_db

# Create all database tables on application startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="FastAPI SQLAlchemy Expense Tracker")

# --- Pydantic Data Validation Schemas ---
class ExpenseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, json_schema_extra={"example": "Coffee"})
    amount: float = Field(..., gt=0, json_schema_extra={"example": 4.50})
    category: str = Field(..., json_schema_extra={"example": "Food"})

class ExpenseCreate(ExpenseBase):
    pass

class ExpenseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    amount: Optional[float] = Field(None, gt=0)
    category: Optional[str] = None

class ExpenseResponse(ExpenseBase):
    expense_id: int
    created_at: datetime
    class Config:
        from_attributes = True  # Allows Pydantic to read SQLAlchemy models directly

# --- Helper Function for Date and Category Filtering ---
def apply_filters(query, model, year: Optional[int], month: Optional[int], day: Optional[int], category: Optional[str] = None):
    if year is not None:
        query = query.filter(func.extract('year', model.created_at) == year)
    if month is not None:
        query = query.filter(func.extract('month', model.created_at) == month)
    if day is not None:
        query = query.filter(func.extract('day', model.created_at) == day)
    if category is not None and hasattr(model, 'category'):
        # Case-insensitive category matching
        query = query.filter(model.category.ilike(category))
    return query

# --- CRUD Endpoints ---

@app.post("/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(expense: ExpenseCreate, db: Session = Depends(get_db)):
    db_expense = models.Expense(**expense.model_dump())
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense

@app.get("/expenses", response_model=List[ExpenseResponse])
def get_all_expenses(db: Session = Depends(get_db)):
    return db.query(models.Expense).all()

@app.get("/expenses/{expense_id}", response_model=ExpenseResponse)
def get_expenses(
    year: Optional[int] = Query(None, description="Filter by year (e.g., 2026)"),
    month: Optional[int] = Query(None, description="Filter by month (1-12)", ge=1, le=12),
    day: Optional[int] = Query(None, description="Filter by day (1-31)", ge=1, le=31),
    category: Optional[str] = Query(None, description="Filter by category (e.g., Food)"),
    db: Session = Depends(get_db)
):
    query = db.query(models.Expense)
    query = apply_filters(query, models.Expense, year, month, day, category)
    return query.all()

@app.put("/expenses/{expense_id}", response_model=ExpenseResponse)
def update_expense(expense_id: int, expense_update: ExpenseUpdate, db: Session = Depends(get_db)):
    db_expense = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if not db_expense:
        raise HTTPException(status_code=404, detail="Expense record not found")
    
    update_data = expense_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_expense, key, value)
        
    db.commit()
    db.refresh(db_expense)
    return db_expense

@app.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    db_expense = db.query(models.Expense).filter(models.Expense.expense_id == expense_id).first()
    if not db_expense:
        raise HTTPException(status_code=404, detail="Expense record not found")
    
    db.delete(db_expense)
    db.commit()
    return None

from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import datetime

import models
from database import engine, get_db
from pdf_generator import generate_pdf_report

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
def index(request: Request, month: str = None, db: Session = Depends(get_db)):
    selected_month = month or datetime.date.today().strftime("%Y-%m")
    
    members = db.query(models.Member).all()
    payments = db.query(models.Payment).filter(models.Payment.month_year == selected_month).all()
    expenses = db.query(models.Expense).all()
    
    # হিসাব-নিকাশ
    total_deposit = sum(p.amount for p in db.query(models.Payment).all())
    total_expense = sum(e.amount for e in expenses)
    current_balance = total_deposit - total_expense
    
    monthly_deposit = sum(p.amount for p in payments)
    monthly_expense = sum(e.amount for e in expenses if e.date.strftime("%Y-%m") == selected_month)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "members": members,
        "payments": {p.member_id: p.amount for p in payments},
        "expenses": expenses,
        "selected_month": selected_month,
        "total_deposit": total_deposit,
        "total_expense": total_expense,
        "current_balance": current_balance,
        "monthly_deposit": monthly_deposit,
        "monthly_expense": monthly_expense
    })

# সদস্য যোগ করা
@app.post("/add-member")
def add_member(name: str = Form(...), address: str = Form(...), db: Session = Depends(get_db)):
    new_member = models.Member(name=name, address=address)
    db.add(new_member)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

# মাস ভিত্তিক জমার টাকা যোগ/আপডেট করা
@app.post("/update-payment")
def update_payment(member_id: int = Form(...), month_year: str = Form(...), amount: float = Form(...), db: Session = Depends(get_db)):
    payment = db.query(models.Payment).filter(
        models.Payment.member_id == member_id, 
        models.Payment.month_year == month_year
    ).first()
    
    if payment:
        payment.amount = amount
    else:
        payment = models.Payment(member_id=member_id, month_year=month_year, amount=amount)
        db.add(payment)
        
    db.commit()
    return RedirectResponse(url=f"/?month={month_year}", status_code=303)

# খরচ যোগ করা
@app.post("/add-expense")
def add_expense(date: str = Form(...), day: str = Form(...), description: str = Form(...), amount: float = Form(...), db: Session = Depends(get_db)):
    exp_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
    new_expense = models.Expense(date=exp_date, day=day, description=description, amount=amount)
    db.add(new_expense)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

# PDF ডাউনলোড
@app.get("/download-pdf/{month_year}")
def download_pdf(month_year: str, db: Session = Depends(get_db)):
    file_path = generate_pdf_report(month_year, db)
    return FileResponse(file_path, media_type='application/pdf', filename=f"Baitul_Mal_{month_year}.pdf")
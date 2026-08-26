from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import models

def generate_pdf_report(month_year, db):
    file_path = f"report_{month_year}.pdf"
    c = canvas.Canvas(file_path, pagesize=A4)
    
    # হেডার
    c.setFont("Helvetica-Bold", 16)
    c.drawString(150, 800, "Pathanpara Subunit - Baitul Mal Report")
    c.setFont("Helvetica", 12)
    c.drawString(220, 780, f"Month: {month_year}")
    
    # সারসংক্ষেপ
    payments = db.query(models.Payment).filter(models.Payment.month_year == month_year).all()
    expenses = db.query(models.Expense).all()
    
    total_dep = sum(p.amount for p in payments)
    total_exp = sum(e.amount for e in expenses if e.date.strftime("%Y-%m") == month_year)
    
    y = 730
    c.drawString(50, y, f"Total Monthly Deposit: Tk {total_dep}")
    c.drawString(300, y, f"Total Monthly Expense: Tk {total_exp}")
    
    c.line(50, y-10, 550, y-10)
    
    # তথ্য তালিকা (সদস্য ও জমা)
    y -= 40
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Member Name")
    c.drawString(300, y, "Amount (Tk)")
    
    c.setFont("Helvetica", 10)
    for p in payments:
        y -= 20
        c.drawString(50, y, p.member.name)
        c.drawString(300, y, str(p.amount))
        
    c.save()
    return file_path
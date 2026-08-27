import datetime
import io
import sqlite3
import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Page Configuration
st.set_page_config(
    page_title="Pathanpara Subunit Baitul Mal", page_icon="", layout="wide"
)

# Database Setup & Migration
conn = sqlite3.connect("baitul_mal.db", check_same_thread=False)
c = conn.cursor()

c.execute(
    """CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            phone TEXT,
            address TEXT
        )"""
)

# Migration check if phone column exists in older database version
c.execute("PRAGMA table_info(members)")
columns = [col[1] for col in c.fetchall()]
if "phone" not in columns:
    c.execute("ALTER TABLE members ADD COLUMN phone TEXT")

c.execute(
    """CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER,
            month_year TEXT,
            amount REAL,
            FOREIGN KEY(member_id) REFERENCES members(id)
        )"""
)

c.execute(
    """CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            day TEXT,
            description TEXT,
            amount REAL
        )"""
)
conn.commit()

# UI CSS with Hind Siliguri Font Support & Clean UI
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;600;700&display=swap');
    
    html, body, [class*="css"], stMarkdown, input, textarea, select {
        font-family: 'Hind Siliguri', sans-serif !important;
    }
    .main { padding: 1.5rem; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; background-color: #0d6efd; color: white; }
    .stButton>button:hover { background-color: #0b5ed7; color: white; }
    </style>
""",
    unsafe_allow_html=True,
)

# App Title Header
st.title("Pathanpara Subunit BM")
st.caption("ICS Pathanpara Subunit Online Database & Financial Management System")

tabs = st.tabs(
    [" Dashboard", " Member & Collections", " Expenses", "PDF"]
)

# ----------------- TAB 1: DASHBOARD -----------------
with tabs[0]:
    st.subheader("Financial Overview")

    c.execute("SELECT SUM(amount) FROM collections")
    total_income = c.fetchone()[0] or 0.0

    c.execute("SELECT SUM(amount) FROM expenses")
    total_expense = c.fetchone()[0] or 0.0

    balance = total_income - total_expense

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Income (Collection)", f"{total_income:,.2f} Tk")
    col2.metric("Total Expense", f"{total_expense:,.2f} Tk")
    col3.metric("Current Cash Balance", f"{balance:,.2f} Tk")

    st.markdown("---")
    st.subheader("Monthly Member Contribution Summary")

    # Dynamic Month-wise Pivot Table
    pivot_query = """
        SELECT m.name AS "Name", m.phone AS "Phone", m.address AS "Address", c.month_year, c.amount
        FROM members m
        LEFT JOIN collections c ON m.id = c.member_id
    """
    df_raw = pd.read_sql_query(pivot_query, conn)

    if not df_raw.empty and df_raw["month_year"].notna().any():
        df_pivot = df_raw.pivot_table(
            index=["Name", "Phone", "Address"],
            columns="month_year",
            values="amount",
            aggfunc="sum",
            fill_value=0.0,
        ).reset_index()

        # Calculate Total Amount per Member
        month_cols = [c for c in df_pivot.columns if c not in ["Name", "Phone", "Address"]]
        df_pivot["Total Amount (Tk)"] = df_pivot[month_cols].sum(axis=1)
    else:
        df_summary_query = """
            SELECT name AS "Name", phone AS "Phone", address AS "Address", 0.0 AS "Total Amount (Tk)"
            FROM members
        """
        df_pivot = pd.read_sql_query(df_summary_query, conn)

    search_term = st.text_input("Search Member by (Name or Phone):")
    if search_term:
        df_pivot = df_pivot[
            df_pivot["Name"].str.contains(search_term, case=False, na=False)
            | df_pivot["Phone"].astype(str).str.contains(search_term, case=False, na=False)
        ]

    st.dataframe(df_pivot, use_container_width=True)

# ----------------- TAB 2: MEMBERS & COLLECTIONS -----------------
with tabs[1]:
    col_a, col_b = st.columns([1, 1])

    with col_a:
        st.subheader("Add New Member")
        new_name = st.text_input("Member Name (Required)")
        new_phone = st.text_input("Phone Number")
        new_address = st.text_input("Address")

        if st.button("Save Member"):
            if new_name.strip():
                try:
                    c.execute(
                        "INSERT INTO members (name, phone, address) VALUES (?, ?, ?)",
                        (new_name.strip(), new_phone.strip(), new_address.strip()),
                    )
                    conn.commit()
                    st.success(f"Member '{new_name}' added successfully!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("A member with this name already exists!")
            else:
                st.warning("Member Name is required!")

    with col_b:
        st.subheader("Monthly Collection Entry")
        members = pd.read_sql_query("SELECT id, name FROM members", conn)

        if not members.empty:
            member_dict = dict(zip(members["name"], members["id"]))
            selected_member = st.selectbox("Select Member", members["name"])

            # Select Month & Year
            selected_date = st.date_input("Select Month & Year", datetime.date.today())
            selected_month = selected_date.strftime("%B %Y")

            # Input with value=None so it remains empty by default
            coll_amount = st.number_input(
                "Amount (Tk)", min_value=0.0, step=10.0, value=None, placeholder="Enter amount..."
            )

            if st.button("Submit Collection"):
                if coll_amount is not None and coll_amount > 0:
                    c.execute(
                        "INSERT INTO collections (member_id, month_year, amount) VALUES (?, ?, ?)",
                        (member_dict[selected_member], selected_month, coll_amount),
                    )
                    conn.commit()
                    st.success(
                        f"Collected {coll_amount} Tk for {selected_member} ({selected_month})."
                    )
                    st.rerun()
                else:
                    st.error("Please enter a valid amount!")
        else:
            st.info("Please add a member on the left panel first.")

    st.markdown("---")
    st.subheader("Collection History (Edit / Delete)")

    all_coll_query = """
        SELECT c.id AS "Entry ID", m.name AS "Member Name", c.month_year AS "Month", c.amount AS "Amount (Tk)"
        FROM collections c
        JOIN members m ON c.member_id = m.id
        ORDER BY c.id DESC
    """
    df_coll = pd.read_sql_query(all_coll_query, conn)

    if not df_coll.empty:
        st.dataframe(df_coll, use_container_width=True)

        selected_id = st.number_input(
            "Enter Entry ID to Edit/Delete", step=1, value=None, placeholder="ID..."
        )
        edit_col1, edit_col2 = st.columns(2)

        with edit_col1:
            new_amt = st.number_input(
                "New Amount (Tk)", min_value=0.0, value=None, placeholder="New amount..."
            )
            if st.button("Update Collection"):
                if selected_id and new_amt is not None:
                    c.execute(
                        "UPDATE collections SET amount = ? WHERE id = ?",
                        (new_amt, selected_id),
                    )
                    conn.commit()
                    st.success("Record updated successfully!")
                    st.rerun()
                else:
                    st.error("Provide valid ID and Amount.")

        with edit_col2:
            if st.button("Delete Collection"):
                if selected_id:
                    c.execute("DELETE FROM collections WHERE id = ?", (selected_id,))
                    conn.commit()
                    st.warning("Record deleted successfully!")
                    st.rerun()
                else:
                    st.error("Provide a valid Entry ID.")

# ----------------- TAB 3: EXPENSES -----------------
with tabs[2]:
    st.subheader("New Expense Entry")

    v_col1, v_col2 = st.columns(2)
    with v_col1:
        exp_date = st.date_input("Expense Date", datetime.date.today())
        exp_day = exp_date.strftime("%A")

    with v_col2:
        exp_desc = st.text_area("Expense Details / Description")
        exp_amount = st.number_input(
            "Expense Amount (Tk)", min_value=0.0, step=10.0, value=None, placeholder="Enter amount..."
        )

    if st.button("Save Expense"):
        if exp_amount is not None and exp_amount > 0 and exp_desc.strip():
            c.execute(
                "INSERT INTO expenses (date, day, description, amount) VALUES (?, ?, ?, ?)",
                (str(exp_date), exp_day, exp_desc.strip(), exp_amount),
            )
            conn.commit()
            st.success("Expense recorded successfully!")
            st.rerun()
        else:
            st.error("Please enter a valid description and amount.")

    st.markdown("---")
    st.subheader("Expense List")
    df_exp = pd.read_sql_query(
        """SELECT ROW_NUMBER() OVER (ORDER BY id DESC) AS 'SL No.', 
                  date AS 'Date', 
                  day AS 'Day', 
                  description AS 'Description', 
                  amount AS 'Amount (Tk)' 
           FROM expenses ORDER BY id DESC""",
        conn,
    )
    st.dataframe(df_exp, use_container_width=True)

# ----------------- TAB 4: PDF EXPORT -----------------
with tabs[3]:
    st.subheader("Download Monthly PDF Report")

    c.execute("SELECT DISTINCT month_year FROM collections")
    months = [row[0] for row in c.fetchall()]

    if months:
        pdf_month = st.selectbox("Select Month for PDF Report:", months)

        if st.button("Generate PDF Report"):
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
            )
            elements = []
            styles = getSampleStyleSheet()

            # Header Titles
            elements.append(
                Paragraph(
                    "<b>Pathanpara Subunit Baitul Mal</b>", styles["Title"]
                )
            )
            elements.append(
                Paragraph(f"<b>Monthly Collection Report: {pdf_month}</b>", styles["Heading2"])
            )
            elements.append(Spacer(1, 15))

            # Fetch monthly collection data
            m_query = """
                SELECT m.name, m.phone, m.address, c.amount 
                FROM collections c
                JOIN members m ON c.member_id = m.id
                WHERE c.month_year = ?
            """
            c.execute(m_query, (pdf_month,))
            rows = c.fetchall()

            data = [["SL", "Name", "Phone", "Address", "Amount (Tk)"]]
            total_m_amt = 0.0

            for idx, row in enumerate(rows, 1):
                data.append([str(idx), str(row[0]), str(row[1] or ""), str(row[2] or ""), f"{row[3]:,.2f}"])
                total_m_amt += row[3]

            data.append(["", "Total Collection", "", "", f"{total_m_amt:,.2f}"])

            t = Table(data, colWidths=[30, 140, 90, 150, 90])
            t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e9ecef")),
                        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ]
                )
            )

            elements.append(t)
            doc.build(elements)

            buffer.seek(0)
            st.download_button(
                label=" Download PDF File",
                data=buffer,
                file_name=f"Baitul_Mal_Report_{pdf_month.replace(' ', '_')}.pdf",
                mime="application/pdf",
            )
    else:
        st.info("No collection entries found to generate PDF.")
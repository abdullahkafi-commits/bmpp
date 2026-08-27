import io
import datetime
import pandas as pd
import sqlite3
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

# Page Configuration
st.set_page_config(page_title="বাইতুল মাল ব্যবস্থাপনা", page_icon="💰", layout="wide")

# Database Setup
conn = sqlite3.connect("baitul_mal.db", check_same_thread=False)
c = conn.cursor()

c.execute(
    """CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            address TEXT
        )"""
)

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
            voucher_no TEXT,
            date TEXT,
            day TEXT,
            description TEXT,
            amount REAL
        )"""
)
conn.commit()

# UI CSS for Minimal & Professional Look
st.markdown(
    """
    <style>
    .main { padding: 1rem; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    .metric-card { background-color: #f8f9fa; border-radius: 10px; padding: 15px; border-left: 5px solid #007bff; }
    </style>
""",
    unsafe_allow_html=True,
)

# App Header
st.title("💰 পাঠানপাড়া সাব-ইউনিট বাইতুল মাল")
st.caption("ICS পাঠানপাড়া সাব-ইউনিট অনলাইন ডাটাবেস ও হিসাব ব্যবস্থাপনা")

tabs = st.tabs(
    ["📊 ড্যাশবোর্ড", "👥 সদস্য সংগ্রহ", "💸 খরচ (Voucher)", "📄 PDF রিপোর্ট"]
)

# ----------------- Tab 1: Dashboard -----------------
with tabs[0]:
    st.subheader("হিসাবের সারসংক্ষেপ")

    # Fetch total stats
    c.execute("SELECT SUM(amount) FROM collections")
    total_income = c.fetchone()[0] or 0.0

    c.execute("SELECT SUM(amount) FROM expenses")
    total_expense = c.fetchone()[0] or 0.0

    balance = total_income - total_expense

    col1, col2, col3 = st.columns(3)
    col1.metric("মোট আদায়", f"{total_income:,.2f} টাকা")
    col2.metric("মোট খরচ", f"{total_expense:,.2f} টাকা")
    col3.metric("বর্তমান ক্যাশ", f"{balance:,.2f} টাকা")

    st.markdown("---")
    st.subheader("সদস্যদের মোট প্রদানের তালিকা")

    query = """
        SELECT m.name AS 'নাম', m.address AS 'ঠিকানা', COALESCE(SUM(c.amount), 0) AS 'মোট টাকা'
        FROM members m
        LEFT JOIN collections c ON m.id = c.member_id
        GROUP BY m.id
    """
    df_summary = pd.read_sql_query(query, conn)

    search_term = st.text_input("🔍 সদস্য খুঁজুন (নাম দিয়ে):")
    if search_term:
        df_summary = df_summary[
            df_summary["নাম"].str.contains(search_term, case=False, na=False)
        ]

    st.dataframe(df_summary, use_container_width=True)

# ----------------- Tab 2: Members & Income -----------------
with tabs[1]:
    col_a, col_b = st.columns([1, 1])

    with col_a:
        st.subheader("নতুন সদস্য যোগ করুন")
        new_name = st.text_input("সদস্যের নাম (একবারই এন্ট্রি করতে হবে)")
        new_address = st.text_input("ঠিকানা")

        if st.button("সদস্য যুক্ত করুন"):
            if new_name.strip():
                try:
                    c.execute(
                        "INSERT INTO members (name, address) VALUES (?, ?)",
                        (new_name.strip(), new_address.strip()),
                    )
                    conn.commit()
                    st.success(f"{new_name} সফলভাবে যুক্ত হয়েছে!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("এই নামের সদস্য ইতিমধ্যে ডাটাবেসে আছে!")
            else:
                st.warning("নাম আবশ্যক!")

    with col_b:
        st.subheader("মাসিক টাকা এন্ট্রি")
        members = pd.read_sql_query("SELECT id, name FROM members", conn)

        if not members.empty:
            member_dict = dict(zip(members["name"], members["id"]))
            selected_member_name = st.selectbox("সদস্য নির্বাচন করুন", members["name"])
            selected_month = st.date_input(
                "মাস ও বছর নির্বাচন করুন", datetime.date.today()
            ).strftime("%B %Y")
            coll_amount = st.number_input("টাকার পরিমাণ (Tk)", min_value=0.0, step=10.0)

            if st.button("টাকা জমা করুন"):
                c.execute(
                    "INSERT INTO collections (member_id, month_year, amount) VALUES (?, ?, ?)",
                    (member_dict[selected_member_name], selected_month, coll_amount),
                )
                conn.commit()
                st.success(
                    f"{selected_member_name}-এর {selected_month} মাসের {coll_amount} টাকা যোগ হয়েছে।"
                )
        else:
            st.info("প্রথমে বাম দিকে নতুন সদস্য যোগ করুন।")

    st.markdown("---")
    st.subheader("আদায়ের ইতিহাস সম্পাদনা ও ডিলেট")

    all_coll_query = """
        SELECT c.id, m.name AS 'নাম', c.month_year AS 'মাস', c.amount AS 'টাকা'
        FROM collections c
        JOIN members m ON c.member_id = m.id
        ORDER BY c.id DESC
    """
    df_coll = pd.read_sql_query(all_coll_query, conn)

    if not df_coll.empty:
        st.dataframe(df_coll, use_container_width=True)

        selected_id = st.number_input("সম্পাদনা বা ডিলেটের জন্য Entry ID দিন", step=1)
        edit_col1, edit_col2 = st.columns(2)

        with edit_col1:
            new_amt = st.number_input("নতুন টাকার পরিমাণ", min_value=0.0)
            if st.button("টাকা আপডেট করুন"):
                c.execute(
                    "UPDATE collections SET amount = ? WHERE id = ?",
                    (new_amt, selected_id),
                )
                conn.commit()
                st.success("আপডেট সফল হয়েছে!")
                st.rerun()

        with edit_col2:
            if st.button("এন্ট্রি ডিলেট করুন"):
                c.execute("DELETE FROM collections WHERE id = ?", (selected_id,))
                conn.commit()
                st.warning("এন্ট্রি ডিলেট করা হয়েছে!")
                st.rerun()

# ----------------- Tab 3: Expenses (Voucher) -----------------
with tabs[2]:
    st.subheader("নতুন ভাউচার এন্ট্রি (খরচ)")

    v_col1, v_col2 = st.columns(2)
    with v_col1:
        v_no = st.text_input("ভাউচার নম্বর")
        v_date = st.date_input("তারিখ", datetime.date.today())
        v_day = v_date.strftime("%A")

    with v_col2:
        v_desc = st.text_area("খরচের বিবরণ (কি কি কাজে খরচ হয়েছে)")
        v_amount = st.number_input("খরচের পরিমাণ (Tk)", min_value=0.0, step=10.0)

    if st.button("ভাউচার সেভ করুন"):
        if v_no and v_amount > 0:
            c.execute(
                "INSERT INTO expenses (voucher_no, date, day, description, amount) VALUES (?, ?, ?, ?, ?)",
                (v_no, str(v_date), v_day, v_desc, v_amount),
            )
            conn.commit()
            st.success("খরচের এন্ট্রি সেভ করা হয়েছে!")
            st.rerun()
        else:
            st.error("ভাউচার নম্বর এবং টাকার পরিমাণ সঠিকভাবে লিখুন।")

    st.markdown("---")
    st.subheader("খরচের তালিকা")
    df_exp = pd.read_sql_query(
        "SELECT id, voucher_no AS 'ভাউচার', date AS 'তারিখ', day AS 'দিন', description AS 'বিবরণ', amount AS 'টাকা' FROM expenses ORDER BY id DESC",
        conn,
    )
    st.dataframe(df_exp, use_container_width=True)

# ----------------- Tab 4: PDF Export -----------------
with tabs[3]:
    st.subheader("মাসভিত্তিক PDF ডাউনলোড")

    c.execute("SELECT DISTINCT month_year FROM collections")
    months = [row[0] for row in c.fetchall()]

    if months:
        pdf_month = st.selectbox("যে মাসের রিপোর্ট ডাউনলোড করতে চান:", months)

        if st.button("PDF জেনারেট করুন"):
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()

            # Header Text
            elements.append(
                Paragraph(
                    f"<b>ICS Pathanpara Subunit Baitul Mal Report</b>", styles["Heading1"]
                )
            )
            elements.append(Paragraph(f"Month: {pdf_month}", styles["Heading2"]))
            elements.append(Spacer(1, 12))

            # Fetch monthly data
            m_query = """
                SELECT m.name, m.address, c.amount 
                FROM collections c
                JOIN members m ON c.member_id = m.id
                WHERE c.month_year = ?
            """
            c.execute(m_query, (pdf_month,))
            data = [["Name", "Address", "Amount (Tk)"]]
            total_m_amt = 0
            for row in c.fetchall():
                data.append([row[0], row[1], str(row[2])])
                total_m_amt += row[2]

            data.append(["Total", "", str(total_m_amt)])

            t = Table(data)
            t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, -1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )

            elements.append(t)
            doc.build(elements)

            buffer.seek(0)
            st.download_button(
                label="📥 PDF ফাইল ডাউনলোড করুন",
                data=buffer,
                file_name=f"Baitul_Mal_{pdf_month}.pdf",
                mime="application/pdf",
            )
    else:
        st.info("এখনো কোনো জমা এন্ট্রি করা হয়নি।")
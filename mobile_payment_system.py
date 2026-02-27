"""
Secure Multi-User Mobile Payment Simulation System Using Python and MySQL
Class 12 Computer Science Project
"""

import hashlib
import random
import uuid
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk

import mysql.connector
from mysql.connector import Error

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# ==========================================================
# Database Credentials (edit these as per your local setup)
# ==========================================================
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "root"
DB_NAME = "mobile_payment_system"
DB_PORT = 3306

# Transaction safety constants
MAX_TRANSACTION_LIMIT = 99999
POLLING_INTERVAL_MS = 5000


class DatabaseManager:
    """All database-related logic is handled in this class."""

    def __init__(self):
        self.connection = None

    def connect(self):
        """Create and return a MySQL connection."""
        try:
            self.connection = mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                port=DB_PORT,
                autocommit=False,
            )
            return self.connection
        except Error as error:
            raise ConnectionError(f"Database connection failed: {error}") from error

    def close(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()

    @staticmethod
    def hash_password(password):
        """Return SHA-256 hash of password."""
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_wallet_uid():
        """Generate wallet UID using uuid.uuid4().hex (mandatory requirement)."""
        return uuid.uuid4().hex

    @staticmethod
    def generate_txn_id():
        """Generate transaction ID using TXN- + uuid.uuid4().hex (mandatory requirement)."""
        return "TXN-" + uuid.uuid4().hex

    @staticmethod
    def generate_bank_uid():
        """Generate bank UID as BANK- + 8 random digits (mandatory requirement)."""
        return f"BANK-{random.randint(10000000, 99999999)}"

    def register_user(self, name, username, password, initial_balance):
        """Register a new user with secure IDs and hashed password."""
        password_hash = self.hash_password(password)
        wallet_uid = self.generate_wallet_uid()
        bank_uid = self.generate_bank_uid()

        query = (
            "INSERT INTO users (name, username, password_hash, wallet_uid, bank_uid, balance) "
            "VALUES (%s, %s, %s, %s, %s, %s)"
        )

        cursor = self.connection.cursor()
        try:
            cursor.execute(query, (name, username, password_hash, wallet_uid, bank_uid, initial_balance))
            self.connection.commit()
            return {"wallet_uid": wallet_uid, "bank_uid": bank_uid}
        except Error:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    def login_user(self, username, password):
        """Validate user login using username + hashed password."""
        password_hash = self.hash_password(password)
        query = (
            "SELECT user_id, name, username, wallet_uid, bank_uid, balance "
            "FROM users WHERE username = %s AND password_hash = %s"
        )

        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute(query, (username, password_hash))
            return cursor.fetchone()
        finally:
            cursor.close()

    def get_user_by_wallet(self, wallet_uid):
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE wallet_uid = %s", (wallet_uid,))
            return cursor.fetchone()
        finally:
            cursor.close()

    def get_balance(self, wallet_uid):
        cursor = self.connection.cursor()
        try:
            cursor.execute("SELECT balance FROM users WHERE wallet_uid = %s", (wallet_uid,))
            result = cursor.fetchone()
            return float(result[0]) if result else 0.0
        finally:
            cursor.close()

    def transfer_money(self, sender_uid, receiver_uid, amount):
        """Transfer wallet balance atomically with transaction safety."""
        if amount <= 0:
            return False, "Amount must be greater than 0.", None
        if amount > MAX_TRANSACTION_LIMIT:
            return False, f"Maximum transaction limit is ₹{MAX_TRANSACTION_LIMIT}.", None
        if sender_uid == receiver_uid:
            return False, "Sender and receiver wallet UIDs cannot be the same.", None

        cursor = self.connection.cursor(dictionary=True)
        txn_id = self.generate_txn_id()
        txn_type = "WALLET_TO_WALLET"
        date_time = datetime.now()

        try:
            self.connection.start_transaction()

            cursor.execute("SELECT balance FROM users WHERE wallet_uid = %s FOR UPDATE", (sender_uid,))
            sender = cursor.fetchone()
            if not sender:
                self.connection.rollback()
                return False, "Sender wallet not found.", None

            cursor.execute("SELECT balance FROM users WHERE wallet_uid = %s FOR UPDATE", (receiver_uid,))
            receiver = cursor.fetchone()
            if not receiver:
                self.connection.rollback()
                return False, "Receiver wallet UID does not exist.", None

            sender_balance = float(sender["balance"])
            if sender_balance < amount:
                self.connection.rollback()
                return False, "Insufficient balance.", None

            cursor.execute(
                "UPDATE users SET balance = balance - %s WHERE wallet_uid = %s",
                (amount, sender_uid),
            )
            cursor.execute(
                "UPDATE users SET balance = balance + %s WHERE wallet_uid = %s",
                (amount, receiver_uid),
            )
            cursor.execute(
                "INSERT INTO transactions (txn_id, sender_uid, receiver_uid, amount, txn_type, date_time, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (txn_id, sender_uid, receiver_uid, amount, txn_type, date_time, "SUCCESS"),
            )

            self.connection.commit()
            return True, "Transaction successful.", txn_id

        except Error as error:
            self.connection.rollback()
            return False, f"Transaction failed: {error}", None
        finally:
            cursor.close()

    def get_recent_transactions(self, wallet_uid):
        """Get last 30 minutes transactions for current user."""
        query = (
            "SELECT * FROM transactions "
            "WHERE date_time >= NOW() - INTERVAL 30 MINUTE "
            "AND (sender_uid = %s OR receiver_uid = %s) "
            "ORDER BY date_time DESC"
        )
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute(query, (wallet_uid, wallet_uid))
            return cursor.fetchall()
        finally:
            cursor.close()

    def get_new_incoming_transactions(self, wallet_uid):
        """Check incoming transactions in last 30 minutes for notification popup."""
        query = (
            "SELECT txn_id, sender_uid, amount, date_time FROM transactions "
            "WHERE receiver_uid = %s AND date_time >= NOW() - INTERVAL 30 MINUTE "
            "ORDER BY date_time DESC"
        )
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute(query, (wallet_uid,))
            return cursor.fetchall()
        finally:
            cursor.close()


class ReceiptManager:
    """Generate PDF receipts using reportlab.platypus."""

    @staticmethod
    def generate_receipt(txn_details):
        file_name = f"receipt_{txn_details['txn_id']}.pdf"

        document = SimpleDocTemplate(file_name, pagesize=A4)
        styles = getSampleStyleSheet()

        elements = []
        elements.append(Paragraph("Mobile Payment Transaction Receipt", styles["Title"]))
        elements.append(Spacer(1, 12))

        data = [
            ["Field", "Value"],
            ["Transaction ID", txn_details["txn_id"]],
            ["Sender UID", txn_details["sender_uid"]],
            ["Receiver UID", txn_details["receiver_uid"]],
            ["Amount", f"₹{txn_details['amount']:.2f}"],
            ["Date and Time", str(txn_details["date_time"])],
            ["Transaction Type", txn_details["txn_type"]],
            ["Status", txn_details["status"]],
        ]

        table = Table(data, colWidths=[180, 320])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )

        elements.append(table)
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("This is a system-generated receipt.", styles["Normal"]))

        document.build(elements)
        return file_name


class MobilePaymentApp:
    """Tkinter GUI logic."""

    def __init__(self, root):
        self.root = root
        self.root.title("Secure Mobile Payment Simulation System")
        self.root.geometry("950x650")

        self.db_manager = DatabaseManager()
        self.current_user = None
        self.notified_transactions = set()

        try:
            self.db_manager.connect()
        except ConnectionError as error:
            messagebox.showerror("Database Error", str(error))
            self.root.destroy()
            return

        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.show_login_screen()

    def clear_frame(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def show_login_screen(self):
        self.clear_frame()

        tk.Label(self.main_frame, text="Login", font=("Arial", 20, "bold")).pack(pady=15)

        tk.Label(self.main_frame, text="Username").pack()
        username_entry = tk.Entry(self.main_frame, width=30)
        username_entry.pack(pady=5)

        tk.Label(self.main_frame, text="Password").pack()
        password_entry = tk.Entry(self.main_frame, width=30, show="*")
        password_entry.pack(pady=5)

        def login_action():
            username = username_entry.get().strip()
            password = password_entry.get().strip()

            if not username or not password:
                messagebox.showwarning("Input Error", "Please enter username and password.")
                return

            user = self.db_manager.login_user(username, password)
            if user:
                self.current_user = user
                self.notified_transactions.clear()
                self.show_dashboard()
            else:
                messagebox.showerror("Login Failed", "Invalid username or password.")

        tk.Button(self.main_frame, text="Login", width=20, command=login_action).pack(pady=10)
        tk.Button(
            self.main_frame,
            text="New User? Register",
            width=20,
            command=self.show_register_screen,
        ).pack()

    def show_register_screen(self):
        self.clear_frame()

        tk.Label(self.main_frame, text="User Registration", font=("Arial", 20, "bold")).pack(pady=15)

        tk.Label(self.main_frame, text="Full Name").pack()
        name_entry = tk.Entry(self.main_frame, width=35)
        name_entry.pack(pady=4)

        tk.Label(self.main_frame, text="Username").pack()
        username_entry = tk.Entry(self.main_frame, width=35)
        username_entry.pack(pady=4)

        tk.Label(self.main_frame, text="Password").pack()
        password_entry = tk.Entry(self.main_frame, width=35, show="*")
        password_entry.pack(pady=4)

        tk.Label(self.main_frame, text="Initial Balance (₹)").pack()
        balance_entry = tk.Entry(self.main_frame, width=35)
        balance_entry.insert(0, "0")
        balance_entry.pack(pady=4)

        def register_action():
            name = name_entry.get().strip()
            username = username_entry.get().strip()
            password = password_entry.get().strip()
            balance_text = balance_entry.get().strip()

            if not name or not username or not password or not balance_text:
                messagebox.showwarning("Input Error", "All fields are required.")
                return

            try:
                initial_balance = float(balance_text)
                if initial_balance < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Input Error", "Initial balance must be a non-negative number.")
                return

            try:
                ids = self.db_manager.register_user(name, username, password, initial_balance)
                messagebox.showinfo(
                    "Registration Successful",
                    f"User registered successfully!\nWallet UID: {ids['wallet_uid']}\nBank UID: {ids['bank_uid']}",
                )
                self.show_login_screen()
            except Error as error:
                messagebox.showerror("Registration Failed", f"Could not register user: {error}")

        tk.Button(self.main_frame, text="Register", width=20, command=register_action).pack(pady=8)
        tk.Button(self.main_frame, text="Back to Login", width=20, command=self.show_login_screen).pack()

    def show_dashboard(self):
        self.clear_frame()

        title_text = f"Welcome, {self.current_user['name']}"
        tk.Label(self.main_frame, text=title_text, font=("Arial", 18, "bold")).pack(pady=8)

        wallet_text = f"Wallet UID: {self.current_user['wallet_uid']}"
        tk.Label(self.main_frame, text=wallet_text, font=("Arial", 11)).pack()

        self.balance_label = tk.Label(self.main_frame, text="", font=("Arial", 14, "bold"), fg="green")
        self.balance_label.pack(pady=8)
        self.refresh_balance()

        transfer_frame = tk.LabelFrame(self.main_frame, text="Wallet-to-Wallet Transfer", padx=10, pady=10)
        transfer_frame.pack(fill="x", pady=8)

        tk.Label(transfer_frame, text="Receiver Wallet UID").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        receiver_entry = tk.Entry(transfer_frame, width=45)
        receiver_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(transfer_frame, text="Amount (₹)").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        amount_entry = tk.Entry(transfer_frame, width=45)
        amount_entry.grid(row=1, column=1, padx=5, pady=5)

        def transfer_action():
            receiver_uid = receiver_entry.get().strip()
            amount_text = amount_entry.get().strip()

            if not receiver_uid or not amount_text:
                messagebox.showwarning("Input Error", "Receiver UID and amount are required.")
                return

            try:
                amount = float(amount_text)
            except ValueError:
                messagebox.showerror("Input Error", "Amount must be a numeric value.")
                return

            success, message, txn_id = self.db_manager.transfer_money(
                self.current_user["wallet_uid"],
                receiver_uid,
                amount,
            )

            if success:
                txn_details = {
                    "txn_id": txn_id,
                    "sender_uid": self.current_user["wallet_uid"],
                    "receiver_uid": receiver_uid,
                    "amount": amount,
                    "txn_type": "WALLET_TO_WALLET",
                    "date_time": datetime.now(),
                    "status": "SUCCESS",
                }
                receipt_path = ReceiptManager.generate_receipt(txn_details)
                messagebox.showinfo("Success", f"{message}\nReceipt generated: {receipt_path}")
                receiver_entry.delete(0, tk.END)
                amount_entry.delete(0, tk.END)
                self.refresh_balance()
                self.load_transactions()
            else:
                messagebox.showerror("Transaction Error", message)

        tk.Button(transfer_frame, text="Send Money", width=18, command=transfer_action).grid(
            row=2, column=1, padx=5, pady=8, sticky="e"
        )

        controls_frame = tk.Frame(self.main_frame)
        controls_frame.pack(fill="x", pady=8)

        tk.Button(controls_frame, text="Refresh", width=14, command=self.refresh_dashboard).pack(side="left", padx=5)
        tk.Button(controls_frame, text="Logout", width=14, command=self.logout).pack(side="right", padx=5)

        tk.Label(
            self.main_frame,
            text="Last 30 minutes transactions",
            font=("Arial", 12, "bold"),
        ).pack(pady=5)

        columns = ("txn_id", "sender_uid", "receiver_uid", "amount", "txn_type", "date_time", "status")
        self.txn_tree = ttk.Treeview(self.main_frame, columns=columns, show="headings", height=12)

        for col in columns:
            self.txn_tree.heading(col, text=col.upper())
            width = 125 if col in ("txn_id", "sender_uid", "receiver_uid") else 100
            self.txn_tree.column(col, width=width, anchor="center")

        self.txn_tree.pack(fill="both", expand=True, pady=8)
        self.load_transactions()

        self.check_notifications_polling()

    def refresh_balance(self):
        balance = self.db_manager.get_balance(self.current_user["wallet_uid"])
        self.balance_label.config(text=f"Current Balance: ₹{balance:.2f}")

    def load_transactions(self):
        for item in self.txn_tree.get_children():
            self.txn_tree.delete(item)

        transactions = self.db_manager.get_recent_transactions(self.current_user["wallet_uid"])
        for txn in transactions:
            self.txn_tree.insert(
                "",
                "end",
                values=(
                    txn["txn_id"],
                    txn["sender_uid"],
                    txn["receiver_uid"],
                    f"₹{float(txn['amount']):.2f}",
                    txn["txn_type"],
                    txn["date_time"],
                    txn["status"],
                ),
            )

    def refresh_dashboard(self):
        self.refresh_balance()
        self.load_transactions()

    def check_notifications_polling(self):
        if not self.current_user:
            return

        try:
            incoming = self.db_manager.get_new_incoming_transactions(self.current_user["wallet_uid"])
            new_items = [txn for txn in incoming if txn["txn_id"] not in self.notified_transactions]

            if new_items:
                latest = new_items[0]
                messagebox.showinfo(
                    "Incoming Payment Notification",
                    (
                        f"New payment received!\n\n"
                        f"Txn ID: {latest['txn_id']}\n"
                        f"From: {latest['sender_uid']}\n"
                        f"Amount: ₹{float(latest['amount']):.2f}\n"
                        f"Time: {latest['date_time']}"
                    ),
                )
                for txn in new_items:
                    self.notified_transactions.add(txn["txn_id"])
                self.refresh_dashboard()

        except Error:
            pass

        self.root.after(POLLING_INTERVAL_MS, self.check_notifications_polling)

    def logout(self):
        self.current_user = None
        self.show_login_screen()

    def on_closing(self):
        self.db_manager.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MobilePaymentApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

import pyodbc
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import streamlit as st
load_dotenv()

def fetch_sendungen(kundennummer: str) -> pd.DataFrame:
    server = st.secrets.POSTTEST.MSQL_Server 
    database = 'SAS'
    conn_str = (
        f'DRIVER={{SQL Server}};'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'Trusted_Connection=yes;'
    )

    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # 30 Tage zurück
        date_30_days_ago = (datetime.today() - timedelta(days=30)).strftime('%Y%m%d')

        query = """
            SELECT poan8, po56paknr, po56dtrfpl
            FROM [SAS].[dbo].[F564205A]
            WHERE poan8 = ? AND po56dtrfpl > ?
        """

        cursor.execute(query, kundennummer, date_30_days_ago)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        df = pd.DataFrame.from_records(rows, columns=columns)

        # Tracking-Link als klickbarer Link
        df["Tracking-Link"] = df["po56paknr"].apply(
            lambda x: f"[📦 PostLink](http://www.post.ch/track?formattedParcelCodes=99361208780{x})"
        )

        cursor.close()
        conn.close()

        return df

    except Exception as e:
        raise RuntimeError(f"Fehler bei Datenbankzugriff: {e}")

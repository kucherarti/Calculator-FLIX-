st.markdown("""
<style>
.main-title {
    font-size: 38px;
    font-weight: 700;
    color: #3FA7A3;
    margin-bottom: 0;
}
.sub-title {
    font-size: 16px;
    color: #4F6F6B;
    margin-top: 4px;
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    "<div class='main-title'>⚡ FLIX – Kalkulator energii</div>"
    "<div class='sub-title'>Dynamiczna cena energii oparta o TGE</div>",
    unsafe_allow_html=True
)

st.markdown("---")

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# ===============================
# Konfiguracja strony
# ===============================
st.set_page_config(page_title="FLIX – Kalkulator FLIX", layout="centered")
st.title("⚡ FLIX – Kalkulator ceny energii (FLIX)")

# ===============================
# 1️⃣ Składniki dodatkowe
# ===============================
st.header("1️⃣ Składniki dodatkowe (certyfikaty, prawa majątkowe, umorzenie)")
skladnik_dodatkowy = st.number_input(
    "Kwota składnika dodatkowego [zł/MWh]",
    value=160.0
)

# ===============================
# 2️⃣ Dane klienta
# ===============================
st.header("2️⃣ Dane klienta")
zuzycie_roczne = st.number_input(
    "Zużycie roczne klienta [MWh]",
    value=600.0
)
cena_aktualna_klienta = st.number_input(
    "Aktualna cena klienta [zł/MWh]",
    value=700.0
)

# ===============================
# 3️⃣ Profil poboru energii
# ===============================
st.header("3️⃣ Profil poboru energii (24h)")
wysoki_start = st.number_input("Godzina zwiększonego poboru – start", 0, 23, 8)
wysoki_end = st.number_input("Godzina zwiększonego poboru – koniec", 1, 24, 16)
waga_wysoka = st.number_input(
    "Współczynnik zwiększonego poboru",
    value=2.0,
    step=0.1
)

# ===============================
# 4️⃣ Dane TGE (CSV)
# ===============================
st.header("4️⃣ Dane TGE (CSV)")

def wczytaj_csv(file):
    try:
        df = pd.read_csv(file, sep=None, engine="python")
        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
            .str.replace("﻿", "", regex=False)
        )

        col_data, col_price = None, None
        for c in df.columns:
            if c in ["data", "date", "datetime"]:
                col_data = c
            if "fixing_i_price" in c:
                col_price = c

        if col_data is None or col_price is None:
            st.error(f"Nie znaleziono wymaganych kolumn. Wykryte: {list(df.columns)}")
            return None

        df = df.rename(columns={
            col_data: "Data",
            col_price: "fixing_i_price"
        })

        df["Data"] = pd.to_datetime(
            df["Data"],
            dayfirst=True,
            format="mixed",
            errors="coerce"
        )
        df = df.dropna(subset=["Data"])

        df["fixing_i_price"] = (
            df["fixing_i_price"]
            .astype(str)
            .str.replace(",", ".")
            .astype(float)
        )

        return df

    except Exception as e:
        st.error(f"Błąd wczytania CSV: {e}")
        return None


uploaded_file = st.file_uploader("Wgraj CSV TGE", type="csv")
tge_df = wczytaj_csv(uploaded_file) if uploaded_file else None

# Dane przykładowe
if tge_df is None:
    dates = pd.date_range("2024-01-01", "2024-12-31 23:00", freq="H")
    tge_df = pd.DataFrame({
        "Data": dates,
        "fixing_i_price": 430 + (dates.hour % 6) * 7 + dates.month
    })
    st.info("Użyto przykładowych danych TGE")

# ===============================
# 5️⃣ Profil godzinowy + cena FLIX
# ===============================
st.header("5️⃣ Wyliczenie ceny FLIX (TGE + składnik dodatkowy)")

tge_df["Godzina"] = tge_df["Data"].dt.hour

tge_df["Waga"] = 1.0
tge_df.loc[
    (tge_df["Godzina"] >= wysoki_start) &
    (tge_df["Godzina"] < wysoki_end),
    "Waga"
] = waga_wysoka

# 👉 CENA FLIX = CENA TGE + SKŁADNIK
tge_df["Cena_FLIX"] = tge_df["fixing_i_price"] + skladnik_dodatkowy

# ===============================
# 6️⃣ Analiza miesięczna (IV–IX)
# ===============================
tge_df = tge_df[tge_df["Data"].dt.month.isin([4, 5, 6, 7, 8, 9])]
tge_df["Miesiąc"] = tge_df["Data"].dt.to_period("M")

monthly = (
    tge_df
    .groupby("Miesiąc")
    .agg(
        Cena_FLIX_1MWh=(
            "Cena_FLIX",
            lambda x: (
                (x * tge_df.loc[x.index, "Waga"]).sum()
                / tge_df.loc[x.index, "Waga"].sum()
            )
        )
    )
    .reset_index()
)

monthly["Miesiąc"] = monthly["Miesiąc"].astype(str)
monthly["Zużycie_miesięczne_MWh"] = zuzycie_roczne / 12
monthly["Koszt_FLIX_zł"] = monthly["Cena_FLIX_1MWh"] * monthly["Zużycie_miesięczne_MWh"]
monthly["Koszt_aktualny_zł"] = cena_aktualna_klienta * monthly["Zużycie_miesięczne_MWh"]
monthly["Oszczędność_zł"] = monthly["Koszt_aktualny_zł"] - monthly["Koszt_FLIX_zł"]

# ===============================
# 7️⃣ Tabela wyników
# ===============================
st.header("6️⃣ Analiza miesięczna – kwiecień–wrzesień")

st.dataframe(
    monthly.rename(columns={
        "Cena_FLIX_1MWh": "Średnia cena FLIX 1 MWh [zł]",
        "Zużycie_miesięczne_MWh": "Zużycie miesięczne [MWh]",
        "Koszt_FLIX_zł": "Koszt FLIX [zł]",
        "Koszt_aktualny_zł": "Koszt aktualny [zł]",
        "Oszczędność_zł": "Oszczędność [zł]"
    })
)

# ===============================
# 8️⃣ Stała cena – I i IV kwartał
# ===============================
st.header("7️⃣ Stała cena 1 MWh – I i IV kwartał")

cena_stala = 460 + skladnik_dodatkowy

st.dataframe(pd.DataFrame({
    "Kwartał": ["I kwartał", "IV kwartał"],
    "Cena stała 1 MWh [zł]": [cena_stala, cena_stala]
}))

# ===============================
# 9️⃣ Wykres – ceny 1 MWh
# ===============================
st.header("📊 Średnia cena FLIX vs aktualna cena klienta")

fig, ax = plt.subplots()
ax.plot(monthly["Miesiąc"], monthly["Cena_FLIX_1MWh"], marker="o", label="FLIX 1 MWh")
ax.plot(
    monthly["Miesiąc"],
    [cena_aktualna_klienta] * len(monthly),
    linestyle="--",
    label="Aktualna cena klienta"
)
ax.set_ylabel("Cena [zł/MWh]")
ax.set_title("Porównanie cen 1 MWh")
ax.grid(True)
ax.legend()
st.pyplot(fig)

# ===============================
# 🔟 Wykres – koszt miesięczny
# ===============================
st.header("📈 Koszt energii miesięcznie")

fig2, ax2 = plt.subplots()
ax2.plot(monthly["Miesiąc"], monthly["Koszt_FLIX_zł"], marker="o", label="Koszt FLIX")
ax2.plot(
    monthly["Miesiąc"],
    monthly["Koszt_aktualny_zł"],
    linestyle="--",
    label="Koszt aktualny"
)
ax2.set_ylabel("Koszt [zł]")
ax2.set_title("Koszt energii (kwiecień–wrzesień)")
ax2.grid(True)
ax2.legend()
st.pyplot(fig2)

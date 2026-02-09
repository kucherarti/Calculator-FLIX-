# ===============================
# IMPORTY
# ===============================
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# ===============================
# KONFIGURACJA STRONY
# ===============================
st.set_page_config(
    page_title="FLIX – Kalkulator energii",
    layout="centered"
)

# ===============================
# CSS – SIDEBAR + STYL
# ===============================
st.markdown("""
<style>
[data-testid="stSidebar"] {
    background-color: #F4F8F8;
}

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

# ===============================
# NAGŁÓWEK
# ===============================
st.markdown(
    "<div class='main-title'>⚡ FLIX – Kalkulator ceny energii</div>"
    "<div class='sub-title'>Dynamiczna cena oparta o TGE + składnik K</div>",
    unsafe_allow_html=True
)
st.markdown("---")

# ===============================
# SIDEBAR – PARAMETRY
# ===============================
st.sidebar.title("⚙️ Parametry kalkulacji")

skladnik_dodatkowy = st.sidebar.number_input(
    "Składnik dodatkowy [zł/MWh]",
    value=160.0
)

zuzycie_roczne = st.sidebar.number_input(
    "Zużycie roczne klienta [MWh]",
    value=600.0
)

cena_aktualna_klienta = st.sidebar.number_input(
    "Aktualna cena klienta [zł/MWh]",
    value=700.0
)

st.sidebar.subheader("Profil zużycia")

wysoki_start = st.sidebar.number_input(
    "Godzina zwiększonego poboru – start",
    0, 23, 8
)
wysoki_end = st.sidebar.number_input(
    "Godzina zwiększonego poboru – koniec",
    1, 24, 16
)
waga_wysoka = st.sidebar.number_input(
    "Współczynnik zwiększonego poboru",
    value=2.0,
    step=0.1
)

# ===============================
# DANE TGE (CSV lub DEMO)
# ===============================
st.header("📂 Dane TGE")

def wczytaj_csv(file):
    df = pd.read_csv(file, sep=None, engine="python")
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace("﻿", "", regex=False)
    )

    col_data = next((c for c in df.columns if c in ["data", "date", "datetime"]), None)
    col_price = next((c for c in df.columns if "fixing" in c), None)

    if col_data is None or col_price is None:
        st.error("Nie znaleziono kolumny daty lub ceny.")
        return None

    df = df.rename(columns={col_data: "Data", col_price: "fixing_i_price"})
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce", dayfirst=True)
    df["fixing_i_price"] = (
        df["fixing_i_price"]
        .astype(str)
        .str.replace(",", ".")
        .astype(float)
    )
    df = df.dropna(subset=["Data"])
    return df

uploaded_file = st.file_uploader("Wgraj plik CSV z TGE", type="csv")

if uploaded_file:
    tge_df = wczytaj_csv(uploaded_file)
else:
    dates = pd.date_range("2024-01-01", "2024-12-31 23:00", freq="H")
    tge_df = pd.DataFrame({
        "Data": dates,
        "fixing_i_price": 430 + (dates.hour % 6) * 7 + dates.month
    })
    st.info("Użyto przykładowych danych TGE")

# ===============================
# FILTR ROKU – TYLKO 2025
# ===============================
tge_df = tge_df[tge_df["Data"].dt.year == 2025]

if tge_df.empty:
    st.error("❌ W pliku CSV nie ma danych dla roku 2025.")
    st.stop()


# ===============================
# OBLICZENIA
# ===============================
tge_df["Godzina"] = tge_df["Data"].dt.hour
tge_df["Waga"] = 1.0
tge_df.loc[
    (tge_df["Godzina"] >= wysoki_start) &
    (tge_df["Godzina"] < wysoki_end),
    "Waga"
] = waga_wysoka

# Cena FLIX = TGE + składnik
tge_df["Cena_FLIX"] = tge_df["fixing_i_price"] + skladnik_dodatkowy

# Analiza tylko IV–IX
tge_df = tge_df[tge_df["Data"].dt.month.isin([4, 5, 6, 7, 8, 9])]
tge_df["Miesiąc"] = tge_df["Data"].dt.to_period("M")

monthly = (
    tge_df
    .groupby("Miesiąc")
    .apply(lambda x: (x["Cena_FLIX"] * x["Waga"]).sum() / x["Waga"].sum())
    .reset_index(name="Cena_FLIX_1MWh")
)

monthly["Miesiąc"] = monthly["Miesiąc"].astype(str)
monthly["Zużycie_miesięczne_MWh"] = zuzycie_roczne / 12
monthly["Koszt_FLIX_zł"] = monthly["Cena_FLIX_1MWh"] * monthly["Zużycie_miesięczne_MWh"]
monthly["Koszt_aktualny_zł"] = cena_aktualna_klienta * monthly["Zużycie_miesięczne_MWh"]
monthly["Oszczędność_zł"] = monthly["Koszt_aktualny_zł"] - monthly["Koszt_FLIX_zł"]

# ===============================
# KROK 4 – METRYKI
# ===============================
st.header("📊 Podsumowanie")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Średnia cena FLIX",
        f"{monthly['Cena_FLIX_1MWh'].mean():.0f} zł/MWh"
    )

with col2:
    st.metric(
        "Średni koszt FLIX",
        f"{monthly['Koszt_FLIX_zł'].mean():,.0f} zł"
    )

with col3:
    st.metric(
        "Łączna oszczędność",
        f"{monthly['Oszczędność_zł'].sum():,.0f} zł"
    )

# ===============================
# KROK 5 – TABELA
# ===============================
st.header("📅 Analiza miesięczna – kwiecień–wrzesień")
st.dataframe(monthly, use_container_width=True)

# ===============================
# WYKRESY
# ===============================
st.markdown("---")
st.header("📈 Analiza graficzna")

fig, ax = plt.subplots()
ax.plot(
    monthly["Miesiąc"],
    monthly["Cena_FLIX_1MWh"],
    marker="o",
    label="FLIX",
    color="#3FA7A3"
)
ax.plot(
    monthly["Miesiąc"],
    [cena_aktualna_klienta] * len(monthly),
    linestyle="--",
    label="Aktualna cena",
    color="#1F2D2B"
)
ax.set_ylabel("Cena [zł/MWh]")
ax.legend()
ax.grid(True)
st.pyplot(fig)

fig2, ax2 = plt.subplots()
ax2.plot(
    monthly["Miesiąc"],
    monthly["Koszt_FLIX_zł"],
    marker="o",
    label="Koszt FLIX",
    color="#3FA7A3"
)
ax2.plot(
    monthly["Miesiąc"],
    monthly["Koszt_aktualny_zł"],
    linestyle="--",
    label="Koszt aktualny",
    color="#1F2D2B"
)
ax2.set_ylabel("Koszt [zł]")
ax2.legend()
ax2.grid(True)
st.pyplot(fig2)

st.caption("⚠️ Kalkulacja orientacyjna. Dane historyczne TGE.")

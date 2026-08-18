import streamlit as st
import pandas as pd
import json
import altair as alt
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

# ---------- Page config ----------
st.set_page_config(
    page_title="Spotify History Analyzer",
    page_icon="🎧",
    layout="wide",
)

# ---------- Spotify Gradient Background ----------
st.markdown("""
<style>
body {
    background: linear-gradient(135deg, #000000 0%, #0A1A0A 20%, #1DB954 50%, #3D5AFE 100%);
    background-attachment: fixed;
    color: #FFFFFF;
}

/* Rounded card container */
.card {
    background-color: rgba(0,0,0,0.55);
    padding: 20px;
    border-radius: 16px;
    border: 1px solid #333333;
    margin-bottom: 25px;
}

/* KPI cards */
.metric-card {
    background-color: rgba(0,0,0,0.55);
    padding: 15px;
    border-radius: 12px;
    border: 1px solid #333333;
    margin-bottom: 15px;
}

/* Dataframe styling */
.dataframe tbody tr {
    color: #FFFFFF;
}
.dataframe thead tr {
    color: #FFFFFF;
}
</style>
""", unsafe_allow_html=True)

PRIMARY = "#1DB954"   # Spotify green
SECONDARY = "#3D5AFE" # Indigo
ACCENT_WARM = "#FF6D00"
ACCENT_COOL = "#00B8D4"
TEXT_LIGHT = "#F5F5F5"

def base_chart(chart):
    return (
        chart
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor=TEXT_LIGHT,
            titleColor=TEXT_LIGHT,
            gridColor="#444444"
        )
        .configure_legend(
            labelColor=TEXT_LIGHT,
            titleColor=TEXT_LIGHT
        )
    )

# ---------- Helpers ----------
def flatten_record(x):
    if not isinstance(x, dict):
        return None

    return {
        "timestamp": x.get("ts"),
        "ms_played": x.get("ms_played", 0),
        "track": x.get("master_metadata_track_name"),
        "artist": x.get("master_metadata_album_artist_name"),
        "album": x.get("master_metadata_album_album_name"),
        "genre": x.get("spotify_track_uri", "Unknown"),  # fallback
        "skipped": x.get("skipped", False),
        "shuffle": x.get("shuffle", False),
        "cover_url": x.get("episode_image_url") or x.get("image_url") or None,
    }

def load_files(files):
    rows = []
    bad_files = []

    for uploaded in files:
        try:
            raw = json.load(uploaded)
            if isinstance(raw, dict):
                raw = [raw]

            for item in raw:
                row = flatten_record(item)
                if row and row["track"] is not None:
                    rows.append(row)
        except Exception as e:
            bad_files.append((uploaded.name, str(e)))

    df = pd.DataFrame(rows)

    if df.empty:
        return df, bad_files

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["ms_played"] = pd.to_numeric(df["ms_played"], errors="coerce").fillna(0)
    df["minutes"] = df["ms_played"] / 60000
    df["hours"] = df["minutes"] / 60

    df["date"] = df["timestamp"].dt.date
    df["year"] = df["timestamp"].dt.year
    df["month"] = df["timestamp"].dt.to_period("M").astype(str)
    df["hour"] = df["timestamp"].dt.hour
    df["weekday"] = df["timestamp"].dt.day_name()

    return df, bad_files

def top_table(df, col, n=10):
    return (
        df.groupby(col, dropna=False)
          .agg(plays=("track", "size"), minutes=("minutes", "sum"))
          .sort_values(["minutes", "plays"], ascending=False)
          .head(n)
          .reset_index()
    )

def heatmap(df, value_col, title, colors):
    chart = alt.Chart(df).mark_rect().encode(
        x=alt.X("hour:O", title="Hour"),
        y=alt.Y("weekday:N", title="Day"),
        color=alt.Color(f"{value_col}:Q", scale=alt.Scale(scheme=colors)),
        tooltip=["weekday", "hour", value_col]
    ).properties(height=300, title=title)
    return base_chart(chart)

# ---------- Header ----------
st.title("🎧 Spotify History Analyzer")
st.caption("Drop your Spotify Streaming_History_Audio_*.json files below and explore your listening history.")

# ---------- Upload ----------
st.sidebar.header("Your Spotify files")
files = st.sidebar.file_uploader(
    "Upload Streaming_History_Audio_*.json files",
    type=["json"],
    accept_multiple_files=True,
)

if not files:
    st.info("👈 Upload one or more Spotify audio-history JSON files to begin.")
    st.stop()

df, bad_files = load_files(files)

if bad_files:
    st.warning("Some files could not be read:")
    for name, err in bad_files:
        st.write(f"- {name}: {err}")

if df.empty:
    st.error("No playable track records were found.")
    st.stop()

# ---------- Sidebar filters ----------
st.sidebar.success(f"Loaded {len(df):,} listening events")

years = sorted(df["year"].dropna().unique().tolist())
selected_years = st.sidebar.multiselect("Years", years, default=years)

artists = sorted(df["artist"].dropna().unique().tolist())
artist_filter = st.sidebar.multiselect("Artists (optional)", artists, default=[])

min_minutes = st.sidebar.slider(
    "Minimum minutes counted per play",
    0.0, 5.0, 0.0, 0.25,
)

f = df[df["year"].isin(selected_years)].copy()

if artist_filter:
    f = f[f["artist"].isin(artist_filter)]

f = f[f["minutes"] >= min_minutes]

if f.empty:
    st.warning("No listening events match your filters.")
    st.stop()

# ---------- Overview ----------
st.header("🎵 Your Music DNA")

total_hours = f["minutes"].sum() / 60
unique_songs = f["track"].nunique()
unique_artists = f["artist"].nunique()
unique_albums = f["album"].nunique()
play_count = len(f)

c1, c2, c3, c4, c5 = st.columns(5)
for col, label, value in [
    (c1, "Listening time", f"{total_hours:,.1f} hrs"),
    (c2, "Listening events", f"{play_count:,}"),
    (c3, "Unique songs", f"{unique_songs:,}"),
    (c4, "Unique artists", f"{unique_artists:,}"),
    (c5, "Unique albums", f"{unique_albums:,}")
]:
    with col:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric(label, value)
        st.markdown('</div>', unsafe_allow_html=True)

# ---------- Tabs ----------
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🏆 Top Music",
    "📈 Evolution",
    "⏰ When You Listen",
    "🔁 Replay & Habits",
    "🎧 Deep Cuts",
    "📝 Yearly Wrapped",
    "🎨 Genre Clusters",
])

# ---------- Top Music ----------
with tab1:
    st.subheader("Your most-played music")

    col1, col2 = st.columns(2)

    # Top Artists
    with col1:
        st.markdown("#### Top artists by listening time")
        artists_df = top_table(f, "artist", 15)

        chart = alt.Chart(artists_df).mark_bar(color=PRIMARY).encode(
            x="minutes:Q",
            y=alt.Y("artist:N", sort="-x"),
            tooltip=["artist", "minutes", "plays"]
        ).properties(height=400)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.altair_chart(base_chart(chart), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.dataframe(artists_df, use_container_width=True, hide_index=True)

    # Top Songs + Album Art
    with col2:
        st.markdown("#### Top songs by listening time")
        songs_df = top_table(f, "track", 15)

        # Add album art thumbnails
        songs_df["cover"] = songs_df["track"].map(
            lambda t: f[f["track"] == t]["cover_url"].dropna().iloc[0]
            if any(f[f["track"] == t]["cover_url"].notna())
            else None
        )

        st.markdown('<div class="card">', unsafe_allow_html=True)
        for _, row in songs_df.iterrows():
            st.markdown(
                f"""
                <div style="display:flex;align-items:center;margin-bottom:10px;">
                    <img src="{row['cover']}" style="width:50px;height:50px;border-radius:8px;margin-right:10px;">
                    <span style="font-size:16px;">{row['track']} — {row['minutes']:.1f} min</span>
                </div>
                """,
                unsafe_allow_html=True
            )
        st.markdown('</div>', unsafe_allow_html=True)

        st.dataframe(songs_df, use_container_width=True, hide_index=True)

# ---------- Evolution ----------
with tab2:
    st.subheader("How your taste changed")

    yearly = (
        f.groupby("year")
         .agg(
             hours=("minutes", lambda x: x.sum()/60),
             plays=("track", "size"),
             artists=("artist", "nunique"),
             songs=("track", "nunique"),
             albums=("album", "nunique"),
         )
         .reset_index()
    )

    chart = alt.Chart(yearly).mark_line(color=PRIMARY, point=True).encode(
        x="year:O",
        y="hours:Q",
        tooltip=["year", "hours"]
    ).properties(height=300)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.dataframe(yearly, use_container_width=True, hide_index=True)

# ---------- When ----------
with tab3:
    st.subheader("When do you listen?")

    hourly = f.groupby("hour")["minutes"].sum().reset_index()
    weekday_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    weekday = f.groupby("weekday")["minutes"].sum().reindex(weekday_order).reset_index()

    # Hour chart
    chart = alt.Chart(hourly).mark_bar(color=ACCENT_COOL).encode(
        x="hour:O",
        y="minutes:Q",
        tooltip=["hour","minutes"]
    ).properties(height=300)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Day chart
    chart = alt.Chart(weekday).mark_bar(color=ACCENT_WARM).encode(
        x=alt.X("weekday:N", sort=weekday_order),
        y="minutes:Q",
        tooltip=["weekday","minutes"]
    ).properties(height=300)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Heatmaps
    heat_df = f.groupby(["weekday","hour"])["minutes"].sum().reset_index()
    session_df = f.groupby(["weekday","hour"])["track"].count().reset_index().rename(columns={"track":"plays"})

    st.markdown("#### Listening intensity heatmap")
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(heatmap(heat_df, "minutes", "Listening Intensity", "greens"), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("#### Session stamina heatmap")
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(heatmap(session_df, "plays", "Session Stamina", "oranges"), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- Replay / habits ----------
with tab4:
    st.subheader("🔁 Replay & listening personality")

    song_stats = (
        f.groupby(["track","artist"])
         .agg(
             plays=("track","size"),
             minutes=("minutes","sum"),
             avg_minutes=("minutes","mean"),
             skips=("skipped","sum"),
         )
         .reset_index()
    )
    song_stats["skip_rate"] = song_stats["skips"] / song_stats["plays"]

    c1, c2, c3 = st.columns(3)
    for col, label, value in [
        (c1, "Avg. play length", f"{f['minutes'].mean():.2f} min"),
        (c2, "Skip rate", f"{100*f['skipped'].mean():.1f}%"),
        (c3, "Shuffle rate", f"{100*f['shuffle'].mean():.1f}%"),
    ]:
        with col:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric(label, value)
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("#### Your most replayed songs")
    replay = song_stats.sort_values(["plays","minutes"], ascending=False).head(25)
    st.dataframe(replay, use_container_width=True, hide_index=True)

# ---------- Deep cuts ----------
with tab5:
    st.subheader("🎧 Deep cuts & hidden patterns")

    artist_stats = (
        f.groupby("artist")
         .agg(
             minutes=("minutes","sum"),
             plays=("track","size"),
             unique_songs=("track","nunique"),
         )
         .reset_index()
    )
    artist_stats["minutes_per_song"] = artist_stats["minutes"] / artist_stats["unique_songs"]

    st.markdown("#### Artists you go deep on")
    deep = artist_stats[artist_stats["plays"] >= 5].sort_values("minutes_per_song", ascending=False).head(25)
    st.dataframe(deep, use_container_width=True, hide_index=True)

# ---------- Wrapped ----------
with tab6:
    st.subheader("📝 Your yearly Spotify Wrapped")

    for year in sorted(f["year"].dropna().unique(), reverse=True):
        y = f[f["year"] == year]
        if y.empty:
            continue

        top_artist = y.groupby("artist")["minutes"].sum().idxmax()
        top_song = y.groupby("track")["minutes"].sum().idxmax()
        top_album = y.groupby("album")["minutes"].sum().idxmax()

        with st.expander(f"🎧 {int(year)}"):
            a, b, c, d = st.columns(4)
            for col, label, value in [
                (a, "Hours", f"{y['minutes'].sum()/60:,.1f}"),
                (b, "Top artist", top_artist),
                (c, "Top song", top_song),
                (d, "Top album", top_album),
            ]:
                with col:
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.metric(label, value)
                    st.markdown('</div>', unsafe_allow_html=True)

# ---------- Genre Clustering ----------
with tab7:
    st.subheader("🎨 Genre Clustering")

    # Fallback genre text
    f["genre_text"] = f["genre"].fillna("Unknown")

    vectorizer = TfidfVectorizer(stop_words="english")
    X = vectorizer.fit_transform(f["genre_text"])

    kmeans = KMeans(n_clusters=5, random_state=42)
    f["cluster"] = kmeans.fit_predict(X)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.write("Your listening grouped into 5 genre clusters:")
    st.dataframe(f[["artist","track","genre_text","cluster"]], use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- Download ----------
st.divider()
st.subheader("📥 Export your analysis")

summary = (
    f.groupby(["artist","track","album"])
     .agg(
         plays=("track","size"),
         minutes=("minutes","sum"),
     )
     .reset_index()
     .sort_values("minutes", ascending=False)
)

csv = summary.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download song-level summary CSV",
    data=csv,
    file_name="spotify_analysis_summary.csv",
    mime="text/csv"
)

st.caption("Privacy note: this app intentionally ignores the ip_addr field.")

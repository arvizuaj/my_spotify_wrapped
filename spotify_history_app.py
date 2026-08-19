#Chunk1

import streamlit as st
import pandas as pd
import json
import altair as alt
import numpy as np

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

.card {
    background-color: rgba(0,0,0,0.55);
    padding: 20px;
    border-radius: 16px;
    border: 1px solid #333333;
    margin-bottom: 25px;
}

.metric-card {
    background-color: rgba(0,0,0,0.55);
    padding: 15px;
    border-radius: 12px;
    border: 1px solid #333333;
    margin-bottom: 15px;
}

.dataframe tbody tr {
    color: #FFFFFF;
}
.dataframe thead tr {
    color: #FFFFFF;
}
</style>
""", unsafe_allow_html=True)

PRIMARY = "#1DB954"
SECONDARY = "#3D5AFE"
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
        "skipped": x.get("skipped", False),
        "shuffle": x.get("shuffle", False),
        "reason_start": x.get("reason_start"),
        "reason_end": x.get("reason_end"),
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
    t = (
        df.groupby(col, dropna=False)
          .agg(plays=("track", "size"), minutes=("minutes", "sum"))
          .sort_values(["minutes", "plays"], ascending=False)
          .head(n)
          .reset_index()
    )
    t["minutes"] = t["minutes"].astype(int)
    return t

def heatmap(df, value_col, title, colors):
    chart = alt.Chart(df).mark_rect().encode(
        x=alt.X("hour:O", title="Hour"),
        y=alt.Y("weekday:N", title="Day"),
        color=alt.Color(f"{value_col}:Q", scale=alt.Scale(scheme=colors)),
        tooltip=["weekday", "hour", value_col]
    ).properties(height=300, title=title)
    return base_chart(chart)

def classify_deliberate_served(row):
    rs = str(row.get("reason_start") or "").lower()
    re = str(row.get("reason_end") or "").lower()

    deliberate_codes = {"fwdbtn", "clickrow", "playbtn", "search", "trackradio"}
    served_codes = {"trackdone", "endplay", "autoplay", "remote"}

    if rs in deliberate_codes:
        return "Deliberate"
    if rs in served_codes or re in served_codes or re in {"trackdone", "endplay"}:
        return "Served"

    if row["minutes"] < 0.5:
        return "Deliberate"
    return "Served"

#Chunk2

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
tab1, tab3, tab4, tab6, tab7, tab9, tab10 = st.tabs([
    "🏆 Top Music",
    "⏰ When You Listen",
    "🔁 Replay & Habits",
    "📝 Yearly Wrapped",
    "🏃 Listening Marathons",
    "🏆 Artist & Track Races",
    "❤️ Loyalty & Behavior",
])

#Chunk3

# ---------- Top Music ----------
with tab1:
    st.subheader("Your most-played music")

    col1, col2 = st.columns(2)

    # -----------------------------
    # Top Artists
    # -----------------------------
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

    # -----------------------------
    # Top Songs
    # -----------------------------
    with col2:
        st.markdown("#### Top songs by listening time")
        songs_df = top_table(f, "track", 15)

        chart = alt.Chart(songs_df).mark_bar(color=SECONDARY).encode(
            x="minutes:Q",
            y=alt.Y("track:N", sort="-x"),
            tooltip=["track", "minutes", "plays"]
        ).properties(height=400)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.altair_chart(base_chart(chart), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.dataframe(songs_df, use_container_width=True, hide_index=True)

    # -----------------------------
    # All-Time Artist Race (Top 20)
    # -----------------------------
    st.markdown("### 🏆 All-Time Artist Race (Top 20)")

    artist_daily = (
        f.groupby(["date","artist"])["minutes"]
        .sum()
        .reset_index()
    )
    artist_daily = artist_daily.sort_values(["artist","date"])
    artist_daily["cum_hours"] = artist_daily.groupby("artist")["minutes"].cumsum() / 60

    top20_artists = (
        artist_daily.groupby("artist")["cum_hours"]
        .max()
        .sort_values(ascending=False)
        .head(20)
        .index
    )
    artist_daily_top = artist_daily[artist_daily["artist"].isin(top20_artists)]

    chart = alt.Chart(artist_daily_top).mark_line().encode(
        x="date:T",
        y="cum_hours:Q",
        color="artist:N",
        tooltip=["date","artist","cum_hours"]
    ).properties(height=350)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------------
    # All-Time Track Race (Top 20)
    # -----------------------------
    st.markdown("### 🏆 All-Time Track Race (Top 20)")

    track_daily = (
        f.groupby(["date","track"])["minutes"]
        .sum()
        .reset_index()
    )
    track_daily = track_daily.sort_values(["track","date"])
    track_daily["cum_hours"] = track_daily.groupby("track")["minutes"].cumsum() / 60

    top20_tracks = (
        track_daily.groupby("track")["cum_hours"]
        .max()
        .sort_values(ascending=False)
        .head(20)
        .index
    )
    track_daily_top = track_daily[track_daily["track"].isin(top20_tracks)]

    chart = alt.Chart(track_daily_top).mark_line().encode(
        x="date:T",
        y="cum_hours:Q",
        color="track:N",
        tooltip=["date","track","cum_hours"]
    ).properties(height=350)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

#Chunk4

# ---------- When You Listen ----------
with tab3:
    st.subheader("⏰ When do you listen?")

    # -----------------------------
    # Hour of Day Listening
    # -----------------------------
    hourly = f.groupby("hour")["minutes"].sum().reset_index()

    chart = alt.Chart(hourly).mark_bar(color=ACCENT_COOL).encode(
        x="hour:O",
        y="minutes:Q",
        tooltip=["hour","minutes"]
    ).properties(height=300)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------------
    # Day of Week Listening
    # -----------------------------
    weekday_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    weekday = f.groupby("weekday")["minutes"].sum().reindex(weekday_order).reset_index()

    chart = alt.Chart(weekday).mark_bar(color=ACCENT_WARM).encode(
        x=alt.X("weekday:N", sort=weekday_order),
        y="minutes:Q",
        tooltip=["weekday","minutes"]
    ).properties(height=300)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------------
    # Evolution Area Chart (Moved Here)
    # -----------------------------
    st.markdown("### 📈 Listening Time by Year")

    yearly = (
        f.groupby("year")
         .agg(hours=("minutes", lambda x: x.sum()/60))
         .reset_index()
    )

    chart = alt.Chart(yearly).mark_area(
        opacity=0.35,
        color="#1DB954"
    ).encode(
        x="year:O",
        y="hours:Q",
        tooltip=["year","hours"]
    ).properties(height=300)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------------
    # Listening Intensity Heatmap
    # -----------------------------
    heat_df = f.groupby(["weekday","hour"])["minutes"].sum().reset_index()

    st.markdown("#### Listening intensity heatmap")
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(
        heatmap(heat_df, "minutes", "Listening Intensity", "greens"),
        use_container_width=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------------
    # Session Stamina Heatmap
    # -----------------------------
    session_df = (
        f.groupby(["weekday","hour"])["track"]
        .count()
        .reset_index()
        .rename(columns={"track":"plays"})
    )

    st.markdown("#### Session stamina heatmap")
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(
        heatmap(session_df, "plays", "Session Stamina", "oranges"),
        use_container_width=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

#Chunk5

# ---------- Replay & Habits ----------
with tab4:
    st.subheader("🔁 Replay & listening personality")

    # -----------------------------
    # Song-level replay stats
    # -----------------------------
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

    # Replay KPIs
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

    # -----------------------------
    # Replay Table
    # -----------------------------
    st.markdown("#### Your most replayed songs")

    replay = song_stats.sort_values(["plays","minutes"], ascending=False).head(25)

    st.dataframe(replay, use_container_width=True, hide_index=True)

    # -----------------------------
    # Deep Cuts (moved from old tab)
    # -----------------------------
    st.markdown("### 🎧 Deep Cuts — Artists You Go Deep On")

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

    # Sort by unique songs descending
    deep = artist_stats.sort_values("unique_songs", ascending=False).head(25)

    # Deep Cuts Visual
    chart = alt.Chart(deep).mark_bar(color="#1DB954").encode(
        x="unique_songs:Q",
        y=alt.Y("artist:N", sort="-x"),
        tooltip=["artist","unique_songs","minutes"]
    ).properties(height=350)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Deep Cuts Table
    st.dataframe(deep, use_container_width=True, hide_index=True)

#Chunk6a

# ---------- Yearly Wrapped ----------
with tab6:
    st.subheader("📝 Your yearly Spotify Wrapped")

    # Loop through each year in descending order
    for year in sorted(f["year"].dropna().unique(), reverse=True):
        y = f[f["year"] == year]
        if y.empty:
            continue

        # Top artist, song, album for the year
        top_artist = y.groupby("artist")["minutes"].sum().idxmax()
        top_song = y.groupby("track")["minutes"].sum().idxmax()
        top_album = y.groupby("album")["minutes"].sum().idxmax()

        # Build visuals (will be added in CHUNK 6B)
        # top_artists_year
        # top_songs_year
        # daily_year

        with st.expander(f"🎧 {int(year)}"):
            # Metrics row
            a, b, c, d = st.columns(4)

            with a:
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("Hours", f"{y['minutes'].sum()/60:,.1f}")
                st.markdown('</div>', unsafe_allow_html=True)

            with b:
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("Top artist", top_artist)
                st.markdown('</div>', unsafe_allow_html=True)

            with c:
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("Top song", top_song)
                st.markdown('</div>', unsafe_allow_html=True)

            with d:
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("Top album", top_album)
                st.markdown('</div>', unsafe_allow_html=True)

            # Visuals will be inserted in CHUNK 6B
            v1, v2, v3 = st.columns(3)

#Chunk6B

        # -----------------------------
        # Build visuals for this year
        # -----------------------------

        # Top Artists (Year)
        top_artists_year = (
            y.groupby("artist")["minutes"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )

        artist_chart = alt.Chart(top_artists_year).mark_bar(color=PRIMARY).encode(
            x="minutes:Q",
            y=alt.Y("artist:N", sort="-x"),
            tooltip=["artist", "minutes"]
        ).properties(height=250)

        # Top Songs (Year)
        top_songs_year = (
            y.groupby("track")["minutes"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )

        song_chart = alt.Chart(top_songs_year).mark_bar(color=SECONDARY).encode(
            x="minutes:Q",
            y=alt.Y("track:N", sort="-x"),
            tooltip=["track", "minutes"]
        ).properties(height=250)

        # Daily Listening Trend (Year)
        daily_year = (
            y.groupby("date")["minutes"]
            .sum()
            .reset_index()
        )

        trend_chart = alt.Chart(daily_year).mark_line(color=ACCENT_COOL).encode(
            x="date:T",
            y="minutes:Q",
            tooltip=["date", "minutes"]
        ).properties(height=250)

        # -----------------------------
        # Insert visuals into expander
        # -----------------------------
        with v1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### Top Artists")
            st.altair_chart(base_chart(artist_chart), use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with v2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### Top Songs")
            st.altair_chart(base_chart(song_chart), use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with v3:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### Daily Listening Trend")
            st.altair_chart(base_chart(trend_chart), use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

#Chunk6C
        # End of expander for this year
        # (No additional visuals needed here)

    # End of Yearly Wrapped tab

#Chunk7
# ---------- Listening Marathons ----------
with tab7:
    st.subheader("🏃 Listening Marathons")

    # Sort by timestamp
    f_sorted = f.sort_values("timestamp")

    # Gap between plays
    f_sorted["gap"] = f_sorted["timestamp"].diff().dt.total_seconds().fillna(0)

    # New session if gap > 30 minutes
    f_sorted["new_session"] = f_sorted["gap"] > (30 * 60)
    f_sorted["session_id"] = f_sorted["new_session"].cumsum()

    # Build sessions
    sessions = (
        f_sorted.groupby("session_id")
        .agg(
            start=("timestamp","min"),
            end=("timestamp","max"),
            duration_minutes=("minutes","sum"),
            tracks=("track","size"),
            skips=("skipped","sum"),
        )
        .reset_index()
    )

    # Convert duration to hours
    sessions["duration_hours"] = sessions["duration_minutes"] / 60

    # Top artist per session
    top_artist_per_session = (
        f_sorted.groupby(["session_id","artist"])["track"]
        .count()
        .reset_index()
        .sort_values(["session_id","track"], ascending=[True,False])
        .groupby("session_id")
        .first()
        .reset_index()
        .rename(columns={"artist":"top_artist","track":"artist_plays"})
    )

    # Top track per session
    top_track_per_session = (
        f_sorted.groupby(["session_id","track"])["track"]
        .count()
        .reset_index(name="plays")
        .sort_values(["session_id","plays"], ascending=[True,False])
        .groupby("session_id")
        .first()
        .reset_index()
        .rename(columns={"track":"top_track","plays":"track_plays"})
    )

    # Merge into sessions table
    sessions = sessions.merge(top_artist_per_session, on="session_id", how="left")
    sessions = sessions.merge(top_track_per_session, on="session_id", how="left")

    # Mood classification
    sessions["mood"] = np.where(
        sessions["skips"] / sessions["tracks"] < 0.1,
        "In the Zone",
        "Chaotic"
    )

    # -----------------------------
    # Marathon Duration Visual
    # -----------------------------
    st.markdown("### ⏱️ Your Longest Listening Marathons")

    duration_chart = alt.Chart(
        sessions.sort_values("duration_hours", ascending=False).head(20)
    ).mark_bar(color=PRIMARY).encode(
        x="duration_hours:Q",
        y=alt.Y("session_id:N", sort="-x"),
        tooltip=["session_id","duration_hours","tracks","top_artist","top_track"]
    ).properties(height=350)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(duration_chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------------
    # Marathon Table (Enhanced)
    # -----------------------------
    st.markdown("### 📋 Marathon Details")

    marathon_table = sessions.sort_values("duration_hours", ascending=False).head(20)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.dataframe(
        marathon_table[
            [
                "session_id",
                "start",
                "end",
                "duration_hours",
                "tracks",
                "skips",
                "mood",
                "top_artist",
                "top_track",
            ]
        ],
        use_container_width=True,
        hide_index=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

#Chunk8
# ---------- Artist & Track Races ----------
with tab9:
    st.subheader("🏆 Artist & Track Races")

    # Artist Race (Cumulative Hours)
    artist_daily = (
        f.groupby(["date","artist"])["minutes"]
        .sum()
        .reset_index()
    )
    artist_daily = artist_daily.sort_values(["artist","date"])
    artist_daily["cum_hours"] = artist_daily.groupby("artist")["minutes"].cumsum() / 60

    top_artists = (
        artist_daily.groupby("artist")["cum_hours"]
        .max()
        .sort_values(ascending=False)
        .head(25)
        .index
    )
    artist_daily_top = artist_daily[artist_daily["artist"].isin(top_artists)]

    chart = alt.Chart(artist_daily_top).mark_line().encode(
        x="date:T",
        y="cum_hours:Q",
        color="artist:N",
        tooltip=["date","artist","cum_hours"]
    ).properties(height=350)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🎨 Artist Race — Top 25")
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Track Race (Cumulative Hours)
    track_daily = (
        f.groupby(["date","track"])["minutes"]
        .sum()
        .reset_index()
    )
    track_daily = track_daily.sort_values(["track","date"])
    track_daily["cum_hours"] = track_daily.groupby("track")["minutes"].cumsum() / 60

    top_tracks = (
        track_daily.groupby("track")["cum_hours"]
        .max()
        .sort_values(ascending=False)
        .head(25)
        .index
    )
    track_daily_top = track_daily[track_daily["track"].isin(top_tracks)]

    chart = alt.Chart(track_daily_top).mark_line().encode(
        x="date:T",
        y="cum_hours:Q",
        color="track:N",
        tooltip=["date","track","cum_hours"]
    ).properties(height=350)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🎶 Track Race — Top 25")
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ---------- Loyalty & Behavior ----------
with tab10:
    st.subheader("❤️ Loyalty & Behavior")

    # Ride-or-Die Artists (high minutes per unique song)
    artist_stats = (
        f.groupby("artist")
         .agg(
             minutes=("minutes","sum"),
             unique_songs=("track","nunique"),
             plays=("track","size"),
         )
         .reset_index()
    )
    artist_stats["minutes_per_song"] = artist_stats["minutes"] / artist_stats["unique_songs"]

    ride_or_die = artist_stats.sort_values("minutes_per_song", ascending=False).head(20)

    chart = alt.Chart(ride_or_die).mark_bar(color=PRIMARY).encode(
        x="minutes_per_song:Q",
        y=alt.Y("artist:N", sort="-x"),
        tooltip=["artist","minutes_per_song","unique_songs","minutes"]
    ).properties(height=350)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🔥 Ride-or-Die Artists")
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.dataframe(ride_or_die, use_container_width=True, hide_index=True)

    # Skip-heavy songs
    skip_stats = (
        f.groupby("track")
         .agg(
             plays=("track","size"),
             skips=("skipped","sum"),
             minutes=("minutes","sum"),
         )
         .reset_index()
    )
    skip_stats["skip_rate"] = skip_stats["skips"] / skip_stats["plays"]
    skip_heavy = skip_stats[skip_stats["plays"] >= 5].sort_values("skip_rate", ascending=False).head(20)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🚫 Songs You Always Skip")
    st.dataframe(skip_heavy, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Deliberate vs Served
    f["intent"] = f.apply(classify_deliberate_served, axis=1)
    intent_counts = f["intent"].value_counts().reset_index()
    intent_counts.columns = ["intent","count"]

    chart = alt.Chart(intent_counts).mark_bar().encode(
        x="intent:N",
        y="count:Q",
        color="intent:N",
        tooltip=["intent","count"]
    ).properties(height=300)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🎯 Deliberate vs Served Listening")
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Album vs Track Listener
    album_stats = (
        f.groupby("album")["track"]
        .nunique()
        .reset_index()
        .rename(columns={"track":"unique_tracks"})
    )

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 💿 Album vs Track Listener")
    st.dataframe(album_stats.sort_values("unique_tracks", ascending=False).head(20),
                 use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ---------- Download Section ----------
st.header("📥 Export Your Data")

song_summary = (
    f.groupby(["track","artist"])
     .agg(
         plays=("track","size"),
         minutes=("minutes","sum"),
         avg_minutes=("minutes","mean"),
         skips=("skipped","sum"),
     )
     .reset_index()
)

csv = song_summary.to_csv(index=False).encode("utf-8")

st.download_button(
    label="Download Song Summary CSV",
    data=csv,
    file_name="spotify_song_summary.csv",
    mime="text/csv",
)

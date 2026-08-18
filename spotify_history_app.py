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

def classify_deliberate_served(row):
    rs = str(row.get("reason_start") or "").lower()
    re = str(row.get("reason_end") or "").lower()

    deliberate_codes = {"fwdbtn", "clickrow", "playbtn", "search", "trackradio"}
    served_codes = {"trackdone", "endplay", "autoplay", "remote"}

    if rs in deliberate_codes:
        return "Deliberate"
    if rs in served_codes or re in served_codes or re in {"trackdone", "endplay"}:
        return "Served"

    # Fallback heuristic for legacy/missing reasons
    if row["minutes"] < 0.5:
        return "Deliberate"
    return "Served"

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
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
    "🏆 Top Music",
    "📈 Evolution",
    "⏰ When You Listen",
    "🔁 Replay & Habits",
    "🎧 Deep Cuts",
    "📝 Yearly Wrapped",
    "🏃 Listening Marathons",
    "🔍 Discovery vs Repetition",
    "🏆 Artist & Track Races",
    "❤️ Loyalty & Behavior",
])

# ---------- Top Music ----------
with tab1:
    st.subheader("Your most-played music")

    col1, col2 = st.columns(2)

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

# ---------- Evolution ----------
with tab2:
    st.subheader("How your taste changed")

    yearly = (
        f.groupby("year")
         .agg(hours=("minutes", lambda x: x.sum()/60))
         .reset_index()
    )

    chart = alt.Chart(yearly).mark_area(
        color=alt.Gradient(
            gradient="linear",
            stops=[
                alt.GradientStop(color="#1DB954", offset=0),
                alt.GradientStop(color="#1DB954AA", offset=1)
            ],
            x1=1, x2=1, y1=1, y2=0
        )
    ).encode(
        x="year:O",
        y="hours:Q",
        tooltip=["year", "hours"]
    ).properties(height=300)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- When ----------
with tab3:
    st.subheader("When do you listen?")

    hourly = f.groupby("hour")["minutes"].sum().reset_index()
    weekday_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    weekday = f.groupby("weekday")["minutes"].sum().reindex(weekday_order).reset_index()

    chart = alt.Chart(hourly).mark_bar(color=ACCENT_COOL).encode(
        x="hour:O",
        y="minutes:Q",
        tooltip=["hour","minutes"]
    ).properties(height=300)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    chart = alt.Chart(weekday).mark_bar(color=ACCENT_WARM).encode(
        x=alt.X("weekday:N", sort=weekday_order),
        y="minutes:Q",
        tooltip=["weekday","minutes"]
    ).properties(height=300)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

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

# ---------- Listening Marathons ----------
with tab7:
    st.subheader("🏃 Listening Marathons")

    f_sorted = f.sort_values("timestamp")
    f_sorted["gap"] = f_sorted["timestamp"].diff().dt.total_seconds().fillna(0)
    f_sorted["new_session"] = f_sorted["gap"] > (30 * 60)
    f_sorted["session_id"] = f_sorted["new_session"].cumsum()

    sessions = (
        f_sorted.groupby("session_id")
        .agg(
            start=("timestamp","min"),
            end=("timestamp","max"),
            duration=("minutes","sum"),
            tracks=("track","size"),
            skips=("skipped","sum"),
        )
        .reset_index()
    )

    sessions["mood"] = np.where(sessions["skips"] / sessions["tracks"] < 0.1, "In the Zone", "Chaotic")

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.dataframe(
        sessions.sort_values("duration", ascending=False).head(20),
        use_container_width=True,
        hide_index=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- Discovery vs Repetition ----------
with tab8:
    st.subheader("🔍 Discovery vs Repetition")

    f["is_new"] = ~f.duplicated("track")

    daily = (
        f.groupby("date")
        .agg(
            new=("is_new","sum"),
            total=("track","size")
        )
        .reset_index()
    )
    daily["repeated"] = daily["total"] - daily["new"]

    new_area = alt.Chart(daily).mark_area(opacity=0.7, color="#1DB954").encode(
        x="date:T",
        y="new:Q",
        tooltip=["date","new"]
    )
    rep_area = alt.Chart(daily).mark_area(opacity=0.5, color="#3D5AFE").encode(
        x="date:T",
        y="repeated:Q",
        tooltip=["date","repeated"]
    )

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(new_area + rep_area), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- Artist & Track Races ----------
with tab9:
    st.subheader("🏆 Artist & Track Races")

    # Artist cumulative hours
    artist_daily = (
        f.groupby(["date","artist"])["minutes"]
        .sum()
        .reset_index()
    )
    artist_daily = artist_daily.sort_values(["artist","date"])
    artist_daily["cum_hours"] = artist_daily.groupby("artist")["minutes"].cumsum() / 60

    artist_chart = alt.Chart(artist_daily).mark_line().encode(
        x="date:T",
        y="cum_hours:Q",
        color="artist:N",
        tooltip=["date","artist","cum_hours"]
    ).properties(height=350, title="All-Time Artist Race")

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(artist_chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Track cumulative hours
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
        .head(10)
        .index
    )
    track_daily_top = track_daily[track_daily["track"].isin(top_tracks)]

    track_chart = alt.Chart(track_daily_top).mark_line().encode(
        x="date:T",
        y="cum_hours:Q",
        color="track:N",
        tooltip=["date","track","cum_hours"]
    ).properties(height=350, title="All-Time Track Race")

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(track_chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- Loyalty & Behavior ----------
with tab10:
    st.subheader("❤️ Loyalty & Behavior")

    # Artist loyalty (ride-or-die vs always skip)
    artist_loyalty = (
        f.groupby("artist")
        .agg(
            plays=("track","size"),
            skips=("skipped","sum"),
        )
        .reset_index()
    )
    artist_loyalty["skip_rate"] = artist_loyalty["skips"] / artist_loyalty["plays"]
    artist_loyalty["complete_rate"] = 1 - artist_loyalty["skip_rate"]

    ride_or_die = artist_loyalty[artist_loyalty["plays"] >= 10].sort_values(
        "complete_rate", ascending=False
    ).head(10)
    always_skip = artist_loyalty[artist_loyalty["plays"] >= 10].sort_values(
        "skip_rate", ascending=False
    ).head(10)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Ride-or-Die Artists")
        chart = alt.Chart(ride_or_die).mark_bar(color="#1DB954").encode(
            x=alt.X("complete_rate:Q", title="Completion rate"),
            y=alt.Y("artist:N", sort="-x"),
            tooltip=["artist","plays","complete_rate"]
        ).properties(height=300)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.altair_chart(base_chart(chart), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown("#### Artists You Always Skip")
        chart = alt.Chart(always_skip).mark_bar(color="#FF6D00").encode(
            x=alt.X("skip_rate:Q", title="Skip rate"),
            y=alt.Y("artist:N", sort="-x"),
            tooltip=["artist","plays","skip_rate"]
        ).properties(height=300)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.altair_chart(base_chart(chart), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Deliberate vs Served Plays (simplified + reason_start/end)
    f["play_type"] = f.apply(classify_deliberate_served, axis=1)

    deliberate_served = (
        f.groupby(["artist","play_type"])["track"]
        .size()
        .reset_index(name="plays")
    )

    top_artists_ds = (
        deliberate_served.groupby("artist")["plays"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .index
    )
    deliberate_served_top = deliberate_served[deliberate_served["artist"].isin(top_artists_ds)]

    chart = alt.Chart(deliberate_served_top).mark_bar().encode(
        x=alt.X("plays:Q", title="Plays"),
        y=alt.Y("artist:N", sort="-x"),
        color=alt.Color("play_type:N", scale=alt.Scale(domain=["Deliberate","Served"], range=["#1DB954","#FF6D00"])),
        tooltip=["artist","play_type","plays"]
    ).properties(height=350, title="Deliberate vs Served Plays")

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Album vs Track Listener
    album_stats = (
        f.groupby(["artist","album"])
        .agg(
            tracks=("track","nunique"),
            minutes=("minutes","sum"),
        )
        .reset_index()
    )
    album_stats["tracks_per_album"] = album_stats["tracks"]

    full_album = (
        album_stats.groupby("artist")["tracks_per_album"]
        .mean()
        .reset_index()
        .sort_values("tracks_per_album", ascending=False)
        .head(10)
    )

    chart = alt.Chart(full_album).mark_bar(color="#1DB954").encode(
        x=alt.X("tracks_per_album:Q", title="Avg tracks per album"),
        y=alt.Y("artist:N", sort="-x"),
        tooltip=["artist","tracks_per_album"]
    ).properties(height=300, title="Album vs Track Listener (Full Album Artists)")

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(chart), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Discovery Age Map (first play per artist)
    first_artist = (
        f.sort_values("timestamp")
        .groupby("artist")["timestamp"]
        .min()
        .reset_index()
    )
    first_artist["year_discovered"] = first_artist["timestamp"].dt.year

    discovery_counts = (
        first_artist.groupby("year_discovered")["artist"]
        .size()
        .reset_index(name="artists")
        .sort_values("year_discovered")
    )

    chart = alt.Chart(discovery_counts).mark_bar(color="#3D5AFE").encode(
        x=alt.X("year_discovered:O", title="Year"),
        y=alt.Y("artists:Q", title="Artists discovered"),
        tooltip=["year_discovered","artists"]
    ).properties(height=300, title="Discovery Age Map")

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.altair_chart(base_chart(chart), use_container_width=True)
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

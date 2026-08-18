import streamlit as st
import pandas as pd
import json
import altair as alt
from io import BytesIO

# ---------- Page config ----------
st.set_page_config(
    page_title="Spotify History Analyzer",
    page_icon="🎧",
    layout="wide",
)

# ---------- Theme / helpers ----------
PRIMARY = "#1DB954"   # Spotify green
SECONDARY = "#3D5AFE" # Indigo
ACCENT_WARM = "#FF6D00"
ACCENT_COOL = "#00B8D4"
BG_LIGHT = "#ECEFF1"
TEXT_DARK = "#263238"

alt.themes.enable("default")

def base_chart():
    return alt.Chart().configure_view(
        strokeWidth=0
    ).configure_axis(
        labelColor=TEXT_DARK,
        titleColor=TEXT_DARK,
        gridColor="#CFD8DC"
    ).configure_legend(
        labelColor=TEXT_DARK,
        titleColor=TEXT_DARK
    )

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
        "reason_start": x.get("reason_start"),
        "reason_end": x.get("reason_end"),
        "shuffle": x.get("shuffle", False),
        # Deliberately do NOT read ip_addr.
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

    df["timestamp_utc"] = df["timestamp"]
    df["date"] = df["timestamp"].dt.date
    df["year"] = df["timestamp"].dt.year
    df["month"] = df["timestamp"].dt.to_period("M").astype(str)
    df["hour"] = df["timestamp"].dt.hour
    df["weekday"] = df["timestamp"].dt.day_name()
    df["weekday_num"] = df["timestamp"].dt.dayofweek

    return df, bad_files

def top_table(df, col, n=10):
    return (
        df.groupby(col, dropna=False)
          .agg(plays=("track", "size"), minutes=("minutes", "sum"))
          .sort_values(["minutes", "plays"], ascending=False)
          .head(n)
          .reset_index()
    )

# ---------- Header ----------
st.title("🎧 Spotify History Analyzer")
st.caption("Drop your Spotify Streaming_History_Audio_*.json files below and explore your listening history.")

# ---------- Upload ----------
st.sidebar.header("Your Spotify files")
files = st.sidebar.file_uploader(
    "Upload Streaming_History_Audio_*.json files",
    type=["json"],
    accept_multiple_files=True,
    help="You can upload multiple years/files at once."
)

if not files:
    st.info("👈 Upload one or more Spotify audio-history JSON files to begin.")
    st.markdown("""
### What you'll get

- 🎵 Music DNA — top songs, artists, albums and total listening
- 📈 Taste evolution across years
- 🧠 Listening personality
- ⏰ When you listen
- 🔁 Replay & obsession analysis
- 🎧 Deep-cut discoveries
- 🏆 Your own Spotify Wrapped
- 📊 Interactive charts and filters
- 📥 Downloadable summary tables
""")
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
artist_filter = st.sidebar.multiselect(
    "Artists (optional)",
    artists,
    default=[],
)

min_minutes = st.sidebar.slider(
    "Minimum minutes counted per play",
    0.0, 5.0, 0.0, 0.25,
    help="Useful for excluding accidental taps or near-instant skips."
)

f = df[df["year"].isin(selected_years)].copy()

if artist_filter:
    f = f[f["artist"].isin(artist_filter)]

f = f[f["minutes"] >= min_minutes]

if f.empty:
    st.warning("No listening events match your filters.")
    st.stop()

# ---------- Overview / hero metrics ----------
st.header("🎵 Your Music DNA")

total_hours = f["minutes"].sum() / 60
unique_songs = f["track"].nunique()
unique_artists = f["artist"].nunique()
unique_albums = f["album"].nunique()
play_count = len(f)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Listening time", f"{total_hours:,.1f} hrs")
c2.metric("Listening events", f"{play_count:,}")
c3.metric("Unique songs", f"{unique_songs:,}")
c4.metric("Unique artists", f"{unique_artists:,}")
c5.metric("Unique albums", f"{unique_albums:,}")

# ---------- Tabs ----------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏆 Top Music",
    "📈 Evolution",
    "⏰ When You Listen",
    "🔁 Replay & Habits",
    "🎧 Deep Cuts",
    "📝 Yearly Wrapped",
])

# ---------- Top Music ----------
with tab1:
    st.subheader("Your most-played music")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Top artists by listening time")
        artists_df = top_table(f, "artist", 15)

        chart = (
            base_chart()
            .mark_bar(color=PRIMARY)
            .encode(
                x=alt.X("minutes:Q", title="Minutes listened"),
                y=alt.Y("artist:N", sort="-x", title=None),
                tooltip=["artist", "minutes", "plays"]
            )
            .properties(height=400)
            .interactive()
        ).transform_data(data=artists_df)

        st.altair_chart(chart, use_container_width=True)
        st.dataframe(artists_df, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("#### Top songs by listening time")
        songs_df = top_table(f, "track", 15)

        chart = (
            base_chart()
            .mark_bar(color=SECONDARY)
            .encode(
                x=alt.X("minutes:Q", title="Minutes listened"),
                y=alt.Y("track:N", sort="-x", title=None),
                tooltip=["track", "minutes", "plays"]
            )
            .properties(height=400)
            .interactive()
        ).transform_data(data=songs_df)

        st.altair_chart(chart, use_container_width=True)
        st.dataframe(songs_df, use_container_width=True, hide_index=True)

    st.markdown("#### Top albums")
    albums_df = top_table(f, "album", 15)
    st.dataframe(albums_df, use_container_width=True, hide_index=True)

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

    st.markdown("#### Listening time by year")
    chart = (
        base_chart()
        .mark_line(color=PRIMARY, point=alt.OverlayMarkDef(color=ACCENT_COOL))
        .encode(
            x=alt.X("year:O", title="Year"),
            y=alt.Y("hours:Q", title="Hours listened"),
            tooltip=["year", "hours"]
        )
        .properties(height=300)
        .interactive()
    ).transform_data(data=yearly)
    st.altair_chart(chart, use_container_width=True)

    st.dataframe(yearly, use_container_width=True, hide_index=True)

    st.markdown("#### Top artists by year")
    year_artist = (
        f.groupby(["year", "artist"])["minutes"]
         .sum()
         .reset_index()
         .sort_values(["year", "minutes"], ascending=[True, False])
    )
    year_artist["rank"] = year_artist.groupby("year").cumcount() + 1

    st.dataframe(
        year_artist[year_artist["rank"] <= 10],
        use_container_width=True,
        hide_index=True
    )

    st.markdown("#### Artists that persisted across years")
    artist_years = (
        f.groupby("artist")["year"]
         .nunique()
         .sort_values(ascending=False)
         .head(20)
         .reset_index(name="years_listened")
    )
    st.dataframe(artist_years, use_container_width=True, hide_index=True)

# ---------- When ----------
with tab3:
    st.subheader("When do you listen?")

    hourly = f.groupby("hour")["minutes"].sum().reset_index()
    weekday_order = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday"
    ]
    weekday = (
        f.groupby("weekday")["minutes"]
         .sum()
         .reindex(weekday_order)
         .reset_index()
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Listening by hour")
        chart = (
            base_chart()
            .mark_bar(color=ACCENT_COOL)
            .encode(
                x=alt.X("hour:O", title="Hour of day"),
                y=alt.Y("minutes:Q", title="Minutes listened"),
                tooltip=["hour", "minutes"]
            )
            .properties(height=300)
            .interactive()
        ).transform_data(data=hourly)
        st.altair_chart(chart, use_container_width=True)

    with col2:
        st.markdown("#### Listening by day of week")
        chart = (
            base_chart()
            .mark_bar(color=ACCENT_WARM)
            .encode(
                x=alt.X("weekday:N", sort=weekday_order, title=None),
                y=alt.Y("minutes:Q", title="Minutes listened"),
                tooltip=["weekday", "minutes"]
            )
            .properties(height=300)
            .interactive()
        ).transform_data(data=weekday)
        st.altair_chart(chart, use_container_width=True)

    st.markdown("#### Listening over time")
    daily = f.groupby("date")["minutes"].sum().reset_index()
    chart = (
        base_chart()
        .mark_line(color=SECONDARY, point=alt.OverlayMarkDef(color=PRIMARY))
        .encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y("minutes:Q", title="Minutes listened"),
            tooltip=["date", "minutes"]
        )
        .properties(height=300)
        .interactive()
    ).transform_data(data=daily)
    st.altair_chart(chart, use_container_width=True)

# ---------- Replay / habits ----------
with tab4:
    st.subheader("🔁 Replay & listening personality")

    song_stats = (
        f.groupby(["track", "artist"])
         .agg(
             plays=("track", "size"),
             minutes=("minutes", "sum"),
             avg_minutes=("minutes", "mean"),
             skips=("skipped", "sum"),
         )
         .reset_index()
    )
    song_stats["skip_rate"] = song_stats["skips"] / song_stats["plays"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Avg. play length", f"{f['minutes'].mean():.2f} min")
    c2.metric("Skip rate", f"{100*f['skipped'].mean():.1f}%")
    c3.metric("Shuffle rate", f"{100*f['shuffle'].mean():.1f}%")

    st.markdown("#### Your most replayed songs")
    replay = song_stats.sort_values(["plays", "minutes"], ascending=False).head(25)
    st.dataframe(replay, use_container_width=True, hide_index=True)

    st.markdown("#### Songs you almost never skip")
    completed = song_stats[song_stats["plays"] >= 3].sort_values(
        ["skip_rate", "plays"], ascending=[True, False]
    ).head(25)
    st.dataframe(completed, use_container_width=True, hide_index=True)

    st.markdown("#### Songs with unusually high repeat behavior")
    repeat = song_stats[song_stats["plays"] >= 5].copy()
    if not repeat.empty:
        chart = (
            base_chart()
            .mark_bar(color=PRIMARY)
            .encode(
                x=alt.X("plays:Q", title="Plays"),
                y=alt.Y("track:N", sort="-x", title=None),
                tooltip=["track", "artist", "plays"]
            )
            .properties(height=400)
            .interactive()
        ).transform_data(data=repeat.sort_values("plays", ascending=False).head(20))
        st.altair_chart(chart, use_container_width=True)

# ---------- Deep cuts ----------
with tab5:
    st.subheader("🎧 Deep cuts & hidden patterns")

    artist_stats = (
        f.groupby("artist")
         .agg(
             minutes=("minutes", "sum"),
             plays=("track", "size"),
             unique_songs=("track", "nunique"),
         )
         .reset_index()
    )
    artist_stats["minutes_per_song"] = (
        artist_stats["minutes"] / artist_stats["unique_songs"]
    )

    st.markdown("#### Artists you go deep on")
    deep = artist_stats[artist_stats["plays"] >= 5].sort_values(
        "minutes_per_song", ascending=False
    ).head(25)
    st.dataframe(deep, use_container_width=True, hide_index=True)

    st.markdown("#### Songs you briefly sampled")
    sampled = song_stats.sort_values(
        ["avg_minutes", "plays"], ascending=[True, False]
    ).head(25)
    st.dataframe(sampled, use_container_width=True, hide_index=True)

    st.markdown("#### Album listening")
    album_stats = (
        f.groupby(["artist", "album"])
         .agg(
             plays=("track", "size"),
             minutes=("minutes", "sum"),
             unique_tracks=("track", "nunique"),
         )
         .reset_index()
         .sort_values("minutes", ascending=False)
    )
    st.dataframe(album_stats.head(50), use_container_width=True, hide_index=True)

# ---------- Wrapped ----------
with tab6:
    st.subheader("📝 Your yearly Spotify Wrapped")

    for year in sorted(f["year"].dropna().unique(), reverse=True):
        y = f[f["year"] == year]
        if y.empty:
            continue

        top_artist = (
            y.groupby("artist")["minutes"].sum().sort_values(ascending=False).index[0]
        )
        top_song = (
            y.groupby("track")["minutes"].sum().sort_values(ascending=False).index[0]
        )
        top_album = (
            y.groupby("album")["minutes"].sum().sort_values(ascending=False).index[0]
        )

        with st.expander(f"🎧 {int(year)}"):
            a, b, c, d = st.columns(4)
            a.metric("Hours", f"{y['minutes'].sum()/60:,.1f}")
            b.metric("Top artist", top_artist)
            c.metric("Top song", top_song)
            d.metric("Top album", top_album)

            ya = (
                y.groupby("artist")["minutes"]
                 .sum()
                 .sort_values(ascending=False)
                 .head(10)
                 .reset_index()
            )
            chart = (
                base_chart()
                .mark_bar(color=SECONDARY)
                .encode(
                    x=alt.X("minutes:Q", title="Minutes listened"),
                    y=alt.Y("artist:N", sort="-x", title=None),
                    tooltip=["artist", "minutes"]
                )
                .properties(height=300)
                .interactive()
            ).transform_data(data=ya)
            st.altair_chart(chart, use_container_width=True)

# ---------- Download ----------
st.divider()
st.subheader("📥 Export your analysis")

summary = (
    f.groupby(["artist", "track", "album"])
     .agg(
         plays=("track", "size"),
         minutes=("minutes", "sum"),
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

st.caption(
    "Privacy note: this app intentionally ignores the ip_addr field and does not "
    "need it for any analysis."
)

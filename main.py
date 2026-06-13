import streamlit as st
import pandas as pd
import re
from collections import Counter

from googleapiclient.discovery import build

from konlpy.tag import Okt
from wordcloud import WordCloud

import matplotlib.pyplot as plt

# -----------------------
# 페이지 설정
# -----------------------
st.set_page_config(
    page_title="유튜브 댓글 분석기",
    page_icon="📊",
    layout="wide"
)

st.title("📊 유튜브 댓글 심층 분석기")

# -----------------------
# API KEY
# -----------------------
api_key = st.text_input(
    "YouTube API Key",
    type="password"
)

video_url = st.text_input(
    "유튜브 링크 입력"
)

max_comments = st.slider(
    "수집할 댓글 수",
    100,
    1000,
    500,
    100
)

# -----------------------
# 영상 ID 추출
# -----------------------
def extract_video_id(url):
    patterns = [
        r"v=([^&]+)",
        r"youtu\.be/([^?]+)"
    ]

    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)

    return None

# -----------------------
# 댓글 수집
# -----------------------
def get_comments(video_id, api_key, limit):

    youtube = build(
        "youtube",
        "v3",
        developerKey=api_key
    )

    comments = []
    next_page_token = None

    while len(comments) < limit:

        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=100,
            pageToken=next_page_token,
            textFormat="plainText"
        )

        response = request.execute()

        for item in response["items"]:

            text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]

            comments.append(text)

            if len(comments) >= limit:
                break

        next_page_token = response.get("nextPageToken")

        if not next_page_token:
            break

    return comments

# -----------------------
# 감성 분석
# -----------------------
positive_words = [
    "좋다","좋아요","최고","재밌다",
    "사랑","감사","행복","대박",
    "멋지다","훌륭"
]

negative_words = [
    "별로","최악","싫다",
    "실망","망했다","구리다",
    "짜증","노잼","아쉽다"
]

def sentiment(comment):

    score = 0

    for w in positive_words:
        if w in comment:
            score += 1

    for w in negative_words:
        if w in comment:
            score -= 1

    if score > 0:
        return "긍정"

    elif score < 0:
        return "부정"

    return "중립"

# -----------------------
# 분석 시작
# -----------------------
if st.button("분석 시작"):

    if not api_key:
        st.error("API 키 입력")
        st.stop()

    video_id = extract_video_id(video_url)

    if not video_id:
        st.error("유튜브 링크 오류")
        st.stop()

    with st.spinner("댓글 수집중..."):

        comments = get_comments(
            video_id,
            api_key,
            max_comments
        )

    if len(comments) == 0:
        st.warning("댓글 없음")
        st.stop()

    df = pd.DataFrame({
        "댓글": comments
    })

    st.success(f"{len(df)}개 댓글 수집 완료")

    # -----------------------
    # 감성 분석
    # -----------------------
    df["감성"] = df["댓글"].apply(sentiment)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "긍정",
            len(df[df["감성"]=="긍정"])
        )

    with col2:
        st.metric(
            "부정",
            len(df[df["감성"]=="부정"])
        )

    with col3:
        st.metric(
            "중립",
            len(df[df["감성"]=="중립"])
        )

    # -----------------------
    # 감성 분포
    # -----------------------
    st.subheader("감성 분포")

    fig, ax = plt.subplots()

    df["감성"].value_counts().plot(
        kind="bar",
        ax=ax
    )

    st.pyplot(fig)

    # -----------------------
    # 형태소 분석
    # -----------------------
    st.subheader("단어 분석")

    okt = Okt()

    words = []

    for comment in comments:

        nouns = okt.nouns(comment)

        words.extend([
            n for n in nouns
            if len(n) >= 2
        ])

    word_count = Counter(words)

    top_words = pd.DataFrame(
        word_count.most_common(20),
        columns=["단어","횟수"]
    )

    st.dataframe(
        top_words,
        use_container_width=True
    )

    # -----------------------
    # 워드클라우드
    # -----------------------
    st.subheader("☁️ 워드클라우드")

    try:

        wc = WordCloud(
            font_path="NanumGothic.ttf",
            width=1200,
            height=600,
            background_color="white"
        )

        wc.generate_from_frequencies(
            word_count
        )

        fig, ax = plt.subplots(
            figsize=(14,7)
        )

        ax.imshow(wc)

        ax.axis("off")

        st.pyplot(fig)

    except Exception:

        st.warning(
            "NanumGothic.ttf 업로드 필요"
        )

    # -----------------------
    # 댓글 길이 분석
    # -----------------------
    st.subheader("댓글 길이 분석")

    df["길이"] = df["댓글"].apply(len)

    fig, ax = plt.subplots()

    ax.hist(df["길이"], bins=20)

    st.pyplot(fig)

    # -----------------------
    # 자주 등장 댓글
    # -----------------------
    st.subheader("자주 등장한 댓글")

    top_comments = pd.DataFrame(
        Counter(comments).most_common(20),
        columns=["댓글","횟수"]
    )

    st.dataframe(
        top_comments,
        use_container_width=True
    )

    # -----------------------
    # 다운로드
    # -----------------------
    csv = df.to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        "CSV 다운로드",
        csv,
        "youtube_comments.csv",
        "text/csv"
    )

import streamlit as st
import googleapiclient.discovery
import googleapiclient.errors
import pandas as pd
import re
import os
import requests
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# -----------------------------------------------------
# [한글 폰트 설정] 스트림릿 클라우드 환경을 위한 폰트 다운로드 함수
# -----------------------------------------------------
@st.cache_data
def download_korean_font():
    font_url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
    font_path = "NanumGothic-Regular.ttf"
    if not os.path.exists(font_path):
        response = requests.get(font_url)
        with open(font_path, "wb") as f:
            f.write(response.content)
    return font_path

# -----------------------------------------------------
# 유튜브 API 호출 및 댓글 수집 함수
# -----------------------------------------------------
def extract_video_id(url):
    """유튜브 URL에서 Video ID 추출"""
    pattern = r'(?:v=|\/v\/|youtu\.be\/|\/embed\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def get_youtube_comments(api_key, video_id, max_results=100):
    """유튜브 API를 사용해 댓글 수집"""
    youtube = googleapiclient.discovery.build(
        "youtube", "v3", developerKey=api_key
    )
    
    comments = []
    try:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(max_results, 100), # 한 번의 요청당 최대 100개
            textFormat="plainText"
        )
        
        while request and len(comments) < max_results:
            response = request.execute()
            for item in response['items']:
                comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                like_count = item['snippet']['topLevelComment']['snippet']['likeCount']
                author = item['snippet']['topLevelComment']['snippet']['authorDisplayName']
                comments.append({
                    "작성자": author,
                    "댓글내용": comment,
                    "좋아요수": like_count
                })
            
            # 다음 페이지가 있고 목표 수량을 채우지 못했다면 계속 수집
            if 'nextPageToken' in response and len(comments) < max_results:
                request = youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    pageToken=response['nextPageToken'],
                    maxResults=min(max_results - len(comments), 100),
                    textFormat="plainText"
                )
            else:
                break
                
        return pd.DataFrame(comments)
    except googleapiclient.errors.HttpError as e:
        st.error(f"유튜브 API 오류가 발생했습니다: {e}")
        return None
    except Exception as e:
        st.error(f"오류 발생: {e}")
        return None

# -----------------------------------------------------
# 스트림릿 UI 구성
# -----------------------------------------------------
st.set_page_config(page_title="유튜브 댓글 심도 분석기", layout="wide")

st.title("📊 유튜브 댓글 심도 분석 및 워드 클라우드")
st.markdown("유튜브 링크와 API 키를 입력하여 대중의 반응을 분석해 보세요.")

# 사이드바 설정
st.sidebar.header("🔑 설정 및 입력")
api_key = st.sidebar.text_input("YouTube API Key를 입력하세요", type="password")
video_url = st.sidebar.text_input("유튜브 영상 링크(URL)를 입력하세요")
max_comments = st.sidebar.slider("수집할 최대 댓글 수", min_value=50, max_value=500, value=100, step=50)

# 한글 폰트 사전 확보
font_path = download_korean_font()

if st.sidebar.button("🚀 댓글 수집 및 분석 시작"):
    if not api_key:
        st.warning("API Key를 입력해주세요.")
    elif not video_url:
        st.warning("유튜브 영상 링크를 입력해주세요.")
    else:
        video_id = extract_video_id(video_url)
        
        if not video_id:
            st.error("올바른 유튜브 URL 형식이 아닙니다.")
        else:
            with st.spinner("유튜브에서 댓글을 열심히 가져오는 중..."):
                df = get_youtube_comments(api_key, video_id, max_comments)
                
            if df is not None and not df.empty:
                st.success(f"총 {len(df)}개의 댓글을 성공적으로 수집했습니다!")
                
                # 레이아웃 분할
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.subheader("📝 수집된 댓글 데이터")
                    st.dataframe(df, use_container_width=True)
                    
                    # 가장 좋아요를 많이 받은 댓글 탑 3
                    st.subheader("👍 베스트 댓글 (좋아요 순)")
                    top_likes = df.sort_values(by="좋아요수", ascending=False).head(3)
                    for idx, row in top_likes.iterrows():
                        st.info(f"**{row['작성자']}** (👍 {row['좋아요수']}개)\n\n{row['댓글내용']}")
                
                with col2:
                    st.subheader("☁️ 한글 워드 클라우드 분석")
                    
                    # 텍스트 전처리 (한글, 영문, 공백만 남기기)
                    all_text = " ".join(df["댓글내용"].astype(str))
                    cleaned_text = re.sub(r'[^가-힣a-zA-Z\s]', '', all_text)
                    
                    if len(cleaned_text.strip()) > 0:
                        # 워드클라우드 생성 (무료 나눔고딕 폰트 경로 적용)
                        wordcloud = WordCloud(
                            font_path=font_path,
                            background_color="white",
                            width=800,
                            height=600,
                            max_words=100,
                            colormap='viridis'
                        ).generate(cleaned_text)
                        
                        # matplotlib로 스트림릿에 시각화 표출
                        fig, ax = plt.subplots(figsize=(10, 7))
                        ax.imshow(wordcloud, interpolation='bilinear')
                        ax.axis("off")
                        st.pyplot(fig)
                    else:
                        st.warning("분석할 만한 유효한 텍스트 단어가 부족합니다.")
                        
                    # 간단한 통계 요약
                    st.subheader("📊 댓글 핵심 통계")
                    total_likes = df["좋아요수"].sum()
                    avg_likes = df["좋아요수"].mean()
                    
                    st.metric(label="총 좋아요 수", value=f"{total_likes}개")
                    st.metric(label="댓글당 평균 좋아요 수", value=f"{avg_likes:.2f}개")
                    
            elif df is not None and df.empty:
                st.warning("이 영상에는 댓글이 없거나 댓글 기능이 중지되어 있습니다.")
